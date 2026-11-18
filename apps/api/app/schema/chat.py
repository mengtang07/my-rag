"""对话出入参"""

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """一条引用来源"""

    index: int = Field(description="引用编号，回答正文里用 [编号] 标注")
    chunk_id: int
    document_id: int
    document_title: str
    heading_path: str = ""
    page_number: int | None = None
    score: float = 0.0


class ChatRequest(BaseModel):
    """对话请求"""

    question: str = Field(min_length=1, max_length=4000, description="用户问题")
    conversation_id: int | None = Field(default=None, description="会话 id；不填则新建")
    top_k: int = Field(default=5, ge=1, le=20, description="召回条数")


class ChatResponse(BaseModel):
    """对话结果（非流式）"""

    conversation_id: int
    message_id: int
    answer: str
    citations: list[Citation] = Field(default_factory=list)
