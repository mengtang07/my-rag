"""文档解析异常"""

from app.exception.base import BusinessException


class ParseException(BusinessException):
    """文档解析失败（格式不支持、内容损坏等）"""
