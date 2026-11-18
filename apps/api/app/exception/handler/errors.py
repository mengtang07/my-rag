"""错误码表

异常类型 → (错误码, HTTP 状态码, 默认提示)。
全局处理器按异常 MRO 逐级查找，因此子类条目会优先于父类命中
（例如 `LLMTimeoutException` 继承 `LLMException`，超时能拿到独立的 504）。
"""

from fastapi.exceptions import RequestValidationError

from app.exception.database import DatabaseException
from app.exception.llm import LLMException
from app.exception.llm_timeout import LLMTimeoutException
from app.exception.not_found import NotFoundException
from app.exception.parse import ParseException
from app.exception.vector_store import VectorStoreException
from rag_core.dingding.exceptions import DingTalkError

ERROR_MAP: dict[type, tuple[str, int, str]] = {
    RequestValidationError: ("422001", 422, "数据验证错误"),
    DatabaseException: ("422001", 422, "数据验证错误"),
    ParseException: ("422002", 422, "文档解析失败"),
    DingTalkError: ("422003", 422, "钉钉知识库调用失败"),
    NotFoundException: ("404001", 404, "资源不存在"),
    LLMTimeoutException: ("500003", 504, "大模型调用超时"),
    LLMException: ("500002", 502, "大模型服务异常"),
    VectorStoreException: ("500006", 500, "向量库异常"),
    Exception: ("500001", 500, "服务器内部错误"),
}

# 协议层错误（Starlette 自带异常）→ 提示文案
PROTOCOL_ERROR_MAP: dict[int, str] = {
    404: "路径不存在",
    405: "请求方法不允许",
    415: "不支持的媒体类型",
}
