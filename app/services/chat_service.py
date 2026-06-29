import json
import re
from typing import Optional

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import settings
from app.database.pinecone import get_pinecone_index
from app.database.postgres import get_db_cursor


def _get_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.OLLAMA_LLM_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.3,
    )


def _get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )


def _query_pinecone(query: str, top_k: int = 5) -> list[dict]:
    """Query Pinecone for relevant menu/document chunks."""
    embeddings = _get_embeddings()
    query_vector = embeddings.embed_query(query)
    index = get_pinecone_index()

    results = index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
    )

    matches = []
    for match in results.matches:
        if match.metadata and match.metadata.get("text"):
            matches.append({
                "text": match.metadata["text"],
                "score": match.score,
                "source": match.metadata.get("source", "Unknown"),
            })
    return matches


def _get_price_from_menu(dish_name: str) -> float:
    """Search Pinecone for dish price automatically."""
    contexts = _query_pinecone(f"{dish_name} price", top_k=3)
    for ctx in contexts:
        text = ctx["text"]
        # Look for price patterns like "Rs.600", "Rs 600", "600"
        match = re.search(
            rf"{re.escape(dish_name)}.*?(?:Rs\.?|PKR)?\s*(\d+(?:,\d+)?)",
            text,
            re.IGNORECASE
        )
        if match:
            # Remove commas from price like "1,600" → "1600"
            price_str = match.group(1).replace(",", "")
            return float(price_str)
        # Fallback — find any number near the text
        match = re.search(r"(\d{2,4})", text)
        if match:
            return float(match.group(1))
    return 0.0


def _get_chat_history(user_id: int, limit: int = 10) -> list[dict]:
    """Retrieve recent chat history from PostgreSQL."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT role, content
               FROM chat_history
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT %s""",
            (user_id, limit),
        )
        rows = cur.fetchall()
    return [
        {"role": row["role"], "content": row["content"]}
        for row in reversed(rows)
    ]


def _save_message(user_id: int, role: str, content: str):
    """Save a chat message to PostgreSQL."""
    with get_db_cursor(auto_commit=True) as cur:
        cur.execute(
            "INSERT INTO chat_history (user_id, role, content) VALUES (%s, %s, %s)",
            (user_id, role, content),
        )


def _parse_order_from_response(response: str) -> Optional[dict]:
    """Parse an order from the bot's response if it contains an order block."""
    order_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(order_pattern, response, re.DOTALL)
    if match:
        try:
            order_data = json.loads(match.group(1))
            if "items" in order_data and order_data["items"]:
                return order_data
        except (json.JSONDecodeError, KeyError):
            pass

    inline_pattern = r"\{\s*\"items\"\s*:"
    match = re.search(inline_pattern, response)
    if match:
        start = match.start()
        try:
            depth = 0
            for i in range(start, len(response)):
                if response[i] == "{":
                    depth += 1
                elif response[i] == "}":
                    depth -= 1
                    if depth == 0:
                        order_data = json.loads(response[start: i + 1])
                        if "items" in order_data and order_data["items"]:
                            return order_data
                        break
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def _enrich_items_with_prices(items: list[dict]) -> list[dict]:
    """
    Automatically fetch prices from Pinecone for each order item.
    Customer only provides dish name and quantity — price is fetched automatically.
    """
    enriched = []
    for item in items:
        dish_name = item.get("menu_item", "")
        quantity = item.get("quantity", 1)

        # Fetch price from menu PDF via Pinecone
        price = item.get("price", 0)
        if not price or price == 0:
            price = _get_price_from_menu(dish_name)

        enriched.append({
            "menu_item": dish_name,
            "quantity": quantity,
            "price": price,
            "subtotal": price * quantity,
        })
    return enriched


def _place_order_from_parse(
    user_id: int,
    order_data: dict,
    special_instructions: Optional[str] = None,
) -> Optional[int]:
    """Place an order — prices fetched automatically from menu."""
    items = order_data.get("items", [])
    if not items:
        return None

    # Enrich items with prices from Pinecone automatically
    enriched_items = _enrich_items_with_prices(items)

    # Calculate total
    total_amount = sum(item["subtotal"] for item in enriched_items)

    with get_db_cursor(auto_commit=True) as cur:
        cur.execute(
            """INSERT INTO orders (user_id, items, total_amount, special_instructions, status)
               VALUES (%s, %s, %s, %s, 'confirmed')
               RETURNING id""",
            (user_id, json.dumps(enriched_items), total_amount, special_instructions),
        )
        result = cur.fetchone()
        return result["id"] if result else None


def process_chat_message(
    user_id: int,
    message: str,
) -> dict:
    """Process a chat message through the RAG pipeline."""

    # Save user message
    _save_message(user_id, "user", message)

    # Get relevant menu context from Pinecone
    menu_contexts = _query_pinecone(message)

    # Get chat history
    history = _get_chat_history(user_id)

    # Build context string
    context_str = "\n\n".join(
        f"[Menu Item {i+1}] (Relevance: {ctx['score']:.2f})\n{ctx['text']}"
        for i, ctx in enumerate(menu_contexts)
    )

    # Build history string
    history_str = "\n".join(
        f"{msg['role']}: {msg['content']}" for msg in history[-6:]
    )

    # System prompt
    system_prompt = """You are RestoBot, a friendly and professional AI restaurant assistant.

Your role:
- Help customers understand the menu, make recommendations, and answer questions.
- When a customer wants to place an order, confirm it warmly and include a JSON order block.
- Prices are fetched automatically — customer only needs to provide dish name and quantity.
- Be warm, helpful, and professional at all times.

ORDER FORMAT:
When the user wants to place an order, end your response with:

```json
{{
  "items": [
    {{"menu_item": "Dish Name", "quantity": 1}},
    {{"menu_item": "Another Dish", "quantity": 2}}
  ]
}}
```

IMPORTANT:
- Do NOT ask customer for price — it is fetched automatically from the menu.
- Do NOT include price in the JSON — only menu_item and quantity.
- Only include JSON block when customer explicitly wants to order.

Current menu context:
{context}

Chat history:
{history}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}"),
    ])

    llm = _get_llm()
    chain = prompt | llm | StrOutputParser()

    response = chain.invoke({
        "context": context_str,
        "history": history_str,
        "question": message,
    })

    # Check if order should be placed
    order_id = None
    order_placed = False

    order_data = _parse_order_from_response(response)
    if order_data:
        order_id = _place_order_from_parse(user_id, order_data)
        if order_id:
            order_placed = True
            # Clean JSON block from response
            response = re.sub(
                r"```(?:json)?\s*\{.*?\}\s*```",
                "",
                response,
                flags=re.DOTALL,
            ).strip()
            response += (
                f"\n\n✅ **Order #{order_id} placed successfully!** "
                "Your order has been confirmed and is being prepared. "
                "Thank you for dining with us! 🍽️"
            )

    # Save assistant response
    _save_message(user_id, "assistant", response)

    return {
        "reply": response,
        "order_placed": order_placed,
        "order_id": order_id,
    }