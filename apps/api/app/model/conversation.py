"""会话模型"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.model.message import Message


class Conversation(Base, IDMixin, TimestampMixin):
    """会话

    Attributes:
        title: 会话标题，默认取首条问题的前若干字符
    """

    title: Mapped[str] = mapped_column(
        String(200), nullable=False, server_default=""
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
