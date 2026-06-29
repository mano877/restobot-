from fastapi import APIRouter, Depends, Query

from app.middleware.auth_middleware import get_current_user
from app.models.schemas import MenuSearchResponse, RecommendationResponse
from app.services.menu_service import search_menu, get_recommendations

router = APIRouter(prefix="/menu", tags=["Menu"])


@router.get(
    "/search",
    response_model=MenuSearchResponse,
    summary="Search menu items",
)
def search_menu_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(10, ge=1, le=50),
    current_user=Depends(get_current_user),
):
    """Search the menu using semantic similarity."""
    return search_menu(query=q, top_k=top_k)


@router.get(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Get personalized menu recommendations",
)
def get_recommendations_endpoint(
    preferences: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
    current_user=Depends(get_current_user),
):
    """Get personalized menu recommendations based on your preferences."""
    return get_recommendations(
        preferences=preferences,
        top_k=top_k,
    )