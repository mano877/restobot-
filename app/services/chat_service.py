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
        match = re.search(
            rf"{re.escape(dish_name)}.*?(?:Rs\.?|PKR)?\s*(\d+(?:,\d+)?)",
            text,
            re.IGNORECASE
        )
        if match:
            price_str = match.group(1).replace(",", "")
            return float(price_str)
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
    """Parse an order from the bot's response."""
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


def _detect_cancel_intent(message: str) -> Optional[int]:
    """Detect if user wants to cancel an order and extract order ID."""
    # Match patterns like "cancel order 7", "cancel #7", "cancel my order #7"
    match = re.search(
        r"cancel.*?(?:order)?.*?#?(\d+)",
        message,
        re.IGNORECASE
    )
    if match:
        return int(match.group(1))

    # Match "cancel my last order" or "cancel my order" without ID
    if re.search(r"cancel.*?order", message, re.IGNORECASE):
        return -1  # -1 means cancel latest order

    return None


def _get_latest_order_id(user_id: int) -> Optional[int]:
    """Get the most recent active order ID for a user."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT id FROM orders 
               WHERE user_id = %s 
               AND status NOT IN ('delivered', 'cancelled')
               ORDER BY created_at DESC 
               LIMIT 1""",
            (user_id,),
        )
        result = cur.fetchone()
        return result["id"] if result else None


def _cancel_order(user_id: int, order_id: int) -> tuple[bool, str]:
    """Cancel an order — returns (success, message)."""
    # Check order exists and belongs to user
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id, status FROM orders WHERE id = %s AND user_id = %s",
            (order_id, user_id),
        )
        order = cur.fetchone()

    if not order:
        return False, f"I couldn't find Order #{order_id} in your account."

    if order["status"] == "delivered":
        return False, f"Order #{order_id} has already been delivered and cannot be cancelled."

    if order["status"] == "cancelled":
        return False, f"Order #{order_id} is already cancelled."

    # Cancel the order
    with get_db_cursor(auto_commit=True) as cur:
        cur.execute(
            """UPDATE orders SET status = 'cancelled', updated_at = NOW()
               WHERE id = %s AND user_id = %s
               RETURNING id""",
            (order_id, user_id),
        )
        result = cur.fetchone()

    if result:
        return True, f"Order #{order_id} has been cancelled successfully."
    return False, "Something went wrong while cancelling your order."


def _enrich_items_with_prices(items: list[dict]) -> list[dict]:
    """Automatically fetch prices from Pinecone for each order item."""
    enriched = []
    for item in items:
        dish_name = item.get("menu_item", "")
        quantity = item.get("quantity", 1)
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
) -> tuple[Optional[int], float]:
    """Place an order — returns (order_id, total_amount)."""
    items = order_data.get("items", [])
    if not items:
        return None, 0.0

    enriched_items = _enrich_items_with_prices(items)
    total_amount = sum(item["subtotal"] for item in enriched_items)

    with get_db_cursor(auto_commit=True) as cur:
        cur.execute(
            """INSERT INTO orders (user_id, items, total_amount, special_instructions, status)
               VALUES (%s, %s, %s, %s, 'confirmed')
               RETURNING id""",
            (user_id, json.dumps(enriched_items), total_amount, special_instructions),
        )
        result = cur.fetchone()
        order_id = result["id"] if result else None

    return order_id, total_amount


def process_chat_message(
    user_id: int,
    message: str,
) -> dict:
    """Process a chat message through the RAG pipeline."""

    _save_message(user_id, "user", message)

    # ── Step 1: Check for cancel intent FIRST ────────────────────────────
    cancel_order_id = _detect_cancel_intent(message)
    if cancel_order_id is not None:
        # If no specific order ID, cancel latest order
        if cancel_order_id == -1:
            cancel_order_id = _get_latest_order_id(user_id)
            if not cancel_order_id:
                response = "You don't have any active orders to cancel. 😊"
                _save_message(user_id, "assistant", response)
                return {
                    "reply": response,
                    "order_placed": False,
                    "order_id": None,
                }

        success, cancel_message = _cancel_order(user_id, cancel_order_id)
        if success:
            response = (
                f"❌ **Order Cancelled**\n\n"
                f"{cancel_message}\n\n"
                "If you'd like to place a new order, just let me know! 😊"
            )
        else:
            response = f"⚠️ {cancel_message}\n\nIs there anything else I can help you with?"

        _save_message(user_id, "assistant", response)
        return {
            "reply": response,
            "order_placed": False,
            "order_id": None,
        }

    # ── Step 2: Normal chat flow ──────────────────────────────────────────
    menu_contexts = _query_pinecone(message)
    history = _get_chat_history(user_id)

    context_str = "\n\n".join(
        f"[Menu Item {i+1}] (Relevance: {ctx['score']:.2f})\n{ctx['text']}"
        for i, ctx in enumerate(menu_contexts)
    )

    history_str = "\n".join(
        f"{msg['role']}: {msg['content']}" for msg in history[-6:]
    )

    system_prompt = """You are RestoBot, a friendly and professional AI restaurant assistant.

Your role:
- Help customers understand the menu, make recommendations, and answer questions.
- When a customer wants to place an order, confirm it warmly and include a JSON order block.
- Prices are fetched automatically — customer only needs to provide dish name and quantity.
- Be warm, helpful, and professional at all times.
- Do NOT say "Here's the order block" or mention JSON to the customer.
- Do NOT reveal internal JSON to customer — it is for internal use only.
- Just confirm the order warmly and naturally.

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
- Do NOT ask customer for price — it is fetched automatically.
- Do NOT include price in JSON — only menu_item and quantity.
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

    order_id = None
    order_placed = False
    total_amount = 0.0

    order_data = _parse_order_from_response(response)
    if order_data:
        order_id, total_amount = _place_order_from_parse(user_id, order_data)
        if order_id:
            order_placed = True
            items_summary = "\n".join(
                f"• {item['menu_item']} x{item['quantity']}"
                for item in order_data.get("items", [])
            )
            response = (
                f"Thank you for your order! 😊\n\n"
                f"📋 **Your Order:**\n{items_summary}\n\n"
                f"✅ **Order #{order_id} placed successfully!**\n"
                f"💰 **Total Amount: Rs. {total_amount:.0f}**\n"
                "Your order is being prepared. Thank you for dining with us! 🍽️"
            )

    _save_message(user_id, "assistant", response)

    return {
        "reply": response,
        "order_placed": order_placed,
        "order_id": order_id,
    }