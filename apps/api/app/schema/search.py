"""检索出入参"""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """检索请求"""

    query: str = Field(min_length=1, max_length=2000, description="检索问题")
    top_k: int = Field(default=5, ge=1, le=50, description="返回条数")
    document_ids: list[int] | None = Field(
        default=None, description="限定在某些文档内检索；不填表示全库"
    )


class SearchHit(BaseModel):
    """一条检索命中"""

    chunk_id: int
    document_id: int
    document_title: str
    heading_path: str = ""
    page_number: int | None = None
    content: str
    score: float = Field(description="相似度分数，越大越相关")


class SearchResponse(BaseModel):
    """检索结果"""

    query: str
    hits: list[SearchHit]
    took_ms: float = Field(description="检索耗时（毫秒）")
