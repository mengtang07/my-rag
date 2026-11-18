"""PDF 解析

PDF 一般没有标题层级，退化成「按页切块」，引用时给页码。
"""

import pymupdf

from rag_core.models import Block, ParsedDocument
from rag_core.parsing.base import normalize


def parse_pdf(data: bytes, filename: str = "") -> ParsedDocument:
    """解析 PDF 文档

    Args:
        data: 文件字节
        filename: 文件名（仅用于日志，不参与解析）

    Returns:
        解析后的文档；每一页是一个块，`page_number` 从 1 开始
    """
    document = pymupdf.open(stream=data, filetype="pdf")

    blocks: list[Block] = []
    title = ""
    page_count = 0

    try:
        metadata = document.metadata or {}
        title = str(metadata.get("title") or "").strip()

        for index in range(document.page_count):
            page = document[index]
            page_count = index + 1
            text = normalize(page.get_text("text"))
            if text:
                blocks.append(Block(text=text, page_number=page_count))
    finally:
        document.close()

    return ParsedDocument(
        title=title,
        blocks=blocks,
        metadata={"source": "pdf", "page_count": page_count},
    )
