"""业务逻辑基类"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.schema.base import PageResult

__all__ = ["BaseService", "PageResult"]


class BaseService:
    """业务逻辑基类，所有 Service 继承此类，共享 session"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
