"""文档入库：解析 → 切块 → 向量化 → 落库 → 建索引

写入顺序固定为 **PostgreSQL 先 → Milvus 后 → PostgreSQL 状态最后**：

- 反过来（先写 Milvus）会产生无法对齐的孤儿向量 —— 崩溃后既不知道该删哪个主键，
  也对不上 PG 的序列。
- 先写 PG 的失败态是**可恢复**的：切块行已经在 PG 里，文档状态停在 `indexing`，
  重跑 `reindex_document()` 只需要「向量化 + 写 Milvus + 改状态」三步。

因此这个流程在关键节点会**中途提交**，而不是攒到最后一次性提交。
"""

import hashlib

from rag_core.chunking import chunk_blocks
from rag_core.models import ParsedDocument
from rag_core.parsing import UnsupportedFormatError, detect_parser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import llm_settings, rag_settings
from app.core.llm import LiteLLMClient, get_llm_client
from app.core.vector_store import VectorStore, get_vector_store
from app.exception.parse import ParseException
from app.exception.vector_store import VectorStoreException
from app.model.chunk import Chunk
from app.model.document import (
    STATUS_FAILED,
    STATUS_INDEXING,
    STATUS_PARSING,
    STATUS_READY,
    Document,
)
from app.service.base import BaseService


class IngestService(BaseService):
    """入库编排"""

    def __init__(
        self,
        db: AsyncSession,
        llm: LiteLLMClient | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        super().__init__(db)
        self._llm = llm
        self._vector_store = vector_store

    @property
    def llm(self) -> LiteLLMClient:
        if self._llm is None:
            self._llm = get_llm_client()
        return self._llm

    @property
    def vector_store(self) -> VectorStore:
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    async def ingest_bytes(
        self,
        data: bytes,
        filename: str,
        *,
        title: str | None = None,
        source_type: str = "file",
    ) -> tuple[Document, bool]:
        """把一份内容摄入知识库

        相同内容重复摄入是幂等的：命中已存在的 sha256 就直接返回原文档。

        Args:
            data: 文件字节
            filename: 文件名（决定解析格式）
            title: 展示标题；不填则用解析出的标题或文件名
            source_type: 来源类型：`file` / `text`

        Returns:
            `(文档, 是否命中已有文档的幂等返回)`

        Raises:
            ParseException: 格式不支持或解析失败
            VectorStoreException: 向量维度与集合不一致
        """
        content_hash = hashlib.sha256(data).hexdigest()

        existing = await self.db.scalar(
            select(Document).where(Document.content_hash == content_hash)
        )
        if existing is not None:
            if existing.status == STATUS_READY:
                return existing, True
            # 上次没处理完（失败或中断）：清干净重来
            await self.vector_store.delete_document(existing.id)
            await self.db.delete(existing)
            await self.db.flush()

        parsed = self._parse(data, filename)

        document = Document(
            title=title or parsed.title or filename,
            filename=filename,
            source_type=source_type,
            file_type=parsed.metadata.get("source"),
            file_size=len(data),
            content_hash=content_hash,
            status=STATUS_PARSING,
        )
        self.db.add(document)
        # 中途提交：让文档行先落地，后面任何一步失败都能查到它
        await self.db.commit()
        await self.db.refresh(document)

        try:
            await self._ingest_parsed(document, parsed)
        except Exception as exc:
            # 把失败状态落库（否则异常回滚后连失败记录都没有）
            await self._mark_failed(document.id, str(exc))
            raise

        return document, False

    def _parse(self, data: bytes, filename: str) -> ParsedDocument:
        """解析文件，失败翻译成业务异常"""
        try:
            parser = detect_parser(filename)
            return parser(data, filename)
        except UnsupportedFormatError as exc:
            raise ParseException(
                message=str(exc), original_exception=exc
            ) from exc
        except Exception as exc:
            raise ParseException(
                message=f"文档解析失败：{exc}",
                detail=repr(exc),
                original_exception=exc,
            ) from exc

    async def _ingest_parsed(self, document: Document, parsed: ParsedDocument) -> None:
        """切块 → 落库 → 向量化 → 写 Milvus → 改状态"""
        drafts = chunk_blocks(
            parsed.blocks,
            max_chars=rag_settings.chunk_max_chars,
            min_chars=rag_settings.chunk_min_chars,
            overlap=rag_settings.chunk_overlap,
        )
        if not drafts:
            raise ParseException(message="文档解析后没有可切分的内容")

        chunks: list[Chunk] = []
        for draft in drafts:
            chunk = Chunk(
                document_id=document.id,
                chunk_index=draft.chunk_index,
                content=draft.text,
                heading_path=draft.heading_path,
                page_number=draft.page_number,
                char_start=draft.char_start,
                char_end=draft.char_end,
                token_count=draft.token_count,
                embedding_model=llm_settings.embed_model,
            )
            self.db.add(chunk)
            chunks.append(chunk)

        document.status = STATUS_INDEXING
        document.chunk_count = len(drafts)
        # 中途提交：切块行先落地，失败后可以只重建向量
        await self.db.commit()
        await self.db.refresh(document)

        vectors = await self.llm.embed_texts([draft.text for draft in drafts])
        if len(vectors) != len(drafts):
            raise VectorStoreException(message="向量化返回的条数与切块数不一致")

        for vector in vectors:
            if len(vector) != self.vector_store.embed_dim:
                raise VectorStoreException(
                    message=(
                        f"embedding 模型返回的维度是 {len(vector)}，"
                        f"与集合配置的 {self.vector_store.embed_dim} 不一致；"
                        "请检查 LLM_EMBED_MODEL 或执行 make milvus-reset"
                    )
                )

        rows = [
            {
                "pk": chunk.id,
                "vector": vector,
                "doc_id": document.id,
                "chunk_index": chunk.chunk_index,
            }
            for chunk, vector in zip(chunks, vectors)
        ]
        await self.vector_store.upsert_chunks(rows)

        document.status = STATUS_READY
        document.embedding_model = llm_settings.embed_model
        document.error_message = None
        await self.db.commit()
        await self.db.refresh(document)

    async def _mark_failed(self, document_id: int, message: str) -> None:
        """把文档标记为失败（失败状态要能留下来）"""
        document = await self.db.get(Document, document_id)
        if document is None:
            return
        document.status = STATUS_FAILED
        document.error_message = message[:2000]
        await self.db.commit()

    async def reindex_document(self, document: Document) -> int:
        """用当前 embedding 模型重建某个文档的向量

        切块正文不变，只重算向量并覆盖 Milvus 里的数据。
        """
        rows = await self.db.execute(
            select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index)
        )
        chunks = list(rows.scalars().all())
        if not chunks:
            raise ParseException(message="文档没有切块，无法重建索引")

        await self.vector_store.delete_document(document.id)

        vectors = await self.llm.embed_texts([chunk.content for chunk in chunks])
        for vector in vectors:
            if len(vector) != self.vector_store.embed_dim:
                raise VectorStoreException(
                    message=(
                        f"embedding 模型返回的维度是 {len(vector)}，"
                        f"与集合配置的 {self.vector_store.embed_dim} 不一致"
                    )
                )

        await self.vector_store.upsert_chunks(
            [
                {
                    "pk": chunk.id,
                    "vector": vector,
                    "doc_id": document.id,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk, vector in zip(chunks, vectors)
            ]
        )

        document.embedding_model = llm_settings.embed_model
        document.status = STATUS_READY
        document.error_message = None
        await self.db.commit()

        return len(chunks)
