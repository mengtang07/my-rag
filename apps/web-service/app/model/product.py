"""商品模型（SPU）"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model.association import product_category
from app.model.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.model.category import Category
    from app.model.sku import Sku


class Product(Base, IDMixin, TimestampMixin):
    """商品表（SPU，标准产品单元）

    - 与分类是多对多关系
    - 与 SKU 是一对多关系：一件商品包含多个规格
    """

    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    # 品牌：可空，未填写时为 NULL
    brand: Mapped[str | None] = mapped_column(String(100), default=None)
    # 是否上架：server_default 让数据库侧插入（以及后续迁移回填）也有默认值
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )

    categories: Mapped[list[Category]] = relationship(
        secondary=product_category,
        back_populates="products",
        lazy="selectin",
    )
    # cascade="all, delete-orphan"：删除商品时连同其 SKU 一起删除
    skus: Mapped[list[Sku]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
