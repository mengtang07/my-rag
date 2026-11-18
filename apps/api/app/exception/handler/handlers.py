"""全局异常处理器

一个 `exception_handler` 注册给所有异常类型，行为完全一致：
查错误码 → 转成统一信封返回。
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from loguru import logger
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.exception.base import BusinessException
from app.exception.handler.errors import ERROR_MAP, PROTOCOL_ERROR_MAP


def _lookup(exc: Exception) -> tuple[str, int, str]:
    """按 MRO 查找异常对应的错误码配置，找不到则回退到 Exception"""
    for exc_type in type(exc).__mro__:
        if exc_type in ERROR_MAP:
            return ERROR_MAP[exc_type]
    return ERROR_MAP[Exception]


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """统一的异常响应

    置 `request.state.exception_handled = True`，让统一响应中间件知道
    这个请求已经处理过了，不要再包一层信封。
    """
    request.state.exception_handled = True

    if isinstance(exc, HTTPException):
        status = exc.status_code
        message = PROTOCOL_ERROR_MAP.get(status, "请求失败")
        code = str(status)
        return JSONResponse(
            status_code=status,
            content={"code": code, "data": None, "message": message},
        )

    code, status, default_message = _lookup(exc)

    body_message = default_message
    if isinstance(exc, BusinessException):
        body_message = exc.message or default_message
        if exc.detail:
            logger.error(f"[{code}] {exc.detail}")
    elif isinstance(exc, RequestValidationError):
        logger.debug(f"参数校验失败: {exc.errors()}")
    else:
        logger.exception(f"未处理的异常: {exc!r}")

    return JSONResponse(
        status_code=status,
        content={"code": code, "data": None, "message": body_message},
    )
