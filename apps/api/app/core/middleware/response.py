"""统一响应封装

只包装 `/api/` 开头、`application/json` 的响应；SSE 端点必须豁免
（它有自己的一套事件协议，被包一层就废了）。
"""

import json
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SUCCESS_CODE: str = "0"
SUCCESS_MESSAGE: str = "success"
DEFAULT_ERROR_MESSAGE: str = "请求失败"

API_PREFIX: str = "/api/"

# 无响应体的状态码
NO_BODY_STATUS: frozenset[int] = frozenset(range(100, 200)) | {204, 304}

# 明确豁免统一封装的路径。
# 不只依赖 content-type 判断（那是隐式的），SSE 端点显式列出来，双保险。
EXEMPT_PATHS: frozenset[str] = frozenset({"/api/chat/stream"})

# 已经是信封的字段
ENVELOPE_KEYS: frozenset[str] = frozenset({"code", "data", "message"})


def _is_json_response(response: Response) -> bool:
    """判断响应是不是 JSON"""
    content_type = response.headers.get("content-type", "")
    return content_type.startswith("application/json")


async def _read_body(response: Response) -> bytes:
    """把响应体读出来（流式响应需要逐块收集）"""
    body_iterator = getattr(response, "body_iterator", None)
    if body_iterator is None:
        return getattr(response, "body", b"") or b""

    chunks: list[bytes] = []
    async for chunk in body_iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else str(chunk).encode())
    return b"".join(chunks)


async def unified_response(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """把 `/api/` 下的 JSON 响应包装成统一结构"""
    response = await call_next(request)

    if not request.url.path.startswith(API_PREFIX):
        return response
    if request.method == "HEAD":
        return response
    if request.url.path in EXEMPT_PATHS:
        return response
    if getattr(request.state, "exception_handled", False):
        return response
    if response.status_code in NO_BODY_STATUS:
        return response
    if not _is_json_response(response):
        return response

    body = await _read_body(response)
    if not body:
        return response

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return response

    # 已经是信封就别再包一层
    if isinstance(payload, dict) and ENVELOPE_KEYS.issubset(payload.keys()):
        return response

    headers = dict(response.headers)
    headers.pop("content-length", None)

    return JSONResponse(
        content={"code": SUCCESS_CODE, "data": payload, "message": SUCCESS_MESSAGE},
        status_code=response.status_code,
        headers=headers,
    )


MIDDLEWARE: tuple[Callable[..., object], dict[str, object]] = (unified_response, {})
