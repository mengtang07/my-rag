"""商品规格模型（SKU）"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.model.product import Product


class Sku(Base, IDMixin, TimestampMixin):
    """商品规格表（SKU，最小库存单元）

    通过 product_id 外键归属于某件商品，与 Product 是一对多关系的“多”端。
    """

    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"),
        index=True,
    )
    # SKU 编码：唯一标识一个规格
    sku_code: Mapped[str] = mapped_column(String(50), unique=True)
    # 价格用 Numeric 存储，避免浮点数精度问题
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # 规格属性，如 {"颜色": "黑色", "存储": "128G"}
    attrs: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'")
    )
    image_url: Mapped[str] = mapped_column(
        String(500), default="", server_default=text("''")
    )

    product: Mapped[Product] = relationship(back_populates="skus")
