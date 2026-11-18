from pydantic import BaseModel, Field


class UploadCredentialRequest(BaseModel):
    """申请上传凭证的入参"""

    filename: str = Field(
        min_length=1, max_length=255, description="原始文件名，例如 photo.png"
    )
    file_size: int = Field(
        gt=0, description="文件大小（字节），会写进凭证的 content-length-range 限制"
    )


class UploadCredentialResponse(BaseModel):
    """阿里云 OSS PostObject 直传凭证

    前端拿到这些字段后，用 `multipart/form-data` 直接 POST 到 `host`：
    表单字段依次为 `OSSAccessKeyId` / `policy` / `signature` / `key` /
    `Content-Type`，文件本身放在 `file` 字段里。
    """

    host: str = Field(description="OSS Bucket 域名，表单 POST 的目标地址")
    access_id: str = Field(description="OSSAccessKeyId 表单字段")
    policy: str = Field(description="Base64 编码的上传策略")
    signature: str = Field(description="上传策略的签名")
    key: str = Field(description="文件在 OSS 中的完整路径")
    content_type: str = Field(description="文件 MIME 类型")


class UploadObjectExistsResponse(BaseModel):
    """文件是否存在"""

    key: str = Field(description="文件在 OSS 中的完整路径")
    exists: bool = Field(description="文件是否存在")
