"""文档接口"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config import rag_settings
from app.core.database import get_db
from app.core.llm import LiteLLMClient, get_llm_client
from app.core.vector_store import VectorStore, get_vector_store
from app.exception.not_found import NotFoundException
from app.exception.parse import ParseException
from app.model.document import Document
from app.schema.chunk import ChunkBrief
from app.schema.document import (
    DocumentBrief,
    DocumentIngestResponse,
    DocumentResponse,
    DocumentTextCreate,
    ReindexResponse,
)
from app.schema.base import PageResult
from app.service.document_service import DocumentService
from app.service.ingest_service import IngestService

router = APIRouter(prefix="/api/documents", tags=["文档"])


@router.post(
    "", response_model=DocumentIngestResponse, status_code=201, summary="上传文档并入库"
)
async def create_document(
    file: Annotated[UploadFile, File(description="要摄入的文件")],
    db: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LiteLLMClient, Depends(get_llm_client)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
) -> DocumentIngestResponse:
    """上传文件，解析 → 切块 → 向量化 → 落库

    相同内容重复上传是幂等的，会直接返回已有文档。
    """
    data = await file.read()

    limit = rag_settings.max_file_mb * 1024 * 1024
    if len(data) > limit:
        raise ParseException(message=f"文件超过大小上限（{rag_settings.max_file_mb}MB）")

    filename = file.filename or "upload.txt"
    document, reused = await IngestService(db, llm=llm, vector_store=store).ingest_bytes(
        data, filename, source_type="file"
    )

    return DocumentIngestResponse(
        document_id=document.id,
        title=document.title,
        status=document.status,
        chunk_count=document.chunk_count,
        reused=reused,
        message="文档已入库" if not reused else "文档已存在，直接复用",
    )


@router.post(
    "/text",
    response_model=DocumentIngestResponse,
    status_code=201,
    summary="直接提交文本入库",
)
async def create_document_text(
    data: DocumentTextCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LiteLLMClient, Depends(get_llm_client)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
) -> DocumentIngestResponse:
    """把一段 markdown / 纯文本直接摄入知识库"""
    filename = data.filename or "text.md"
    document, reused = await IngestService(
        db, llm=llm, vector_store=store
    ).ingest_bytes(
        data.content.encode("utf-8"),
        filename,
        title=data.title,
        source_type="text",
    )

    return DocumentIngestResponse(
        document_id=document.id,
        title=document.title,
        status=document.status,
        chunk_count=document.chunk_count,
        reused=reused,
        message="文本已入库" if not reused else "文本已存在，直接复用",
    )


@router.get("", response_model=PageResult[DocumentBrief], summary="文档列表")
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    keyword: Annotated[str | None, Query(description="按标题/文件名模糊匹配")] = None,
    status: Annotated[str | None, Query(description="按处理状态过滤")] = None,
    page: Annotated[int, Query(ge=1, description="页码，从 1 起")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
) -> PageResult[DocumentBrief]:
    """文档分页列表"""
    return await DocumentService(db).list_documents(
        keyword=keyword, status=status, page=page, page_size=page_size
    )


@router.get(
    "/{document_id}", response_model=DocumentResponse, summary="文档详情"
)
async def get_document(
    document_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentResponse:
    """按 id 取文档详情"""
    return await DocumentService(db).get_document_response(document_id)


@router.get(
    "/{document_id}/chunks",
    response_model=PageResult[ChunkBrief],
    summary="查看文档的切块",
)
async def list_document_chunks(
    document_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="页码，从 1 起")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="每页条数")] = 50,
) -> PageResult[ChunkBrief]:
    """查看某个文档切出来的片段（调试与核对引用用）"""
    service = DocumentService(db)
    if await service.get_document(document_id) is None:
        raise NotFoundException(message="文档不存在")
    return await service.list_chunks(document_id, page=page, page_size=page_size)


@router.post(
    "/{document_id}/reindex", response_model=ReindexResponse, summary="重建文档向量"
)
async def reindex_document(
    document_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LiteLLMClient, Depends(get_llm_client)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
) -> ReindexResponse:
    """用当前 embedding 模型重建该文档的向量（切块正文不变）"""
    service = IngestService(db, llm=llm, vector_store=store)
    document = await service.db.get(Document, document_id)
    if document is None:
        raise NotFoundException(message="文档不存在")

    count = await service.reindex_document(document)
    return ReindexResponse(
        document_id=document_id,
        chunk_count=count,
        embedding_model=document.embedding_model or "",
    )


@router.delete("/{document_id}", status_code=204, summary="删除文档")
async def delete_document(
    document_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
) -> None:
    """删除文档：先删 Milvus 向量，再删 PostgreSQL 行（切块随外键级联删除）"""
    deleted = await DocumentService(db, vector_store=store).delete_document(document_id)
    if not deleted:
        raise NotFoundException(message="文档不存在")
