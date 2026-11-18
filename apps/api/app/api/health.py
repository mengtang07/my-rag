"""健康检查与系统状态

`/health` 刻意不带 `/api/` 前缀，因此不参与统一响应封装，
返回的是最朴素的结构，便于探针/负载均衡直接判断。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import llm_settings, milvus_settings
from app.core.database import get_db
from app.core.vector_store import VectorStore, get_vector_store
from app.schema.system import SystemStatusResponse

router = APIRouter(tags=["健康检查"])

system_router = APIRouter(prefix="/api/system", tags=["系统"])


@router.get("/health", summary="健康检查")
async def health_check() -> dict[str, str]:
    """服务存活探测"""
    return {"status": "ok"}


@system_router.get(
    "/status", response_model=SystemStatusResponse, summary="系统就绪状态"
)
async def system_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
) -> SystemStatusResponse:
    """检查三个依赖是否就绪：PostgreSQL / Milvus / 大模型网关

    Milvus 的集合维度与配置的 embedding 维度会并排列出来，不一致一眼就能看到。
    """
    details: dict[str, Any] = {}

    # 数据库
    database_state = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        database_state = f"error: {exc}"
    details["database"] = database_state

    # 向量库
    milvus_state = "ok"
    chunk_count = 0
    try:
        await store.ensure_ready()
        chunk_count = await store.count()
    except Exception as exc:  # noqa: BLE001
        milvus_state = f"error: {exc}"
    details["milvus"] = {
        "uri": milvus_settings.uri,
        "collection": milvus_settings.collection,
        "collection_dim": milvus_settings.embed_dim,
        "vectors": chunk_count,
    }

    # 大模型网关
    details["llm"] = {
        "api_base": llm_settings.api_base,
        "chat_model": llm_settings.chat_model,
        "embed_model": llm_settings.embed_model,
        "embed_dim": milvus_settings.embed_dim,
        "api_key_configured": bool(llm_settings.api_key),
    }

    overall = "ok"
    if database_state != "ok" or not milvus_state.startswith("ok"):
        overall = "degraded"

    return SystemStatusResponse(
        status=overall,
        database=database_state,
        milvus=milvus_state,
        llm="ok" if llm_settings.api_key else "missing_api_key",
        details=details,
    )
