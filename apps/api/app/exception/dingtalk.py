"""钉钉开放平台异常"""

from app.exception.base import BusinessException


class DingTalkException(BusinessException):
    """钉钉接口调用失败"""
