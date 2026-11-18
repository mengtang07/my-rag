"""钉钉知识库接入

对外暴露：

- `DingTalkClient` —— 开放平台接口的异步客户端（鉴权 / 知识库 / 节点 / 正文）
- `DingTalkService` —— 把知识库拉成两层树（目录树 + 文档内标题树）
- `DingNode` / `DingBlock` / `DingDocument` / `DingTree` —— 树结构模型
- `DingTalkError` —— 异常

只用 httpx + pydantic，不依赖 FastAPI / SQLAlchemy。
"""

from rag_core.dingding.client import DingTalkClient
from rag_core.dingding.exceptions import DingTalkError
from rag_core.dingding.models import (
    KIND_DOCUMENT,
    KIND_FOLDER,
    KIND_WORKSPACE,
    DingBlock,
    DingDocument,
    DingNode,
    DingTree,
)
from rag_core.dingding.tree import (
    DingTalkService,
    build_block_tree,
    iter_blocks,
    iter_document_nodes,
    parse_block,
    parse_heading_level,
    parse_node,
)

__all__ = [
    "KIND_DOCUMENT",
    "KIND_FOLDER",
    "KIND_WORKSPACE",
    "DingBlock",
    "DingDocument",
    "DingNode",
    "DingTalkClient",
    "DingTalkError",
    "DingTalkService",
    "DingTree",
    "build_block_tree",
    "iter_blocks",
    "iter_document_nodes",
    "parse_block",
    "parse_heading_level",
    "parse_node",
]
