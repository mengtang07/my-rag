"""把钉钉知识库拉成树

两步：

1. **目录树** —— 递归 `wiki/nodes`，把知识库 → 文件夹 → 文档组织起来，
   每个节点记着从根到自己的路径（面包屑）
2. **文档内标题树** —— 取文档的 blocks，按 `heading.level` 拼成层级树

块结构在钉钉那边不是完全稳定的（不同文档类型返回的字段名有出入，
`heading.level` 见过 `"2"` 也见过 `"heading-2"` 两种写法），
所以这里对字段名做了兼容处理。
"""

from collections.abc import Iterator
from typing import Any

from rag_core.dingding.client import DingTalkClient
from rag_core.dingding.exceptions import DingTalkError
from rag_core.dingding.models import (
    KIND_DOCUMENT,
    KIND_FOLDER,
    DingBlock,
    DingDocument,
    DingNode,
    DingTree,
)

# 目录树最大深度，防止知识库里有环或结构异常时无限递归
DEFAULT_MAX_DEPTH: int = 12


def parse_heading_level(value: Any) -> int | None:
    """解析标题层级

    钉钉这个字段见过两种写法：`"2"` 和 `"heading-2"`，都认。

    Args:
        value: 原始值

    Returns:
        层级（1 起）；解析不出来返回 None
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None

    text = str(value).strip().lower()
    if text.startswith("heading-"):
        text = text[len("heading-") :].strip()
    try:
        level = int(text)
    except ValueError:
        return None
    return level if level > 0 else None


def _extract_text(payload: Any) -> str:
    """从块的结构里抽出纯文本

    文档里各类型块的字段名不完全一致，按顺序试：
    `text` → 表格的 `cells` → 递归找 `text` / `content`。
    """
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return ""

    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text

    cells = payload.get("cells")
    if isinstance(cells, list):
        rows: list[str] = []
        for row in cells:
            if isinstance(row, list):
                rows.append(" | ".join(str(cell) for cell in row))
            else:
                rows.append(str(row))
        return "\n".join(row for row in rows if row)

    return _find_text(payload)


def _find_text(payload: dict[str, Any]) -> str:
    """递归找第一段文本（代码块、图片这类 `unknown` 块会走到这里）"""
    for key in ("text", "content"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value

    for key in ("textRun", "elements", "children", "paragraph", "heading"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            found = _find_text(nested)
            if found:
                return found
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    found = _find_text(item)
                    if found:
                        return found

    return ""


def parse_block(raw: dict[str, Any]) -> DingBlock:
    """把一个原始块转成 `DingBlock`"""
    block_type = str(raw.get("blockType") or "unknown")

    payload: dict[str, Any] = {}
    candidate = raw.get(block_type)
    if isinstance(candidate, dict):
        payload = candidate
    else:
        element = raw.get("element")
        if isinstance(element, dict):
            payload = element

    level: int | None = None
    if block_type == "heading":
        level = parse_heading_level(payload.get("level"))

    return DingBlock(
        block_id=str(raw.get("id") or raw.get("blockId") or ""),
        index=int(raw.get("index") or 0),
        block_type=block_type,
        text=_extract_text(payload),
        level=level,
    )


def build_block_tree(blocks: list[dict[str, Any]]) -> list[DingBlock]:
    """把扁平的块列表按标题层级拼成树

    遇到标题就压栈（关掉同层与更深的标题），普通块挂到当前标题下。
    """
    roots: list[DingBlock] = []
    stack: list[DingBlock] = []

    for raw in blocks:
        block = parse_block(raw)

        if block.block_type == "heading" and block.level is not None:
            while stack and (stack[-1].level or 0) >= block.level:
                stack.pop()
            if stack:
                stack[-1].children.append(block)
            else:
                roots.append(block)
            stack.append(block)
            continue

        if stack:
            stack[-1].children.append(block)
        else:
            roots.append(block)

    return roots


def iter_blocks(
    nodes: list[DingBlock], path: tuple[str, ...] = ()
) -> Iterator[tuple[DingBlock, tuple[str, ...]]]:
    """按文档顺序遍历块，附带它所处的标题路径

    标题自己也在产出里（路径含自己），这样切块时标题既能当上下文，
    又能当一个独立的标题块。
    """
    for node in nodes:
        if node.block_type == "heading" and node.level is not None:
            node_path = path + (node.text,)
            yield node, node_path
            yield from iter_blocks(node.children, node_path)
        else:
            yield node, path
            yield from iter_blocks(node.children, path)


def parse_node(raw: dict[str, Any], path: list[str]) -> DingNode:
    """把一个原始节点转成 `DingNode`

    wiki 接口给的是 `type`（FILE/FOLDER），企业存储接口给的是 `nodeType`，
    两种都认。
    """
    node_id = str(raw.get("nodeId") or raw.get("id") or "")
    name = str(raw.get("name") or "")

    kind_raw = str(raw.get("nodeType") or raw.get("type") or "").upper()
    is_folder = kind_raw == "FOLDER"

    content_type = str(raw.get("contentType") or raw.get("category") or "")

    # docKey：wiki 文档是 node_id；企业存储的文档是 uuid
    doc_key: str | None = None
    if not is_folder:
        doc_key = str(raw.get("uuid") or "") or node_id or None

    url = raw.get("url") or raw.get("docUrl")
    url_text = str(url) if url else None

    return DingNode(
        node_id=node_id,
        name=name,
        kind=KIND_FOLDER if is_folder else KIND_DOCUMENT,
        content_type=content_type,
        doc_key=doc_key,
        url=url_text,
        path=[*path, name] if name else list(path),
    )


class DingTalkService:
    """钉钉知识库的读取编排"""

    def __init__(self, client: DingTalkClient) -> None:
        self.client = client

    async def list_workspaces(self) -> list[dict[str, Any]]:
        """列出可见的知识库"""
        return await self.client.list_workspaces()

    async def build_tree(
        self,
        workspace_id: str | None = None,
        *,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> DingTree:
        """拉一个知识库的目录树

        Args:
            workspace_id: 知识库 id；不填取第一个
            max_depth: 最大递归深度

        Returns:
            目录树
        """
        workspaces = await self.list_workspaces()
        if not workspaces:
            raise DingTalkError(message="没有可见的钉钉知识库")

        if workspace_id:
            workspace = next(
                (
                    item
                    for item in workspaces
                    if str(item.get("workspaceId") or item.get("id") or "") == workspace_id
                ),
                None,
            )
            if workspace is None:
                raise DingTalkError(message=f"找不到知识库 {workspace_id}")
        else:
            workspace = workspaces[0]

        resolved_id = str(
            workspace.get("workspaceId") or workspace.get("id") or ""
        )
        workspace_name = str(workspace.get("name") or "")
        root_node_id = str(
            workspace.get("rootNodeId") or workspace.get("rootNode") or ""
        )

        nodes: list[DingNode] = []
        if root_node_id:
            nodes = await self._walk(root_node_id, [], 0, max_depth)

        return DingTree(
            workspace_id=resolved_id,
            workspace_name=workspace_name,
            nodes=nodes,
        )

    async def _walk(
        self,
        parent_node_id: str,
        path: list[str],
        depth: int,
        max_depth: int,
    ) -> list[DingNode]:
        """递归拉一层节点"""
        if depth > max_depth:
            return []

        raw_nodes = await self.client.list_nodes(parent_node_id)
        result: list[DingNode] = []

        for raw in raw_nodes:
            node = parse_node(raw, path)
            if node.kind == KIND_FOLDER:
                node.children = await self._walk(
                    node.node_id, node.path, depth + 1, max_depth
                )
            result.append(node)

        return result

    async def fetch_document(self, node: DingNode) -> DingDocument:
        """拉一篇文档的正文并转成标题树"""
        doc_key = node.doc_key or node.node_id
        blocks = await self.client.get_document_blocks(doc_key)

        return DingDocument(
            node_id=node.node_id,
            title=node.name,
            doc_key=doc_key,
            url=node.url,
            path=list(node.path),
            blocks=build_block_tree(blocks),
        )

    async def pull(
        self,
        workspace_id: str | None = None,
        *,
        max_depth: int = DEFAULT_MAX_DEPTH,
        skip_content: bool = False,
    ) -> tuple[DingTree, list[DingDocument]]:
        """拉整个知识库：目录树 + 所有文档正文

        Args:
            workspace_id: 知识库 id
            max_depth: 目录树最大深度
            skip_content: 只拉目录树，不取正文

        Returns:
            `(目录树, 文档列表)`
        """
        tree = await self.build_tree(workspace_id, max_depth=max_depth)
        if skip_content:
            return tree, []

        documents: list[DingDocument] = []
        for node in iter_document_nodes(tree.nodes):
            documents.append(await self.fetch_document(node))

        return tree, documents


def iter_document_nodes(nodes: list[DingNode]) -> Iterator[DingNode]:
    """按目录顺序遍历所有文档节点"""
    for node in nodes:
        if node.kind == KIND_DOCUMENT:
            yield node
        if node.children:
            yield from iter_document_nodes(node.children)
