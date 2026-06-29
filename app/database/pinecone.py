from typing import Optional

from pinecone import Pinecone, ServerlessSpec

from app.config import settings

_pinecone_client: Optional[Pinecone] = None
_pinecone_index = None


def get_pinecone_client() -> Pinecone:
    global _pinecone_client
    if _pinecone_client is None:
        _pinecone_client = Pinecone(api_key=settings.PINECONE_API_KEY)
    return _pinecone_client


def get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        client = get_pinecone_client()
        existing = client.list_indexes()
        index_names = [idx.name for idx in existing]

        if settings.PINECONE_INDEX_NAME not in index_names:
            client.create_index(
                name=settings.PINECONE_INDEX_NAME,
                dimension=settings.PINECONE_EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=settings.PINECONE_ENVIRONMENT,
                ),
            )

        _pinecone_index = client.Index(settings.PINECONE_INDEX_NAME)
    return _pinecone_index


def delete_vectors_by_filter(filter_dict: dict):
    """Delete vectors from Pinecone matching the given filter."""
    index = get_pinecone_index()
    try:
        index.delete(filter=filter_dict)
    except Exception:
        pass


def delete_vectors_by_ids(ids: list[str]):
    """Delete specific vectors by their IDs."""
    index = get_pinecone_index()
    try:
        index.delete(ids=ids)
    except Exception:
        pass
def get_pinecone_client() -> Pinecone:
    global _pinecone_client
    if _pinecone_client is None:
        print(f"DEBUG PINECONE KEY: {settings.PINECONE_API_KEY[:10]}...")  # shows first 10 chars only
        _pinecone_client = Pinecone(api_key=settings.PINECONE_API_KEY)
    return _pinecone_client