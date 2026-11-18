"""请求耗时中间件

统计每个请求在服务端消耗的时间，并写入响应头 `X-Process-Time`。

- 单位：毫秒（保留 2 位小数）
- 取值范围：`0.01` ~ `99999.99`

客户端（浏览器 / 移动端 / 网关）可以直接从响应头里读到这次请求的服务端耗时，
不需要额外的接口。
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import Response

# 响应头名称（跨域时需要在 CORS 的 expose_headers 里放行）
PROCESS_TIME_HEADER: str = "X-Process-Time"


async def process_time(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """统计请求耗时并写入响应头"""
    # perf_counter 是单调时钟，不受系统时间调整影响，适合测量时长
    start = time.perf_counter()

    response = await call_next(request)

    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers[PROCESS_TIME_HEADER] = str(round(elapsed_ms, 2))
    return response


MIDDLEWARE: tuple[Callable[..., Any], dict[str, Any]] = (process_time, {})
