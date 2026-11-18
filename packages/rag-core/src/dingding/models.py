"""钉钉知识库的结构模型

两层树：

- **目录树**：`DingNode` —— 知识库 → 文件夹 → 文档
- **文档内标题树**：`DingBlock` —— blocks 按标题层级拼成的树

`DingNode.path` 记着从知识库根到自己的祖先名，切块时可以直接当面包屑用。
"""

from pydantic import BaseModel, Field

# 节点种类
KIND_WORKSPACE = "workspace"
KIND_FOLDER = "folder"
KIND_DOCUMENT = "document"


class DingNode(BaseModel):
    """知识库目录树里的一个节点

    Attributes:
        node_id: 钉钉节点 id
        name: 节点名称
        kind: `folder` / `document`
        content_type: 文件类型，`ALIDOC`（在线文档）/ `DOCUMENT`（本地文件）/ 空
        doc_key: 取正文用的 key。wiki 接口里等于 node_id，存储接口里是 uuid
        url: 在钉钉里的访问地址
        path: 从知识库根到自己的祖先名（含自己）
        children: 子节点
    """

    node_id: str
    name: str
    kind: str
    content_type: str = ""
    doc_key: str | None = None
    url: str | None = None
    path: list[str] = Field(default_factory=list)
    children: list["DingNode"] = Field(default_factory=list)


class DingBlock(BaseModel):
    """文档正文里的一个块

    Attributes:
        block_id: 块 id
        index: 在文档中的顺序
        block_type: `heading` / `paragraph` / `unorderedList` / `orderedList` / `table` / `blockquote` / `unknown`
        text: 抽出来的纯文本
        level: 标题层级（1 起）；非标题为 None
        children: 子块
    """

    block_id: str
    index: int
    block_type: str
    text: str = ""
    level: int | None = None
    children: list["DingBlock"] = Field(default_factory=list)


class DingDocument(BaseModel):
    """一篇钉钉文档（目录树节点 + 正文标题树）"""

    node_id: str
    title: str
    doc_key: str | None = None
    url: str | None = None
    path: list[str] = Field(default_factory=list)
    blocks: list[DingBlock] = Field(default_factory=list)


class DingTree(BaseModel):
    """一个知识库的目录树"""

    workspace_id: str
    workspace_name: str
    nodes: list[DingNode] = Field(default_factory=list)


DingNode.model_rebuild()
DingBlock.model_rebuild()
