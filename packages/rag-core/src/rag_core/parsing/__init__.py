"""文档解析：按格式分派到具体解析器

对外只暴露 `detect_parser`，调用方不需要关心具体格式。
"""

from rag_core.parsing.base import (
    SUPPORTED_SUFFIXES,
    ParserFunc,
    UnsupportedFormatError,
    decode,
    detect_parser,
    get_suffix,
    normalize,
)

__all__ = [
    "SUPPORTED_SUFFIXES",
    "ParserFunc",
    "UnsupportedFormatError",
    "decode",
    "detect_parser",
    "get_suffix",
    "normalize",
]
