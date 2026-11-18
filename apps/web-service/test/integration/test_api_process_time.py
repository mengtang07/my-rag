"""请求耗时中间件测试"""

from httpx import AsyncClient


async def test_process_time_header_present(client: AsyncClient) -> None:
    """响应里带上 X-Process-Time 头"""
    response = await client.get("/health")

    assert response.status_code == 200
    assert "X-Process-Time" in response.headers


async def test_process_time_is_valid_number(client: AsyncClient) -> None:
    """X-Process-Time 是毫秒数（浮点秒 × 1000，保留 2 位小数）"""
    response = await client.get("/api/products")

    assert response.status_code == 200
    elapsed = float(response.headers["X-Process-Time"])
    assert elapsed >= 0


async def test_process_time_present_on_error_response(client: AsyncClient) -> None:
    """错误响应同样带上耗时头"""
    response = await client.get("/api/products/999999")

    assert response.status_code == 404
    assert "X-Process-Time" in response.headers
