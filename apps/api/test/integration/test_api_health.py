"""健康检查与统一响应封装"""

from httpx import AsyncClient


async def test_health_returns_plain_structure(client: AsyncClient) -> None:
    """`/health` 刻意不带 `/api/` 前缀，因此不参与统一封装"""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_api_response_is_wrapped(client: AsyncClient) -> None:
    """`/api/` 下的 JSON 响应被包成统一信封"""
    response = await client.get("/api/conversations")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "0"
    assert body["message"] == "success"
    assert "items" in body["data"]
    assert body["data"]["total"] == 0


async def test_not_found_uses_business_error_code(client: AsyncClient) -> None:
    """资源不存在走业务错误码 404001"""
    response = await client.get("/api/documents/999")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "404001"
    assert body["data"] is None
    assert body["message"] == "文档不存在"


async def test_validation_error_uses_business_error_code(
    client: AsyncClient,
) -> None:
    """参数校验失败走 422001"""
    response = await client.post("/api/search", json={"query": ""})

    assert response.status_code == 422
    assert response.json()["code"] == "422001"
