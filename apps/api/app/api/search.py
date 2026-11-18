"""检索接口

只做向量召回与回表，**不调用大模型** —— 调试召回质量、前端展示来源都用它。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.llm import LiteLLMClient, get_llm_client
from app.core.vector_store import VectorStore, get_vector_store
from app.schema.search import SearchHit, SearchRequest, SearchResponse
from app.service.retrieval_service import RetrievalService

router = APIRouter(prefix="/api/search", tags=["检索"])


@router.post("", response_model=SearchResponse, summary="向量检索")
async def search(
    data: SearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LiteLLMClient, Depends(get_llm_client)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
) -> SearchResponse:
    """按问题检索最相关的知识片段"""
    hits, _, took_ms = await RetrievalService(
        db, llm=llm, vector_store=store
    ).search_with_context(
        data.query, top_k=data.top_k, document_ids=data.document_ids
    )

    return SearchResponse(
        query=data.query,
        hits=[
            SearchHit(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                document_title=hit.document_title,
                heading_path=hit.heading_path,
                page_number=hit.page_number,
                content=hit.content,
                score=round(hit.score, 4),
            )
            for hit in hits
        ],
        took_ms=round(took_ms, 2),
    )
