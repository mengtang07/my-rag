"""关联表（中间表）包

多对多关系需要一张中间表来存放两端的外键，
统一放在本包中，与业务模型分离开来。
"""

from app.model.association.product_category import product_category

__all__ = ["product_category"]
