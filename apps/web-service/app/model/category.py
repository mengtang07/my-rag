"""分类模型"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model.association import product_category
from app.model.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.model.product import Product


class Category(Base, IDMixin, TimestampMixin):
    """商品分类表

    与商品是多对多关系：一件商品可以属于多个分类，一个分类下也可以有多件商品。
    """

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))

    # secondary 指向关联表，back_populates 与 Product.categories 配对
    products: Mapped[list[Product]] = relationship(
        secondary=product_category,
        back_populates="categories",
        lazy="selectin",
    )
