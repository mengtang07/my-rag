"""系统状态出参"""

from typing import Any

from pydantic import BaseModel, Field


class SystemStatusResponse(BaseModel):
    """系统就绪状态

    三个依赖（PostgreSQL / Milvus / 大模型网关）任一不通都会在这里暴露出来。
    """

    status: str = Field(description="overall: ok / degraded")
    database: str = Field(description="数据库连通情况")
    milvus: str = Field(description="向量库连通情况")
    llm: str = Field(description="大模型网关配置情况")
    details: dict[str, Any] = Field(default_factory=dict)
