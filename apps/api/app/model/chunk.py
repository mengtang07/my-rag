"""切块模型"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.model.document import Document


class Chunk(Base, IDMixin, TimestampMixin):
    """切块

    **切块正文只存在这里**（PostgreSQL 是唯一真相源）。
    Milvus 里只放向量和主键，主键就是本表的 `id` —— 检索命中后回表取正文。

    Attributes:
        document_id: 所属文档
        chunk_index: 文档内序号，从 0 起
        content: 切块正文（已带 `## 标题路径` 前缀）
        heading_path: 标题层级路径，如 `安装 > 依赖`
        page_number: 页码（1 起）；只有 PDF 之类的分页格式才有
        char_start: 在原始纯文本中的起始字符偏移
        char_end: 在原始纯文本中的结束字符偏移
        token_count: 估算的 token 数
        embedding_model: 该切块向量所用的 embedding 模型
    """

    document_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    heading_path: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default=""
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    document: Mapped[Document] = relationship(
        back_populates="chunks", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
    )
