"""数据库异常"""

from app.exception.base import BusinessException


class DatabaseException(BusinessException):
    """数据库操作失败"""
