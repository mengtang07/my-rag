"""Milvus 向量库封装

用异步客户端（`AsyncMilvusClient`），避免同步 RPC 阻塞事件循环。
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from loguru import logger
from pymilvus import AsyncMilvusClient, DataType, MilvusClient

from app.core.config import milvus_settings
from app.core.milvus_schema import (
    FIELD_CHUNK_INDEX,
    FIELD_DOC_ID,
    FIELD_PK,
    FIELD_VECTOR,
    build_index_params,
    build_schema,
    get_collection_dim,
)
from app.exception.vector_store import VectorStoreException


@dataclass(slots=True)
class VectorHit:
    """一条向量检索命中

    Attributes:
        chunk_id: 命中的切块 id（= PostgreSQL 里 `chunk.id`）
        score: 相似度分数
        document_id: 所属文档 id
        chunk_index: 文档内序号
    """

    chunk_id: int
    score: float
    document_id: int
    chunk_index: int


class VectorStore:
    """Milvus 集合的读写封装"""

    def __init__(self) -> None:
        self.collection: str = milvus_settings.collection
        self.embed_dim: int = milvus_settings.embed_dim
        self.search_ef: int = milvus_settings.search_ef
        self.batch_size: int = milvus_settings.batch_size
        self._client: AsyncMilvusClient | None = None

    @property
    def client(self) -> AsyncMilvusClient:
        """获取客户端（懒加载单例）"""
        if self._client is None:
            kwargs: dict[str, Any] = {
                "uri": milvus_settings.uri,
                "timeout": milvus_settings.timeout,
            }
            if milvus_settings.token:
                kwargs["token"] = milvus_settings.token
            self._client = AsyncMilvusClient(**kwargs)
        return self._client

    async def ensure_ready(self) -> None:
        """幂等确保集合存在、索引齐全、已加载

        集合已存在但维度对不上时**明确报错**，不静默重建 ——
        静默重建会把用户已有的向量全部丢掉。
        """
        client = self.client

        if await client.has_collection(self.collection):
            info = await client.describe_collection(self.collection)
            existing = get_collection_dim(info)
            if existing is not None and existing != self.embed_dim:
                raise VectorStoreException(
                    message=(
                        f"集合 {self.collection} 的向量维度是 {existing}，"
                        f"与当前配置的 {self.embed_dim} 不一致；"
                        "请执行 make milvus-reset 重建集合"
                    )
                )
            await client.load_collection(self.collection)
            return

        await client.create_collection(
            collection_name=self.collection,
            schema=build_schema(self.embed_dim),
            index_params=build_index_params(),
            consistency_level="Strong",
        )
        await client.load_collection(self.collection)
        logger.info(f"Milvus 集合已创建：{self.collection}（dim={self.embed_dim}）")

    async def upsert_chunks(
        self, rows: list[dict[str, Any]]
    ) -> int:
        """写入（或覆盖）向量

        Args:
            rows: 每项包含 `pk` / `vector` / `doc_id` / `chunk_index`

        Returns:
            写入的条数
        """
        if not rows:
            return 0

        for start in range(0, len(rows), self.batch_size):
            batch = rows[start : start + self.batch_size]
            await self.client.upsert(collection_name=self.collection, data=batch)

        return len(rows)

    async def search(
        self,
        vector: list[float],
        *,
        top_k: int,
        document_ids: list[int] | None = None,
    ) -> list[VectorHit]:
        """向量检索

        Args:
            vector: 查询向量
            top_k: 返回条数
            document_ids: 限定在某些文档内检索；None 表示不限定

        Returns:
            命中列表，按相似度降序
        """
        filters = ""
        if document_ids:
            filters = f"{FIELD_DOC_ID} in {document_ids}"

        results = await self.client.search(
            collection_name=self.collection,
            data=[vector],
            filter=filters,
            limit=top_k,
            output_fields=[FIELD_DOC_ID, FIELD_CHUNK_INDEX],
            search_params={
                "metric_type": "COSINE",
                "params": {"ef": self.search_ef},
            },
        )

        hits: list[VectorHit] = []
        for item in results[0] if results else []:
            entity = item.get("entity", {}) or {}
            # 主键字段名是自定义的 `pk`（不是 Milvus 默认的 `id`），
            # 命中结果里的键就用这个名字
            chunk_id = item.get(FIELD_PK, item.get("id"))
            if chunk_id is None:
                continue
            hits.append(
                VectorHit(
                    chunk_id=int(chunk_id),
                    score=float(item.get("distance", 0.0)),
                    document_id=int(entity.get(FIELD_DOC_ID, 0)),
                    chunk_index=int(entity.get(FIELD_CHUNK_INDEX, 0)),
                )
            )
        return hits

    async def delete_document(self, document_id: int) -> None:
        """删除某个文档的全部向量"""
        await self.client.delete(
            collection_name=self.collection,
            filter=f"{FIELD_DOC_ID} == {document_id}",
        )

    async def delete_chunks(self, chunk_ids: list[int]) -> None:
        """按切块 id 删除向量"""
        if not chunk_ids:
            return
        await self.client.delete(
            collection_name=self.collection,
            ids=list(chunk_ids),
        )

    async def count(self) -> int:
        """统计集合里的向量条数"""
        rows = await self.client.query(
            collection_name=self.collection,
            filter=f"{FIELD_PK} >= 0",
            output_fields=["count(*)"],
        )
        if not rows:
            return 0
        return int(rows[0].get("count(*)", 0))

    async def drop(self) -> None:
        """删除整个集合"""
        if await self.client.has_collection(self.collection):
            await self.client.drop_collection(self.collection)
            logger.info(f"Milvus 集合已删除：{self.collection}")

    async def close(self) -> None:
        """关闭连接"""
        if self._client is not None:
            await self._client.close()
            self._client = None


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    """FastAPI 依赖：获取向量库封装（进程内复用同一个客户端）"""
    return VectorStore()
