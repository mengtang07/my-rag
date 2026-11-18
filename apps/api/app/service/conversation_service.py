"""会话与消息"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.conversation import Conversation
from app.model.message import Message
from app.schema.conversation import ConversationBrief, MessageResponse
from app.service.base import BaseService, PageResult


class ConversationService(BaseService):
    """会话管理"""

    async def list_conversations(
        self, *, page: int = 1, page_size: int = 20
    ) -> PageResult[ConversationBrief]:
        """会话分页列表"""
        total = await self.db.scalar(select(func.count()).select_from(Conversation)) or 0
        rows = await self.db.execute(
            select(Conversation)
            .order_by(Conversation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [ConversationBrief.model_validate(row) for row in rows.scalars().all()]
        return PageResult(items=items, total=total, page=page, page_size=page_size)

    async def get_conversation(self, conversation_id: int) -> Conversation | None:
        """按 id 取会话"""
        return await self.db.get(Conversation, conversation_id)

    async def list_messages(
        self, conversation_id: int, *, page: int = 1, page_size: int = 50
    ) -> PageResult[MessageResponse]:
        """会话的消息历史"""
        count_stmt = (
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        total = await self.db.scalar(count_stmt) or 0

        rows = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [MessageResponse.model_validate(row) for row in rows.scalars().all()]
        return PageResult(items=items, total=total, page=page, page_size=page_size)

    async def delete_conversation(self, conversation_id: int) -> bool:
        """删除会话（消息随外键级联删除）"""
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            return False
        await self.db.delete(conversation)
        await self.db.flush()
        return True
