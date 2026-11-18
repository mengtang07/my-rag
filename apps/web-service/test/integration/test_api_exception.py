"""未知异常（500）处理测试

未知异常由 Starlette 的 ServerErrorMiddleware 兜底，
它位于中间件栈的最外层，因此这里单独构造一个应用来验证。
"""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.exception.handler import exception_handler


async def test_unhandled_exception_returns_500() -> None:
    """未捕获的异常返回 500 与业务错误码 500001"""
    test_app = FastAPI()
    test_app.add_exception_handler(Exception, exception_handler)

    @test_app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        response = await c.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "500001"
    assert body["message"] == "服务器内部错误"
    assert body["data"] is None
