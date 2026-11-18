"""ORM 模型层测试

覆盖商品的增删改查、关系查询与级联删除。
数据库来自 conftest 的内存 SQLite 夹具，无需真实数据库。
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model import Category, Product, Sku
from app.model.association import product_category


async def _make_product(db_session: AsyncSession) -> Product:
    """造一个带分类和 SKU 的商品"""
    product = Product(name="iPhone 16", description="最新款智能手机")
    product.categories.extend([Category(name="数码"), Category(name="手机")])
    product.skus.append(
        Sku(
            sku_code="IP16-128-BLK",
            price=Decimal("4999.00"),
            stock=100,
            attrs={"颜色": "黑色", "存储": "128G"},
        )
    )
    product.skus.append(
        Sku(
            sku_code="IP16-256-WHT",
            price=Decimal("5999.00"),
            stock=50,
            attrs={"颜色": "白色", "存储": "256G"},
        )
    )

    db_session.add(product)
    await db_session.commit()

    return product


async def test_create_product_with_relations(db_session: AsyncSession) -> None:
    """新建商品时同时带上分类与 SKU"""
    product = await _make_product(db_session)

    assert product.id is not None
    assert len(product.categories) == 2
    assert len(product.skus) == 2


async def test_query_product_with_relations(db_session: AsyncSession) -> None:
    """查询商品时带出所属分类与 SKU 列表"""
    product = await _make_product(db_session)
    product_id = product.id

    # 清掉会话缓存，强制走一次真实的查询
    db_session.expire_all()

    loaded = await db_session.get(Product, product_id)
    assert loaded is not None
    assert loaded.name == "iPhone 16"
    assert loaded.created_at is not None
    assert {c.name for c in loaded.categories} == {"数码", "手机"}
    assert {(s.sku_code, s.price) for s in loaded.skus} == {
        ("IP16-128-BLK", Decimal("4999.00")),
        ("IP16-256-WHT", Decimal("5999.00")),
    }


async def test_update_sku_price(db_session: AsyncSession) -> None:
    """修改 SKU 价格"""
    product = await _make_product(db_session)
    sku = product.skus[0]
    sku_id = sku.id

    sku.price = Decimal("4599.00")
    await db_session.commit()
    db_session.expire_all()

    loaded = await db_session.get(Sku, sku_id)
    assert loaded is not None
    assert loaded.price == Decimal("4599.00")


async def test_delete_product_cascades_skus(db_session: AsyncSession) -> None:
    """删除商品时，其 SKU 一并删除（delete-orphan 级联）"""
    product = await _make_product(db_session)

    await db_session.delete(product)
    await db_session.commit()

    sku_count = await db_session.scalar(select(func.count()).select_from(Sku))
    assert sku_count == 0


async def test_delete_category_clears_association(db_session: AsyncSession) -> None:
    """删除分类时，中间表里与它关联的记录一并清理"""
    product = await _make_product(db_session)
    category = product.categories[0]
    category_id = category.id

    await db_session.delete(category)
    await db_session.commit()

    # 与被删分类关联的中间表记录应已消失，另一个分类的关联保持不变
    links = await db_session.execute(
        select(product_category.c.category_id).where(
            product_category.c.category_id == category_id
        )
    )
    assert links.all() == []

    total = await db_session.scalar(select(func.count()).select_from(product_category))
    assert total == 1
