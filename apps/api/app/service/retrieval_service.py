"""检索：向量化 → Milvus 召回 → 回表取正文 → 组装上下文"""

import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import rag_settings
from app.core.llm import LiteLLMClient, get_llm_client
from app.core.vector_store import VectorStore, get_vector_store
from app.model.chunk import Chunk
from app.model.document import Document
from app.service.base import BaseService
from rag_core.text.estimate import estimate_tokens

# 召回时多取一些候选，留给可选的重排环节筛选
CANDIDATE_FACTOR: int = 2


@dataclass(slots=True)
class RetrievedChunk:
    """一条检索命中的完整信息（含正文与文档标题）"""

    chunk_id: int
    document_id: int
    document_title: str
    heading_path: str
    page_number: int | None
    content: str
    score: float


class RetrievalService(BaseService):
    """向量检索与上下文组装"""

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

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        document_ids: list[int] | None = None,
    ) -> list[RetrievedChunk]:
        """向量检索

        正文只存在 PostgreSQL 里，所以流程是「Milvus 召回主键 → 回表取正文」。

        Args:
            query: 用户问题
            top_k: 返回条数
            document_ids: 限定在某些文档内检索

        Returns:
            命中列表，按相似度降序
        """
        limit = top_k or rag_settings.top_k

        vectors = await self.llm.embed_texts([query])
        if not vectors:
            return []

        candidates = await self.vector_store.search(
            vectors[0],
            top_k=limit * CANDIDATE_FACTOR,
            document_ids=document_ids,
        )
        if not candidates:
            return []

        rows = await self.db.execute(
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.id.in_([hit.chunk_id for hit in candidates]))
        )
        mapping = {chunk.id: (chunk, document) for chunk, document in rows.all()}

        results: list[RetrievedChunk] = []
        for hit in candidates:
            pair = mapping.get(hit.chunk_id)
            if pair is None:
                # 孤儿向量：Milvus 里有、PG 里已经没有（文档删过或 PG 回滚过）
                continue
            chunk, document = pair
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_title=document.title,
                    heading_path=chunk.heading_path,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    score=hit.score,
                )
            )

        if rag_settings.use_rerank and len(results) > limit:
            results = await self._rerank(query, results, limit)

        return results[:limit]

    async def _rerank(
        self, query: str, results: list[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]:
        """用网关的重排模型给候选片段重新排序"""
        try:
            ranked = await self.llm.rerank(
                query, [item.content for item in results], limit
            )
        except Exception:  # noqa: BLE001 - 重排失败就退回原顺序，不该让检索整体失败
            return results

        reranked: list[RetrievedChunk] = []
        for index, score in ranked:
            if 0 <= index < len(results):
                item = results[index]
                item.score = score
                reranked.append(item)
        return reranked

    async def build_context(
        self, hits: list[RetrievedChunk], *, max_tokens: int | None = None
    ) -> tuple[str, list[RetrievedChunk]]:
        """把命中片段拼成上下文

        Args:
            hits: 命中列表（已按分数降序）
            max_tokens: 上下文的 token 上限

        Returns:
            `(上下文文本, 实际用到的片段)`
        """
        budget = max_tokens or rag_settings.max_context_tokens

        blocks: list[str] = []
        used: list[RetrievedChunk] = []
        total = 0

        for index, hit in enumerate(hits, start=1):
            source = hit.document_title
            if hit.heading_path:
                source += f" / {hit.heading_path}"
            if hit.page_number:
                source += f" / 第 {hit.page_number} 页"

            block = f"[{index}] (来源：{source})\n{hit.content}"
            tokens = estimate_tokens(block)

            # 至少保留一条：哪怕超预算也别让模型啥也看不到
            if used and total + tokens > budget:
                break

            blocks.append(block)
            used.append(hit)
            total += tokens

        return "\n\n".join(blocks), used

    async def search_with_context(
        self,
        query: str,
        *,
        top_k: int | None = None,
        document_ids: list[int] | None = None,
    ) -> tuple[list[RetrievedChunk], str, float]:
        """检索 + 组装上下文，返回命中、上下文与耗时"""
        start = time.perf_counter()
        hits = await self.search(query, top_k=top_k, document_ids=document_ids)
        context, _ = await self.build_context(hits)
        took_ms = (time.perf_counter() - start) * 1000
        return hits, context, took_ms
