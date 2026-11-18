"""消息模型"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.model.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.model.conversation import Conversation

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


class Message(Base, IDMixin, TimestampMixin):
    """会话消息

    Attributes:
        conversation_id: 所属会话
        role: `user` / `assistant`
        content: 消息正文
        citations: 引用列表（助手消息用），存 JSON
        token_count: 估算的 token 数
    """

    conversation_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    conversation: Mapped[Conversation] = relationship(
        back_populates="messages", lazy="selectin"
    )
