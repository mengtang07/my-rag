"""PostgreSQL 上的接口与数据库行为测试

SQLite 只为速度服务，下面这些行为只有真实 PostgreSQL 才能验证：

- 唯一约束（`sku_code`）
- 数据库级外键级联（`ON DELETE CASCADE`），而不是 ORM 的 delete-orphan
- `server_default`（`is_active`）
- `JSON` / `Numeric` 字段的类型往返

用例跑在事务里，结束后回滚，不会留下数据。
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.model import Category, Product, Sku
from app.model.association import product_category

pytestmark = pytest.mark.postgres


async def _create_category(session: AsyncSession, name: str = "数码") -> Category:
    category = Category(name=name)
    session.add(category)
    await session.flush()
    return category


async def _create_product(session: AsyncSession, name: str = "iPhone 16") -> Product:
    product = Product(name=name)
    session.add(product)
    await session.flush()
    return product


async def test_create_product_via_api(pg_client: AsyncClient) -> None:
    """完整链路：建分类 -> 建商品 -> 建 SKU -> 列表/详情查询"""
    category_response = await pg_client.post(
        "/api/categories", json={"name": "数码", "description": "电子产品"}
    )
    assert category_response.status_code == 201
    assert category_response.json()["code"] == "0"
    category_id = category_response.json()["data"]["id"]

    product_response = await pg_client.post(
        "/api/products",
        json={
            "name": "iPhone 16",
            "description": "最新款智能手机",
            "category_ids": [category_id],
        },
    )
    assert product_response.status_code == 201
    product_body = product_response.json()
    assert product_body["code"] == "0"
    product_id = product_body["data"]["id"]
    assert product_body["data"]["categories"] == [
        {"id": category_id, "name": "数码"}
    ]

    sku_response = await pg_client.post(
        f"/api/products/{product_id}/skus",
        json={
            "sku_code": "IP16-128-BLK",
            "price": "4999.00",
            "stock": 100,
            "attrs": {"颜色": "黑色"},
            "image_url": "https://example.com/ip16.png",
        },
    )
    assert sku_response.status_code == 201
    sku_data = sku_response.json()["data"]
    assert sku_data["sku_code"] == "IP16-128-BLK"
    assert sku_data["price"] == "4999.00"

    list_response = await pg_client.get("/api/products", params={"keyword": "iPhone"})
    assert list_response.status_code == 200
    page = list_response.json()["data"]
    assert page["total"] == 1
    assert page["items"][0]["name"] == "iPhone 16"

    detail_response = await pg_client.get(f"/api/products/{product_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert [c["name"] for c in detail["categories"]] == ["数码"]
    assert [s["sku_code"] for s in detail["skus"]] == ["IP16-128-BLK"]


async def test_duplicate_sku_code_is_rejected(pg_client: AsyncClient) -> None:
    """数据库唯一约束生效，业务层转成 422 业务错误"""
    product_response = await pg_client.post("/api/products", json={"name": "iPhone 16"})
    product_id = product_response.json()["data"]["id"]
    payload = {
        "sku_code": "DUPLICATE",
        "price": "1.00",
        "stock": 1,
        "attrs": {},
        "image_url": "https://example.com/a.png",
    }

    first = await pg_client.post(f"/api/products/{product_id}/skus", json=payload)
    assert first.status_code == 201

    second = await pg_client.post(f"/api/products/{product_id}/skus", json=payload)
    assert second.status_code == 422
    body = second.json()
    assert body["code"] == "422001"
    assert body["message"] == "SKU编码重复"
    assert body["data"] is None


async def test_delete_product_cascades_at_database_level(
    pg_session: AsyncSession,
) -> None:
    """用原生 SQL 删商品也能级联删掉 SKU 与关联记录（证明 ondelete 生效）

    ORM 删除会自己处理级联，看不出数据库约束是否写对；这里绕过 ORM。
    """
    product = await _create_product(pg_session)
    category = await _create_category(pg_session)
    pg_session.add(Sku(product_id=product.id, sku_code="IP16-1", price=Decimal("1.00")))
    await pg_session.execute(
        product_category.insert().values(
            product_id=product.id, category_id=category.id
        )
    )
    await pg_session.flush()
    product_id = product.id

    await pg_session.execute(
        text("DELETE FROM product WHERE id = :id"), {"id": product_id}
    )

    sku_count = await pg_session.scalar(
        text("SELECT count(*) FROM sku WHERE product_id = :id"), {"id": product_id}
    )
    link_count = await pg_session.scalar(
        text("SELECT count(*) FROM product_category WHERE product_id = :id"),
        {"id": product_id},
    )
    assert sku_count == 0
    assert link_count == 0


async def test_is_active_uses_server_default(pg_session: AsyncSession) -> None:
    """直接插入、不写 is_active 时由数据库默认值补上 true"""
    value = await pg_session.scalar(
        text("INSERT INTO product (name) VALUES ('bare insert') RETURNING is_active")
    )
    assert value is True


async def test_json_and_numeric_roundtrip(pg_session: AsyncSession) -> None:
    """JSON 属性和 Numeric 价格在 PostgreSQL 上原样往返"""
    product = await _create_product(pg_session)
    attrs = {"颜色": "黑色", "存储": "128G"}
    sku = Sku(
        product_id=product.id,
        sku_code="IP16-JSON",
        price=Decimal("4999.00"),
        stock=3,
        attrs=attrs,
    )
    pg_session.add(sku)
    await pg_session.flush()
    sku_id = sku.id
    pg_session.expire_all()

    loaded = await pg_session.get(Sku, sku_id)
    assert loaded is not None
    assert loaded.attrs == attrs
    assert loaded.price == Decimal("4999.00")
