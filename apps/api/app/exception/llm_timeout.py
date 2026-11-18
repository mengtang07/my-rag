"""大模型调用超时"""

from app.exception.llm import LLMException


class LLMTimeoutException(LLMException):
    """大模型调用超时

    继承 `LLMException`，全局处理器按 MRO 查表时会优先命中本类，
    因此超时能拿到独立的 504 状态码与错误码。
    """
