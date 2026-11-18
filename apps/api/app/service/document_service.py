"""文档管理"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.vector_store import VectorStore, get_vector_store
from app.exception.not_found import NotFoundException
from app.model.chunk import Chunk
from app.model.document import Document
from app.schema.chunk import ChunkBrief
from app.schema.document import DocumentBrief, DocumentResponse
from app.service.base import BaseService, PageResult


class DocumentService(BaseService):
    """文档的增删查"""

    def __init__(
        self, db: AsyncSession, vector_store: VectorStore | None = None
    ) -> None:
        super().__init__(db)
        self._vector_store = vector_store

    @property
    def vector_store(self) -> VectorStore:
        """向量库封装（默认用进程内共享的那个）"""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    async def list_documents(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PageResult[DocumentBrief]:
        """文档分页列表"""
        conditions: list[ColumnElement[bool]] = []
        if keyword:
            like = f"%{keyword}%"
            conditions.append(Document.title.ilike(like) | Document.filename.ilike(like))
        if status:
            conditions.append(Document.status == status)

        count_stmt = select(func.count()).select_from(Document)
        stmt = select(Document)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            stmt = stmt.where(condition)

        total = await self.db.scalar(count_stmt) or 0

        rows = await self.db.execute(
            stmt.order_by(Document.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [DocumentBrief.model_validate(row) for row in rows.scalars().all()]

        return PageResult(items=items, total=total, page=page, page_size=page_size)

    async def get_document(self, document_id: int) -> Document | None:
        """按 id 取文档，不存在返回 None"""
        return await self.db.get(Document, document_id)

    async def get_document_response(self, document_id: int) -> DocumentResponse:
        """按 id 取文档详情，不存在抛业务异常"""
        document = await self.get_document(document_id)
        if document is None:
            raise NotFoundException(message="文档不存在")
        return DocumentResponse.model_validate(document)

    async def list_chunks(
        self, document_id: int, *, page: int = 1, page_size: int = 50
    ) -> PageResult[ChunkBrief]:
        """某个文档下的切块列表"""
        count_stmt = (
            select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
        )
        total = await self.db.scalar(count_stmt) or 0

        rows = await self.db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [ChunkBrief.model_validate(row) for row in rows.scalars().all()]

        return PageResult(items=items, total=total, page=page, page_size=page_size)

    async def delete_document(self, document_id: int) -> bool:
        """删除文档

        顺序很重要：**先删 Milvus 向量，再删 PostgreSQL 行**。
        反过来的话，PG 删成功而 Milvus 删失败会留下查不到正文的孤儿向量；
        而 PG 有正文但向量没了，检索会直接漏召回，更糟。
        """
        document = await self.get_document(document_id)
        if document is None:
            return False

        await self.vector_store.delete_document(document_id)
        await self.db.delete(document)
        await self.db.flush()
        return True
