from typing import Optional

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import settings
from app.database.pinecone import get_pinecone_index
from app.models.schemas import MenuSearchResult, MenuSearchResponse, RecommendationResponse


def _get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )


def _get_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.OLLAMA_LLM_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.3,
    )


def _query_pinecone(query: str, top_k: int = 5) -> list[dict]:
    """Query Pinecone for relevant menu chunks."""
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
                "id": match.id,
                "text": match.metadata["text"],
                "score": match.score,
                "source": match.metadata.get("source", "Unknown"),
            })
    return matches


def search_menu(
    query: str,
    top_k: int = 10,
) -> MenuSearchResponse:
    """Search the menu by query text using vector similarity."""
    matches = _query_pinecone(query, top_k=top_k)

    if not matches:
        return MenuSearchResponse(query=query, results=[], total=0)

    # Format results using LLM
    chunks_text = "\n\n".join(m["text"] for m in matches)

    system_prompt = """You are a restaurant menu assistant.
Extract relevant dishes from the menu text based on the customer query.

IMPORTANT RULES:
- Only include dishes that DIRECTLY match the query
- Do NOT suggest random accompaniments unless asked
- Do NOT pair rice dishes (Biryani, Pulao) with bread (Naan, Paratha)
- Maximum 5 results

Format your response as:
🍽️ Dish Name — Rs. Price
   Description"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Customer query: {query}\n\nMenu text:\n{chunks}"),
    ])

    llm = _get_llm()
    chain = prompt | llm | StrOutputParser()
    formatted_text = chain.invoke({"query": query, "chunks": chunks_text})

    result = MenuSearchResult(
        id="search_result",
        text=formatted_text,
        score=1.0,
        source="AI formatted result",
    )

    return MenuSearchResponse(
        query=query,
        results=[result],
        total=1,
    )


def get_recommendations(
    preferences: str,
    top_k: int = 5,
) -> RecommendationResponse:
    """Get menu recommendations based on user preferences."""
    matches = _query_pinecone(preferences, top_k=top_k)

    if not matches:
        return RecommendationResponse(recommendations=[], based_on=preferences)

    # Format recommendations using LLM
    chunks_text = "\n\n".join(m["text"] for m in matches)

    system_prompt = """You are a friendly restaurant assistant.
Recommend the best matching dishes based on customer preferences.

IMPORTANT RULES:
- Only recommend dishes that DIRECTLY match the preference
- Do NOT suggest random accompaniments or side dishes unless asked
- Do NOT pair rice dishes (Biryani, Pulao) with bread (Naan, Paratha)
- Keep recommendations focused and relevant
- Maximum 3 recommendations

Format your response as:
🌟 Recommended for you:

🍽️ Dish Name — Rs. Price
   Why we recommend it: [reason based on preferences]

Keep it warm, friendly and helpful."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Customer preferences: {preferences}\n\nMenu:\n{chunks}"),
    ])

    llm = _get_llm()
    chain = prompt | llm | StrOutputParser()
    formatted = chain.invoke({
        "preferences": preferences,
        "chunks": chunks_text,
    })

    result = MenuSearchResult(
        id="recommendation_result",
        text=formatted,
        score=1.0,
        source="AI recommendation",
    )

    return RecommendationResponse(
        recommendations=[result],
        based_on=preferences,
    )