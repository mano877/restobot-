from fastapi import APIRouter

from app.config import settings
from app.database.postgres import get_db_cursor
from app.database.pinecone import get_pinecone_client
from app.models.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health check endpoint",
)
def health_check():
    """Check the health status of the API and its dependencies."""
    # Check PostgreSQL
    db_status = "healthy"
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        db_status = "unhealthy"

    # Check Pinecone
    pinecone_status = "healthy"
    try:
        client = get_pinecone_client()
        client.list_indexes()
    except Exception:
        pinecone_status = "unhealthy"

    # Check Ollama
    ollama_status = "healthy"
    try:
        import httpx
        response = httpx.get(
            f"{settings.OLLAMA_BASE_URL}/api/tags",
            timeout=5.0,
        )
        if response.status_code != 200:
            ollama_status = "unhealthy"
    except Exception:
        ollama_status = "unhealthy"

    return HealthResponse(
        status="healthy" if all(
            s == "healthy" for s in [db_status, pinecone_status, ollama_status]
        ) else "degraded",
        version=settings.APP_VERSION,
        database=db_status,
        pinecone=pinecone_status,
        ollama=ollama_status,
    )
