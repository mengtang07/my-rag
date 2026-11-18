"""Word (docx) 解析

按 Word 的 Heading N 样式还原标题层级；表格整块保留。
"""

import io

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from rag_core.models import Block, ParsedDocument


def _style_name(paragraph: Paragraph) -> str:
    """取段落样式名；样式缺失或异常时返回空串"""
    try:
        style = paragraph.style
        if style is None:
            return ""
        return style.name or ""
    except (AttributeError, KeyError, ValueError):
        return ""


def parse_docx(data: bytes, filename: str = "") -> ParsedDocument:
    """解析 docx 文档

    Args:
        data: 文件字节
        filename: 文件名（仅用于日志，不参与解析）

    Returns:
        解析后的文档
    """
    document = Document(io.BytesIO(data))

    blocks: list[Block] = []
    heading_stack: list[str] = []
    buffer: list[str] = []
    title = ""

    def flush() -> None:
        nonlocal buffer
        content = "\n\n".join(part for part in buffer if part)
        if content:
            blocks.append(Block(text=content, heading_path=tuple(heading_stack)))
        buffer = []

    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]

        if tag == "p":
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            style_name = _style_name(paragraph)

            if style_name.startswith("Heading"):
                flush()
                level_text = style_name[len("Heading") :].strip()
                level = int(level_text) if level_text.isdigit() else 1
                if text:
                    del heading_stack[level - 1 :]
                    heading_stack.append(text)
                    if not title and level == 1:
                        title = text
                continue

            if text:
                buffer.append(text)
            continue

        if tag == "tbl":
            table = Table(child, document)
            flush()
            rows: list[str] = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append(Block(text="\n".join(rows), heading_path=tuple(heading_stack)))
            continue

    flush()

    return ParsedDocument(title=title, blocks=blocks, metadata={"source": "docx"})
