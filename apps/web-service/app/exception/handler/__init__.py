"""异常处理器包

对外统一出口：业务代码只从这里 import，不必知道处理器/配置/文档各在哪个模块。
"""

from app.exception.handler.docs import generate_error_docs
from app.exception.handler.handlers import exception_handler

__all__ = ["exception_handler", "generate_error_docs"]
