"""健康检查与异常处理测试"""

from httpx import AsyncClient


async def test_health_check(client: AsyncClient) -> None:
    """健康检查接口不参与统一响应封装"""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_path_not_found(client: AsyncClient) -> None:
    """不存在的路径返回 404"""
    response = await client.get("/api/not-exists")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "404"
    assert body["data"] is None


async def test_method_not_allowed(client: AsyncClient) -> None:
    """不允许的请求方法返回 405"""
    response = await client.post("/health")

    assert response.status_code == 405
    body = response.json()
    assert body["code"] == "405"
