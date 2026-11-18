"""ORM 模型

导入本包即完成所有模型的注册（Alembic 生成迁移脚本时依赖这一点）。
"""

from app.model.association import product_category
from app.model.base import Base, IDMixin, TimestampMixin
from app.model.category import Category
from app.model.product import Product
from app.model.sku import Sku

__all__ = [
    "Base",
    "Category",
    "IDMixin",
    "Product",
    "Sku",
    "TimestampMixin",
    "product_category",
]
