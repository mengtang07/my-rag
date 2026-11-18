"""Schema 校验层测试（同步用例）

这里的用例都是普通的 `def`：不碰数据库、不需要事件循环，pytest 直接同步执行。
它们和 `test_model_orm.py` 里的异步用例共用 `asyncio_mode = "auto"` 这一套配置，
两者互不干扰。
"""

import pytest
from pydantic import ValidationError

from app.schema.category import CategoryCreate
from app.schema.product import ProductCreate, ProductUpdate


def test_product_create_defaults() -> None:
    """只传必填字段，其余走默认值"""
    product = ProductCreate(name="iPhone 16")

    assert product.description == ""
    assert product.brand is None
    assert product.category_ids == []


def test_product_create_with_all_fields() -> None:
    """字段传全时原样保留"""
    product = ProductCreate(
        name="iPhone 16",
        description="最新款智能手机",
        brand="Apple",
        category_ids=[1, 2],
    )

    assert product.name == "iPhone 16"
    assert product.description == "最新款智能手机"
    assert product.brand == "Apple"
    assert product.category_ids == [1, 2]


def test_product_create_rejects_empty_name() -> None:
    """名称为空，违反 min_length 约束"""
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(name="")

    assert exc_info.value.errors()[0]["type"] == "string_too_short"


def test_product_create_rejects_too_long_name() -> None:
    """名称超过 200 字，违反 max_length 约束"""
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(name="x" * 201)

    assert exc_info.value.errors()[0]["type"] == "string_too_long"


def test_product_update_all_fields_optional() -> None:
    """更新接口的所有字段都可省略"""
    update = ProductUpdate()

    assert update.name is None
    assert update.description is None
    assert update.brand is None
    assert update.category_ids is None


def test_category_create_defaults() -> None:
    """分类描述默认空串"""
    category = CategoryCreate(name="数码")

    assert category.name == "数码"
    assert category.description == ""
