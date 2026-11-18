"""HTML 解析

递归走一遍 DOM：h1~h6 推进标题栈，块级标签作为正文边界。
"""

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from rag_core.models import Block, ParsedDocument
from rag_core.parsing.base import decode

_HEADING_RE = re.compile(r"h[1-6]")

# 这些标签的内容视为独立段落
_BLOCK_TAGS = frozenset(
    {
        "p",
        "li",
        "td",
        "th",
        "tr",
        "pre",
        "blockquote",
        "dd",
        "dt",
        "figcaption",
        "div",
        "section",
        "article",
        "main",
        "header",
        "footer",
        "br",
        "hr",
    }
)

# 这些标签的内容直接丢弃
_SKIP_TAGS = frozenset({"script", "style", "noscript", "template", "svg", "iframe"})


def parse_html(data: bytes, filename: str = "") -> ParsedDocument:
    """解析 HTML 文档

    Args:
        data: 文件字节
        filename: 文件名（仅用于日志，不参与解析）

    Returns:
        解析后的文档；`title` 取 `<title>` 标签
    """
    soup = BeautifulSoup(decode(data), "html.parser")

    title = ""
    if soup.title is not None:
        title = soup.title.get_text(strip=True)

    blocks: list[Block] = []
    heading_stack: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = "\n\n".join(part.strip() for part in buffer if part.strip())
        if content:
            blocks.append(Block(text=content, heading_path=tuple(heading_stack)))
        buffer = []

    def walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    buffer.append(text)
                continue

            if not isinstance(child, Tag):
                continue

            name = (child.name or "").lower()
            if name in _SKIP_TAGS:
                continue

            if _HEADING_RE.fullmatch(name):
                flush()
                level = int(name[1])
                heading = child.get_text(" ", strip=True)
                if heading:
                    del heading_stack[level - 1 :]
                    heading_stack.append(heading)
                continue

            if name in _BLOCK_TAGS:
                flush()
                walk(child)
                flush()
                continue

            walk(child)

    root = soup.body or soup
    walk(root)
    flush()

    return ParsedDocument(title=title, blocks=blocks, metadata={"source": "html"})
