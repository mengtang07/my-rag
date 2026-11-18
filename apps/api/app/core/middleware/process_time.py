"""耗时统计中间件"""

import time
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

PROCESS_TIME_HEADER: str = "X-Process-Time"


async def process_time(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """在响应头里带上处理耗时（毫秒）"""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    response.headers[PROCESS_TIME_HEADER] = f"{elapsed:.2f}"
    return response


MIDDLEWARE: tuple[Callable[..., object], dict[str, object]] = (process_time, {})
