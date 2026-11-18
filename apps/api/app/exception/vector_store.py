"""向量库异常"""

from app.exception.base import BusinessException


class VectorStoreException(BusinessException):
    """Milvus 向量库操作失败"""
