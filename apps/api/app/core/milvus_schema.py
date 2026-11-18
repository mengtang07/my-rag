"""Milvus 集合定义

**刻意不 import 任何配置模块**（pydantic-settings 等）：
`docker/milvus-init` 那个轻量镜像只装了 pymilvus，靠这个特性才能 import 到
本模块并完成「建集合 + 建索引 + 加载」。

集合只存向量和主键，**不存正文** —— 正文在 PostgreSQL，检索命中后回表取。
"""

from typing import Any

from pymilvus import DataType, MilvusClient

from app.exception.vector_store import VectorStoreException

# 字段名
FIELD_PK: str = "pk"
FIELD_VECTOR: str = "vector"
FIELD_DOC_ID: str = "doc_id"
FIELD_CHUNK_INDEX: str = "chunk_index"

# 索引参数：HNSW 无需训练，个人知识库规模下召回与延迟都够用
INDEX_TYPE: str = "HNSW"
METRIC_TYPE: str = "COSINE"
HNSW_M: int = 16
HNSW_EF_CONSTRUCTION: int = 200


def build_schema(dim: int) -> Any:
    """构造集合 schema

    Args:
        dim: 向量维度，必须与 embedding 模型的实际维度一致

    Returns:
        CollectionSchema
    """
    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field(FIELD_PK, DataType.INT64, is_primary=True)
    schema.add_field(FIELD_VECTOR, DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field(FIELD_DOC_ID, DataType.INT64)
    schema.add_field(FIELD_CHUNK_INDEX, DataType.INT64)
    return schema


def build_index_params() -> Any:
    """构造索引参数（HNSW + 余弦距离）"""
    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name=FIELD_VECTOR,
        index_type=INDEX_TYPE,
        metric_type=METRIC_TYPE,
        params={"M": HNSW_M, "efConstruction": HNSW_EF_CONSTRUCTION},
    )
    return index_params


def get_collection_dim(info: dict[str, Any]) -> int | None:
    """从 `describe_collection` 的结果里取出向量字段的维度"""
    for field in info.get("fields", []):
        if field.get("name") == FIELD_VECTOR:
            params = field.get("params") or {}
            dim = params.get("dim")
            return int(dim) if dim is not None else None
    return None


def ensure_collection(client: Any, collection_name: str, dim: int) -> str:
    """幂等地确保集合存在、索引齐全、已加载到内存

    同步版本，给 `scripts/milvus_init.py` 和 `docker/milvus-init` 用。

    Args:
        client: pymilvus 的 MilvusClient
        collection_name: 集合名
        dim: 向量维度

    Returns:
        集合名

    Raises:
        VectorStoreException: 已存在的集合维度与 `dim` 不一致
    """
    if client.has_collection(collection_name):
        info = client.describe_collection(collection_name)
        existing = get_collection_dim(info)
        if existing is not None and existing != dim:
            raise VectorStoreException(
                message=(
                    f"集合 {collection_name} 的向量维度是 {existing}，"
                    f"与当前配置的 {dim} 不一致；请执行 make milvus-reset 重建集合"
                )
            )
        client.load_collection(collection_name)
        return collection_name

    client.create_collection(
        collection_name=collection_name,
        schema=build_schema(dim),
        index_params=build_index_params(),
        consistency_level="Strong",
    )
    client.load_collection(collection_name)
    return collection_name
