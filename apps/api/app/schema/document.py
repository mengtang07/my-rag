"""文档出入参"""

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentBrief(BaseModel):
    """文档列表项"""

    id: int
    title: str
    filename: str
    file_type: str | None = None
    file_size: int = 0
    status: str = Field(description="pending/parsing/indexing/ready/failed")
    chunk_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(DocumentBrief):
    """文档详情"""

    source_type: str
    content_hash: str
    embedding_model: str | None = None
    error_message: str | None = None
    source_path: str | None = None
    updated_at: datetime


class DocumentTextCreate(BaseModel):
    """直接提交文本入库"""

    title: str = Field(min_length=1, max_length=300, description="文档标题")
    content: str = Field(min_length=1, description="markdown 或纯文本内容")
    filename: str | None = Field(
        default=None, max_length=255, description="可选文件名，用于判定解析格式"
    )


class DocumentIngestResponse(BaseModel):
    """入库结果"""

    document_id: int
    title: str
    status: str
    chunk_count: int
    reused: bool = Field(default=False, description="是否命中已存在文档的幂等返回")
    message: str = "success"


class ReindexResponse(BaseModel):
    """重建向量索引的结果"""

    document_id: int
    chunk_count: int
    embedding_model: str
    message: str = "success"
