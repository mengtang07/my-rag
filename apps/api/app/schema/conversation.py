"""会话出入参"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schema.chat import Citation


class ConversationCreate(BaseModel):
    """新建会话"""

    title: str = Field(default="", max_length=200, description="会话标题；留空则用首条问题")


class ConversationBrief(BaseModel):
    """会话列表项"""

    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """会话消息"""

    id: int
    conversation_id: int
    role: str
    content: str
    citations: list[Citation] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
