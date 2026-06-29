from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_user
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import process_chat_message

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to RestoBot",
)
def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    """Send a message to the AI restaurant assistant.

    The bot can answer menu questions, make recommendations, and automatically
    place orders when asked.
    """
    result = process_chat_message(
        user_id=current_user.user_id,
        message=request.message,
    )

    return ChatResponse(
        reply=result["reply"],
        user_id=current_user.user_id,
        order_placed=result["order_placed"],
        order_id=result["order_id"],
    )