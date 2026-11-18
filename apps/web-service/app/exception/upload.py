"""文件上传异常"""

from app.exception.base import BusinessException


class UploadException(BusinessException):
    """文件上传业务异常

    典型场景：OSS 未配置完整、不支持的文件类型、删除的文件不存在。
    """

    pass
