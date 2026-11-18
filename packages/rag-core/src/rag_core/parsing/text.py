"""纯文本解析（.txt / .log）

纯文本没有结构，按空行分段，每段就是一个块。
"""

from rag_core.models import Block, ParsedDocument
from rag_core.parsing.base import decode, normalize


def parse_text(data: bytes, filename: str = "") -> ParsedDocument:
    """解析纯文本

    Args:
        data: 文件字节
        filename: 文件名（仅用于日志，不参与解析）

    Returns:
        解析后的文档
    """
    text = normalize(decode(data))

    blocks: list[Block] = []
    offset = 0
    for part in text.split("\n\n"):
        stripped = part.strip()
        if not stripped:
            offset += len(part) + 2
            continue

        start = text.find(part, offset)
        end = start + len(part) if start >= 0 else None
        blocks.append(
            Block(
                text=stripped,
                char_start=start if start >= 0 else None,
                char_end=end,
            )
        )
        offset = (end if end is not None else offset) + 2

    title = ""
    if blocks:
        title = blocks[0].text.splitlines()[0][:200]

    return ParsedDocument(title=title, blocks=blocks, metadata={"source": "text"})
