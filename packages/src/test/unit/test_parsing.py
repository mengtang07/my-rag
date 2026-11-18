"""文档解析测试"""

import pytest

from rag_core.parsing import UnsupportedFormatError, detect_parser
from rag_core.parsing.html import parse_html
from rag_core.parsing.markdown import parse_markdown
from rag_core.parsing.text import parse_text

MARKDOWN = """# 部署手册

## 前置条件

需要 Docker 29 以上版本。

## 安装步骤

执行 `docker compose up -d` 启动依赖服务。

### 数据库

用 `make db-init` 初始化。
""".encode()


def test_detect_parser_rejects_unknown_suffix() -> None:
    """不支持的格式抛 UnsupportedFormatError"""
    with pytest.raises(UnsupportedFormatError):
        detect_parser("archive.zip")


def test_detect_parser_by_suffix() -> None:
    """按后缀选解析器"""
    assert detect_parser("a.md") is parse_markdown
    assert detect_parser("a.MD") is parse_markdown
    assert detect_parser("a.txt") is parse_text


def test_markdown_heading_path() -> None:
    """markdown 还原标题层级"""
    parsed = parse_markdown(MARKDOWN, "部署手册.md")

    assert parsed.title == "部署手册"
    paths = {block.heading_path for block in parsed.blocks}
    # 二级标题嵌在一级标题下，路径是完整层级
    assert ("部署手册", "前置条件") in paths
    assert ("部署手册", "安装步骤") in paths
    assert ("部署手册", "安装步骤", "数据库") in paths


def test_markdown_title_falls_back_to_empty() -> None:
    """没有一级标题时标题为空"""
    parsed = parse_markdown("## 只有二级标题\n\n正文。".encode(), "x.md")
    assert parsed.title == ""


def test_html_heading_path() -> None:
    """html 还原标题层级，丢弃 script"""
    html = (
        "<html><head><title>页面</title>"
        "<script>var x=1;</script></head><body>"
        "<h1>主标题</h1><p>正文一</p>"
        "<h2>子标题</h2><p>正文二</p>"
        "</body></html>"
    ).encode()
    parsed = parse_html(html, "a.html")

    assert parsed.title == "页面"
    paths = {block.heading_path for block in parsed.blocks}
    assert ("主标题",) in paths
    assert ("主标题", "子标题") in paths
    assert all("var x" not in block.text for block in parsed.blocks)


def test_text_parser_blocks_and_offsets() -> None:
    """纯文本按空行分段，并记录字符偏移"""
    parsed = parse_text("第一段\n\n第二段".encode(), "a.txt")

    assert len(parsed.blocks) == 2
    assert parsed.blocks[0].text == "第一段"
    assert parsed.blocks[0].char_start == 0
    assert parsed.blocks[1].char_start is not None
    assert parsed.blocks[1].char_start > 0


def test_text_parser_handles_gbk() -> None:
    """非 utf-8 的编码不会炸"""
    parsed = parse_text("中文内容".encode("gb18030"), "a.txt")
    assert parsed.blocks[0].text == "中文内容"
