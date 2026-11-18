"""解析基础设施：编码兜底、文本归一化、格式分派

解析器统一签名：`func(data: bytes, filename: str) -> ParsedDocument`。
"""

import re
from collections.abc import Callable
from pathlib import PurePosixPath

from rag_core.models import ParsedDocument

ParserFunc = Callable[[bytes, str], ParsedDocument]

# 支持的文件后缀 → 展示用的格式名
SUPPORTED_SUFFIXES: dict[str, str] = {
    "md": "markdown",
    "markdown": "markdown",
    "txt": "text",
    "log": "text",
    "pdf": "pdf",
    "docx": "docx",
    "html": "html",
    "htm": "html",
}


class UnsupportedFormatError(ValueError):
    """不支持的文件格式

    应用层会把它翻译成业务异常 `ParseException`。
    """


def decode(data: bytes) -> str:
    """按 utf-8 解码，失败时依次退到 gb18030 / latin-1

    Args:
        data: 原始字节

    Returns:
        解码后的文本
    """
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def normalize(text: str) -> str:
    """归一化换行符、空字节与连续空行

    Args:
        text: 原始文本

    Returns:
        归一化后的文本（首尾空白已去除）
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_suffix(filename: str) -> str:
    """取文件后缀（小写，不含点号）

    Args:
        filename: 文件名或路径

    Returns:
        后缀名；没有后缀时返回空字符串

    Examples:
        >>> get_suffix("a/b/部署手册.MD")
        'md'
    """
    return PurePosixPath(filename).suffix.lower().lstrip(".")


def detect_parser(filename: str) -> ParserFunc:
    """按文件名后缀选择解析器

    具体的解析模块在这里**惰性导入**，避免 markdown-it / pymupdf / python-docx
    在不需要时也被加载。

    Args:
        filename: 文件名或路径

    Returns:
        解析函数

    Raises:
        UnsupportedFormatError: 后缀不在支持列表里
    """
    suffix = get_suffix(filename)

    if suffix not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise UnsupportedFormatError(
            f"暂不支持的文件格式：{suffix or '(无后缀)'}；当前支持：{supported}"
        )

    if suffix in ("md", "markdown"):
        from rag_core.parsing.markdown import parse_markdown

        return parse_markdown

    if suffix == "pdf":
        from rag_core.parsing.pdf import parse_pdf

        return parse_pdf

    if suffix == "docx":
        from rag_core.parsing.docx import parse_docx

        return parse_docx

    if suffix in ("html", "htm"):
        from rag_core.parsing.html import parse_html

        return parse_html

    from rag_core.parsing.text import parse_text

    return parse_text
