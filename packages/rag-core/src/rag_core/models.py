"""RAG 领域数据结构

这几个 dataclass 是解析器、切块器与应用层之间的契约：
解析器产出 `ParsedDocument`，切块器把它变成一串 `ChunkDraft`，
应用层再把 `ChunkDraft` 落库（PostgreSQL）并向量化（Milvus）。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Block:
    """文档中的一个结构块

    Attributes:
        text: 块的正文
        heading_path: 标题层级路径，从外到内（如 ("安装", "依赖")）
        page_number: 页码（1 起）；只有 PDF 之类的分页格式才有
        char_start: 在原始纯文本中的起始字符偏移；无法确定时为 None
        char_end: 在原始纯文本中的结束字符偏移；无法确定时为 None
    """

    text: str
    heading_path: tuple[str, ...] = ()
    page_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None


@dataclass(slots=True)
class ParsedDocument:
    """一份解析后的文档

    Attributes:
        title: 文档标题；解析器拿不到时由调用方回退到文件名
        blocks: 结构块列表，顺序即原文顺序
        metadata: 解析器附带的额外信息（如 PDF 页数、docx 段落数）
    """

    title: str
    blocks: list[Block]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChunkDraft:
    """一个待入库的切块

    Attributes:
        text: 切块正文（已带 `## 标题路径` 前缀，前缀参与向量化）
        heading_path: 标题层级路径的字符串形式（用 ` > ` 连接）
        chunk_index: 在整篇文档中的序号，从 0 起
        page_number: 页码；无分页时为 None
        char_start: 在原始纯文本中的起始字符偏移
        char_end: 在原始纯文本中的结束字符偏移
        token_count: 估算的 token 数
    """

    text: str
    heading_path: str
    chunk_index: int
    page_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    token_count: int = 0
