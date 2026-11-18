"""Milvus 集合管理

用法：
    python apps/api/scripts/milvus_init.py            # 幂等建集合 + 建索引 + 加载
    python apps/api/scripts/milvus_init.py --status   # 查看集合状态
    python apps/api/scripts/milvus_init.py --reset    # 删集合并按当前维度重建
    python apps/api/scripts/milvus_init.py --drop     # 只删集合
"""

import argparse
import sys
from pathlib import Path

from loguru import logger
from pymilvus import MilvusClient

WEB_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_SERVICE_DIR))

from app.core.config import milvus_settings  # noqa: E402
from app.core.milvus_schema import (  # noqa: E402
    FIELD_DOC_ID,
    FIELD_PK,
    FIELD_VECTOR,
    ensure_collection,
    get_collection_dim,
)


def build_client() -> MilvusClient:
    """按配置创建同步客户端"""
    kwargs: dict[str, object] = {
        "uri": milvus_settings.uri,
        "timeout": milvus_settings.timeout,
    }
    if milvus_settings.token:
        kwargs["token"] = milvus_settings.token
    return MilvusClient(**kwargs)  # type: ignore[arg-type]


def show_status(client: MilvusClient) -> None:
    """打印集合状态"""
    name = milvus_settings.collection
    if not client.has_collection(name):
        print(f"集合 {name} 不存在")
        return

    info = client.describe_collection(name)
    dim = get_collection_dim(info)
    # 用主键过滤统计条数：Milvus 不支持对向量字段做 is not null 判断
    rows = client.query(collection_name=name, filter=f"{FIELD_PK} >= 0")
    print(f"集合：{name}")
    print(f"  向量维度：{dim}（配置值 {milvus_settings.embed_dim}）")
    print(f"  字段：{[field.get('name') for field in info.get('fields', [])]}")
    print(f"  向量条数：{len(rows)}")
    if dim is not None and dim != milvus_settings.embed_dim:
        print("  ⚠️ 维度与配置不一致，需要执行 make milvus-reset")


def main() -> None:
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Milvus 集合管理")
    parser.add_argument("--status", action="store_true", help="查看集合状态")
    parser.add_argument("--reset", action="store_true", help="删集合并按当前维度重建")
    parser.add_argument("--drop", action="store_true", help="只删集合")
    args = parser.parse_args()

    client = build_client()

    try:
        if args.drop:
            if client.has_collection(milvus_settings.collection):
                client.drop_collection(milvus_settings.collection)
                logger.info(f"集合 {milvus_settings.collection} 已删除")
            return

        if args.reset:
            if client.has_collection(milvus_settings.collection):
                client.drop_collection(milvus_settings.collection)
                logger.info("旧集合已删除")
            ensure_collection(client, milvus_settings.collection, milvus_settings.embed_dim)
            logger.info("集合已按当前维度重建")
            show_status(client)
            return

        if args.status:
            show_status(client)
            return

        ensure_collection(client, milvus_settings.collection, milvus_settings.embed_dim)
        logger.info(f"集合 {milvus_settings.collection} 就绪")
        show_status(client)
    finally:
        client.close()


if __name__ == "__main__":
    main()
