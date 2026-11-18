"""大模型网关异常"""

from app.exception.base import BusinessException


class LLMException(BusinessException):
    """大模型网关调用失败"""
