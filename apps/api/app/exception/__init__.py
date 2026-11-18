"""业务异常定义

对外统一出口：业务代码只从这里 import。
"""

from app.exception.base import BusinessException
from app.exception.database import DatabaseException
from app.exception.dingtalk import DingTalkException
from app.exception.llm import LLMException
from app.exception.llm_timeout import LLMTimeoutException
from app.exception.not_found import NotFoundException
from app.exception.parse import ParseException
from app.exception.vector_store import VectorStoreException

__all__ = [
    "BusinessException",
    "DatabaseException",
    "DingTalkException",
    "LLMException",
    "LLMTimeoutException",
    "NotFoundException",
    "ParseException",
    "VectorStoreException",
]
