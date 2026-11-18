"""资源不存在"""

from app.exception.base import BusinessException


class NotFoundException(BusinessException):
    """资源不存在"""
