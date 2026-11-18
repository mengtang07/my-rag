"""会话接口"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.exception.not_found import NotFoundException
from app.model.conversation import Conversation
from app.schema.base import PageResult
from app.schema.conversation import (
    ConversationBrief,
    ConversationCreate,
    MessageResponse,
)
from app.service.conversation_service import ConversationService

router = APIRouter(prefix="/api/conversations", tags=["会话"])


@router.post(
    "",
    response_model=ConversationBrief,
    status_code=201,
    summary="新建会话",
)
async def create_conversation(
    data: ConversationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationBrief:
    """新建一个空会话"""
    conversation = Conversation(title=data.title)
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return ConversationBrief.model_validate(conversation)


@router.get("", response_model=PageResult[ConversationBrief], summary="会话列表")
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="页码，从 1 起")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
) -> PageResult[ConversationBrief]:
    """会话分页列表"""
    return await ConversationService(db).list_conversations(
        page=page, page_size=page_size
    )


@router.get(
    "/{conversation_id}", response_model=ConversationBrief, summary="会话详情"
)
async def get_conversation(
    conversation_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationBrief:
    """按 id 取会话"""
    conversation = await ConversationService(db).get_conversation(conversation_id)
    if conversation is None:
        raise NotFoundException(message="会话不存在")
    return ConversationBrief.model_validate(conversation)


@router.get(
    "/{conversation_id}/messages",
    response_model=PageResult[MessageResponse],
    summary="会话消息",
)
async def list_messages(
    conversation_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="页码，从 1 起")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="每页条数")] = 50,
) -> PageResult[MessageResponse]:
    """某个会话的历史消息"""
    service = ConversationService(db)
    if await service.get_conversation(conversation_id) is None:
        raise NotFoundException(message="会话不存在")
    return await service.list_messages(conversation_id, page=page, page_size=page_size)


@router.delete("/{conversation_id}", status_code=204, summary="删除会话")
async def delete_conversation(
    conversation_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除会话（消息随外键级联删除）"""
    deleted = await ConversationService(db).delete_conversation(conversation_id)
    if not deleted:
        raise NotFoundException(message="会话不存在")
