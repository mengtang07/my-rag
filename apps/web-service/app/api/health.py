"""健康检查接口

路径刻意不带 `/api/` 前缀，因此不参与统一响应封装，
返回的是最朴素的结构，便于探针/负载均衡直接判断。
"""

from fastapi import APIRouter

router = APIRouter(tags=["健康检查"])


@router.get("/health", summary="健康检查")
async def health_check() -> dict[str, str]:
    """服务存活探测"""
    return {"status": "ok"}
