"""基础设施层

这个包**刻意保持零 import**：`docker/milvus-init` 那个只装了 pymilvus 的轻量镜像
要能 import 到 `app.core.milvus_schema`，靠的就是这里不做任何连带导入。
"""
