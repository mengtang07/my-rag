"""统一响应与参数校验测试（不需要真实数据库）

补齐之前只验证了状态码、没验证响应体的部分：
- 成功响应是否包成 `{code, data, message}`
- 参数校验失败是否走统一错误结构
- 数据库约束类业务异常是否映射成 422
"""

from httpx import AsyncClient


async def test_success_response_is_wrapped(client: AsyncClient) -> None:
    """成功响应统一包装：code=0，业务数据在 data 里"""
    response = await client.get("/api/products")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "0"
    assert body["message"] == "success"
    assert body["data"] == {"items": [], "total": 0, "page": 1, "page_size": 20}


async def test_validation_error_returns_unified_body(client: AsyncClient) -> None:
    """请求体校验失败返回 422 + 422001，错误信息是统一结构"""
    response = await client.post("/api/products", json={"name": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "422001"
    assert body["data"] is None
    assert "body.name" in body["message"]


async def test_query_validation_error(client: AsyncClient) -> None:
    """查询参数越界同样返回 422 统一结构"""
    response = await client.get("/api/products", params={"page": 0})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "422001"
    assert "query.page" in body["message"]


async def test_missing_relation_becomes_business_error(client: AsyncClient) -> None:
    """关联的分类不存在时，数据库约束冲突被转成 422 业务错误"""
    response = await client.post(
        "/api/products", json={"name": "iPhone 16", "category_ids": [999999]}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "422001"
    assert body["message"] == "关联的分类不存在"
    assert body["data"] is None
