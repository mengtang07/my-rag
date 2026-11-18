"""Markdown 解析

用 markdown-it-py 走一遍 token 流，维护标题栈，得到「标题层级 → 正文」的映射。
标题路径会随切块一起入库，回答时就能精确引用到「第几节」。
"""

import re

from markdown_it import MarkdownIt

from rag_core.models import Block, ParsedDocument
from rag_core.parsing.base import decode, normalize

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    """去掉 HTML 标签，保留文字"""
    return _TAG_RE.sub(" ", text)


def parse_markdown(data: bytes, filename: str = "") -> ParsedDocument:
    """解析 Markdown 文档

    Args:
        data: 文件字节
        filename: 文件名（仅用于日志，不参与解析）

    Returns:
        解析后的文档；`title` 取第一个一级标题，没有则为空
    """
    text = normalize(decode(data))
    tokens = MarkdownIt("commonmark").parse(text)

    blocks: list[Block] = []
    heading_stack: list[str] = []
    buffer: list[str] = []
    title = ""

    def flush() -> None:
        """把缓冲区里的正文落成一个块（标题路径取当前标题栈）"""
        nonlocal buffer
        content = "\n\n".join(part.strip() for part in buffer if part.strip())
        if content:
            blocks.append(Block(text=content, heading_path=tuple(heading_stack)))
        buffer = []

    pending_level: int | None = None

    for token in tokens:
        if token.type == "heading_open":
            # 遇到新标题：先把上一段正文结算掉（此时标题栈还是上一节的）
            flush()
            level_text = token.tag[1:] if token.tag else ""
            pending_level = int(level_text) if level_text.isdigit() else 1
            continue

        if token.type == "inline":
            if pending_level is not None:
                heading = token.content.strip()
                if heading:
                    # 截断到本级之前，再压入本级标题 —— 维护正确的层级嵌套
                    del heading_stack[pending_level - 1 :]
                    heading_stack.append(heading)
                    if not title and pending_level == 1:
                        title = heading
                pending_level = None
            else:
                buffer.append(token.content)
            continue

        if token.type in ("fence", "code_block"):
            # 代码块整体作为一个块，避免被段落切分开
            flush()
            buffer.append(token.content)
            continue

        if token.type == "html_block":
            flush()
            buffer.append(_strip_tags(token.content))
            continue

    flush()

    return ParsedDocument(title=title, blocks=blocks, metadata={"source": "markdown"})
