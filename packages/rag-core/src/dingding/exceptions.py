"""钉钉开放平台异常"""


class DingTalkError(Exception):
    """钉钉接口调用失败

    刻意跟应用层的 `BusinessException` 保持同样的字段形状
    （`message` / `detail` / `original_exception`），
    这样应用的全局异常处理器可以统一处理，而本包不必依赖 FastAPI。

    Attributes:
        message: 对外暴露的信息
        detail: 对内详细信息，供日志排查
        original_exception: 原始异常实例
    """

    def __init__(
        self,
        message: str,
        *,
        detail: str = "",
        original_exception: Exception | None = None,
    ):
        self.message = message
        self.detail = detail
        self.original_exception = original_exception
        super().__init__(message)
