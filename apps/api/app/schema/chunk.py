"""切块出入参"""

from pydantic import BaseModel, Field


class ChunkBrief(BaseModel):
    """切块"""

    id: int
    document_id: int
    chunk_index: int
    content: str
    heading_path: str = Field(default="", description="标题层级路径，如 `安装 > 依赖`")
    page_number: int | None = Field(default=None, description="页码（1 起）")
    token_count: int = 0

    model_config = {"from_attributes": True}
