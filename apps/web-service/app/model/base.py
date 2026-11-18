"""ORM 基类"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """所有模型的基类，统一表名规则为类名的小写"""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


class IDMixin:
    """自增主键"""

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


class TimestampMixin:
    """创建时间与更新时间"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
