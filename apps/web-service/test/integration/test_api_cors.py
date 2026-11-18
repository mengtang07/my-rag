"""跨域中间件测试"""

from httpx import AsyncClient


async def test_cors_simple_request(client: AsyncClient) -> None:
    """带 Origin 的普通请求返回跨域响应头"""
    response = await client.get("/health", headers={"Origin": "http://example.com"})

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    # 前端要能读到耗时头，必须在 expose_headers 里放行
    assert "X-Process-Time" in response.headers["Access-Control-Expose-Headers"]


async def test_cors_preflight_request(client: AsyncClient) -> None:
    """预检请求由中间件直接响应，不进入路由"""
    response = await client.options(
        "/api/products",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert "POST" in response.headers["Access-Control-Allow-Methods"]


async def test_cors_headers_on_api_response(client: AsyncClient) -> None:
    """业务接口的响应也带跨域头"""
    response = await client.get(
        "/api/products", headers={"Origin": "http://example.com"}
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "*"
