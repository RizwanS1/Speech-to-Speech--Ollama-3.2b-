from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assistant.server.auth import get_current_user
from assistant.server.db import get_db
from assistant.server.models import ChatMessage, ChatMessageResponse, User

router = APIRouter(tags=["history"])


@router.get("/history/{session_id}", response_model=list[ChatMessageResponse])
async def get_history(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChatMessageResponse]:
    result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.user_id == current_user.id,
            ChatMessage.session_id == session_id,
        )
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return [ChatMessageResponse.model_validate(message) for message in result.scalars()]
