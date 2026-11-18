"""文档模型"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.model.chunk import Chunk

# 文档状态：pending → parsing → indexing → ready，任一步失败转 failed
STATUS_PENDING = "pending"
STATUS_PARSING = "parsing"
STATUS_INDEXING = "indexing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"


class Document(Base, IDMixin, TimestampMixin):
    """文档

    一份被摄入知识库的原始资料。**切块正文不在这里**，在 `chunk` 表；
    本表只存元信息，便于列表页展示与状态跟踪。

    Attributes:
        title: 展示标题；解析器拿不到时回退到文件名
        filename: 原始文件名
        source_type: 来源类型：`file` / `text` / `url`
        file_type: 格式：`markdown` / `pdf` / `docx` / `html` / `text`
        file_size: 文件字节数
        content_hash: 内容 sha256，**唯一** —— 用来做重复摄入的幂等去重
        status: 处理状态，取值见本模块的 `STATUS_*` 常量
        error_message: 失败原因
        chunk_count: 已生成的切块数
        embedding_model: 生成向量时用的 embedding 模型名（换模型后据此判断要不要重建）
        source_path: 原始路径或 URL
    """

    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="file"
    )
    file_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=STATUS_PENDING, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
