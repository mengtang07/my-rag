"""Milvus 集合与向量读写（真实 Milvus）"""

import uuid

import pytest

from app.core.milvus_schema import (
    FIELD_CHUNK_INDEX,
    FIELD_DOC_ID,
    FIELD_PK,
    FIELD_VECTOR,
    ensure_collection,
)
from app.core.vector_store import VectorStore

pytestmark = pytest.mark.milvus

DIM: int = 8


@pytest.fixture
def collection_name() -> str:
    """用带后缀的测试集合名，避免污染开发集合"""
    return f"test_chunks_{uuid.uuid4().hex[:8]}"


async def test_ensure_collection_is_idempotent(
    milvus_available: bool, collection_name: str
) -> None:
    """建集合可以反复执行，不会报错"""
    store = VectorStore()
    store.collection = collection_name
    store.embed_dim = DIM

    await store.ensure_ready()
    await store.ensure_ready()  # 再来一次也不能炸

    assert await store.client.has_collection(collection_name)
    await store.drop()
    await store.close()


async def test_upsert_and_search_roundtrip(
    milvus_available: bool, collection_name: str
) -> None:
    """写入向量后能检索回来"""
    store = VectorStore()
    store.collection = collection_name
    store.embed_dim = DIM

    await store.ensure_ready()
    try:
        vector = [0.1] * DIM
        await store.upsert_chunks(
            [
                {
                    FIELD_PK: 1,
                    FIELD_VECTOR: vector,
                    FIELD_DOC_ID: 10,
                    FIELD_CHUNK_INDEX: 0,
                }
            ]
        )

        hits = await store.search(vector, top_k=5)
        assert len(hits) == 1
        assert hits[0].chunk_id == 1
        assert hits[0].document_id == 10
        assert hits[0].score > 0.99
    finally:
        await store.drop()
        await store.close()


async def test_delete_by_document(
    milvus_available: bool, collection_name: str
) -> None:
    """按文档 id 删除向量"""
    store = VectorStore()
    store.collection = collection_name
    store.embed_dim = DIM

    await store.ensure_ready()
    try:
        await store.upsert_chunks(
            [
                {
                    FIELD_PK: index,
                    FIELD_VECTOR: [0.1] * DIM,
                    FIELD_DOC_ID: 10,
                    FIELD_CHUNK_INDEX: index,
                }
                for index in (1, 2, 3)
            ]
        )
        assert await store.count() == 3

        await store.delete_document(10)
        assert await store.count() == 0
    finally:
        await store.drop()
        await store.close()
