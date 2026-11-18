"""统一响应结构中间件

把 `/api/` 开头的接口响应统一包装成：

```json
{"code": "0", "data": <业务数据>, "message": "success"}
```

错误响应统一成：

```json
{"code": "<错误码>", "data": null, "message": "<错误信息>"}
```

以下场景原样返回，不做包装：

- 非 `/api/` 路径（`/docs`、`/openapi.json`、`/health` 等）
- `HEAD` 请求（语义上无响应体）
- 异常处理器已经处理过的请求（`request.state.exception_handled`）
- 无响应体的状态码（1xx、204、304）
- 非 JSON 响应（文件下载、流式响应）
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

# 成功响应的固定字段
SUCCESS_CODE: str = "0"
SUCCESS_MESSAGE: str = "success"

# 无响应体的状态码：1xx、204、304
NO_BODY_STATUS: frozenset[int] = frozenset(range(100, 200)) | {204, 304}

# 错误响应兜底文案
DEFAULT_ERROR_MESSAGE: str = "请求失败"


def _is_json_response(response: Response) -> bool:
    """判断响应是否是 JSON（文件下载、流式响应等原样返回）"""
    return response.headers.get("content-type", "").startswith("application/json")


def _format_validation_error(errors: list[Any]) -> str:
    """把 Pydantic 的校验错误格式化成可读文本"""
    lines: list[str] = []
    for err in errors:
        if not isinstance(err, dict):
            continue
        loc = ".".join(str(p) for p in err.get("loc", []))
        msg = str(err.get("msg", "参数不合法"))
        lines.append(f"{loc}: {msg}" if loc else msg)
    return "\n".join(lines)


def _extract_error_message(payload: Any) -> str:
    """从 FastAPI 默认错误响应体里提取可读文案

    FastAPI 的默认错误响应形如 `{"detail": "商品不存在"}`，
    参数校验错误则是 `{"detail": [{"loc": [...], "msg": "..."}]}`。
    """
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            return _format_validation_error(detail)
    return DEFAULT_ERROR_MESSAGE


async def unified_response(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """把接口响应统一成 {code, data, message} 结构"""
    response = await call_next(request)

    # 非 /api/ 路径不参与统一封装
    if not request.url.path.startswith("/api/"):
        return response

    # HEAD 请求语义上无响应体
    if request.method == "HEAD":
        return response

    # 异常处理器已经生成过统一结构，原样返回，避免二次封装
    if getattr(request.state, "exception_handled", False):
        return response

    # 无响应体的状态码（1xx、204、304），包装了也会被协议层丢弃
    if response.status_code in NO_BODY_STATUS:
        return response

    # 非 JSON 响应（文件下载、流式响应）保持原样
    if not _is_json_response(response):
        return response

    # 取出响应体（必须消费掉，否则原响应无法发送）
    body_iterator = getattr(response, "body_iterator", None)
    if body_iterator is None:
        return response

    body: bytes = b""
    async for chunk in body_iterator:
        body += chunk

    headers = dict(response.headers)
    headers.pop("content-length", None)

    try:
        payload: Any = json.loads(body) if body else None
    except json.JSONDecodeError:
        payload = None

    if response.status_code >= 400:
        # 错误响应：错误码用 HTTP 状态码，业务数据置空
        code = str(response.status_code)
        message = _extract_error_message(payload)
        data = None
    else:
        code = SUCCESS_CODE
        message = SUCCESS_MESSAGE
        data = payload

    return JSONResponse(
        content={"code": code, "data": data, "message": message},
        status_code=response.status_code,
        headers=headers,
    )


MIDDLEWARE: tuple[Callable[..., Any], dict[str, Any]] = (unified_response, {})
