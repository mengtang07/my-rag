"""商品与分类的关联表

关联表（中间表）不由 ORM 模型映射，而是直接用 `Table` 声明，
它只负责存放多对多关系两端的外键，本身没有业务字段。
"""

from sqlalchemy import Column, ForeignKey, Table

from app.model.base import Base

# 商品与分类的多对多关联表
product_category: Table = Table(
    "product_category",
    Base.metadata,
    Column(
        "product_id",
        ForeignKey("product.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        ForeignKey("category.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
