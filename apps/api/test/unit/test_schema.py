"""出入参校验测试"""

import pytest
from pydantic import ValidationError

from app.schema.base import PageResult
from app.schema.chat import ChatRequest, Citation
from app.schema.document import DocumentTextCreate
from app.schema.search import SearchRequest


def test_document_text_create_requires_content() -> None:
    """内容不能为空"""
    with pytest.raises(ValidationError):
        DocumentTextCreate(title="标题", content="")


def test_document_text_create_length_limit() -> None:
    """标题有长度上限"""
    with pytest.raises(ValidationError):
        DocumentTextCreate(title="x" * 301, content="内容")


def test_search_request_top_k_bounds() -> None:
    """top_k 必须在 1~50 之间"""
    assert SearchRequest(query="问题", top_k=10).top_k == 10
    with pytest.raises(ValidationError):
        SearchRequest(query="问题", top_k=0)
    with pytest.raises(ValidationError):
        SearchRequest(query="问题", top_k=51)


def test_chat_request_requires_question() -> None:
    """问题不能为空"""
    with pytest.raises(ValidationError):
        ChatRequest(question="")


def test_page_result_is_generic() -> None:
    """分页结果支持泛型"""
    page = PageResult[Citation](items=[], total=0, page=1, page_size=20)
    assert page.items == []
    assert page.page_size == 20


def test_citation_defaults() -> None:
    """引用的默认字段"""
    citation = Citation(
        index=1, chunk_id=2, document_id=3, document_title="部署手册"
    )
    assert citation.heading_path == ""
    assert citation.page_number is None
    assert citation.score == 0.0
