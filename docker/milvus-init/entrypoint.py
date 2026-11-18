"""Milvus 集合初始化容器入口

这个镜像里**只装了 pymilvus**，没有 pydantic-settings 等项目依赖，
所以配置全部从环境变量直接读，不 import 任何配置模块。

`app.core.milvus_schema` 刻意不依赖配置模块，就是为了能被本脚本 import 到。
"""

import os
import sys
import time

from pymilvus import MilvusClient

# 源码挂载在 /src，/src/app 是 python 包（/app 留给镜像里的本脚本）
sys.path.insert(0, "/src")

from app.core.milvus_schema import ensure_collection  # noqa: E402

URI: str = os.environ.get("MILVUS_URI", "http://milvus:19530")
COLLECTION: str = os.environ.get("MILVUS_COLLECTION", "rag_chunks")
DIM: int = int(os.environ.get("MILVUS_EMBED_DIM", "1024"))
TOKEN: str = os.environ.get("MILVUS_TOKEN", "")


def main() -> int:
    """建集合 + 建索引 + 加载，幂等"""
    kwargs: dict[str, object] = {"uri": URI}
    if TOKEN:
        kwargs["token"] = TOKEN

    client = MilvusClient(**kwargs)  # type: ignore[arg-type]
    try:
        # Milvus 刚起来时可能还没完全就绪，重试几次
        last_error: Exception | None = None
        for attempt in range(10):
            try:
                ensure_collection(client, COLLECTION, DIM)
                print(f"[milvus-init] 集合 {COLLECTION} 就绪（dim={DIM}）")
                return 0
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                print(f"[milvus-init] 第 {attempt + 1} 次尝试失败：{exc}")
                time.sleep(3)

        print(f"[milvus-init] 初始化失败：{last_error}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
