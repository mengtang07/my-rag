"""文件上传业务逻辑

采用「前端直传」模式：应用只负责签发阿里云 OSS 的 PostObject 上传凭证，
文件由浏览器直接发到 OSS，不经过应用服务器，因此不受应用带宽限制。

凭证的具体签发逻辑在 `packages/duyi-utils` 的 `AliyunOSSUploader` 里，
本模块负责把配置翻译成 uploader，并把底层异常翻译成业务异常。
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from duyi_utils.upload.aliyun import AliyunOSSConfig, AliyunOSSUploader
from duyi_utils.upload.dir_strategy import date_uuid_strategy, flat_uuid_strategy

from app.core.config import oss_settings
from app.exception import UploadException


class UploadService:
    """文件上传服务"""

    def __init__(self, uploader: AliyunOSSUploader) -> None:
        self._uploader = uploader

    def create_credentials(self, filename: str, file_size: int) -> dict[str, str]:
        """签发前端直传凭证

        Args:
            filename: 原始文件名，后缀决定 MIME 类型。
            file_size: 文件大小（字节），写进凭证的 content-length-range 限制。

        Returns:
            上传凭证字典，字段见 `UploadCredentialResponse`。

        Raises:
            UploadException: 后缀拿不到、类型不支持，或类型不在白名单内。
        """
        try:
            return self._uploader.generate_upload_credentials(filename, file_size)
        except ValueError as exc:
            # duyi-utils 用 ValueError 表示「取不到后缀 / 类型不支持 / 类型不在白名单」
            raise UploadException(message=str(exc)) from exc

    async def object_exists(self, key: str) -> bool:
        """判断文件是否存在于 OSS

        Raises:
            UploadException: 查询失败。
        """
        try:
            return await self._uploader.exists(key)
        except Exception as exc:
            raise UploadException(
                message="文件状态查询失败",
                detail=str(exc),
                original_exception=exc,
            ) from exc

    async def delete_object(self, key: str) -> None:
        """删除 OSS 中的文件

        Raises:
            UploadException: 删除失败。
        """
        try:
            await self._uploader.delete(key)
        except Exception as exc:
            raise UploadException(
                message="文件删除失败",
                detail=str(exc),
                original_exception=exc,
            ) from exc


def _dir_strategy(name: str) -> Callable[[str], str]:
    """按配置名挑一个目录策略：date（按日期分层）/ flat（扁平）"""
    if name.strip().lower() == "flat":
        return flat_uuid_strategy
    return date_uuid_strategy


def _build_uploader() -> AliyunOSSUploader:
    """按配置构造 uploader

    Raises:
        UploadException: OSS 配置不完整。
    """
    required = {
        "OSS_ACCESS_KEY_ID": oss_settings.access_key_id,
        "OSS_ACCESS_KEY_SECRET": oss_settings.access_key_secret,
        "OSS_BUCKET_NAME": oss_settings.bucket_name,
        "OSS_ENDPOINT": oss_settings.endpoint,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise UploadException(
            message="阿里云 OSS 未配置完整，无法上传文件",
            detail=f"缺少配置项：{', '.join(missing)}",
        )

    mime_types = [item.strip() for item in oss_settings.mime_types.split(",") if item.strip()]

    config = AliyunOSSConfig(
        access_key_id=oss_settings.access_key_id,
        access_key_secret=oss_settings.access_key_secret,
        bucket_name=oss_settings.bucket_name,
        endpoint=oss_settings.endpoint,
        expire_seconds=oss_settings.expire_seconds,
        mime_types=mime_types or None,
        dir_strategy=_dir_strategy(oss_settings.dir_strategy),
    )
    return AliyunOSSUploader(config)


@lru_cache(maxsize=1)
def get_upload_service() -> UploadService:
    """FastAPI 依赖：获取上传服务（进程内复用同一个 uploader）"""
    return UploadService(_build_uploader())
