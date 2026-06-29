from fastapi import APIRouter, Depends

from app.database.postgres import get_db_cursor
from app.middleware.auth_middleware import get_current_user
from app.models.schemas import HistoryResponse, ChatMessage

router = APIRouter(prefix="/users/{user_id}/history", tags=["History"])


@router.get(
    "",
    response_model=HistoryResponse,
    summary="Get chat history for a user",
)
def get_chat_history(
    user_id: int,
    current_user=Depends(get_current_user),
):
    """Retrieve the chat history for a specific user. Users can only view their own history."""
    # Ensure users can only access their own history
    if current_user.user_id != user_id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own chat history",
        )

    with get_db_cursor() as cur:
        cur.execute(
            """SELECT role, content, created_at
               FROM chat_history
               WHERE user_id = %s
               ORDER BY created_at ASC""",
            (user_id,),
        )
        rows = cur.fetchall()

    messages = [
        ChatMessage(
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )
        for row in rows
    ]

    return HistoryResponse(messages=messages, total=len(messages))


@router.delete(
    "",
    summary="Delete chat history for a user",
)
def delete_chat_history(
    user_id: int,
    current_user=Depends(get_current_user),
):
    """Delete the chat history for a specific user."""
    if current_user.user_id != user_id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own chat history",
        )

    with get_db_cursor(auto_commit=True) as cur:
        cur.execute(
            "DELETE FROM chat_history WHERE user_id = %s",
            (user_id,),
        )

    return {"message": "Chat history deleted successfully"}
