"""文件上传服务单元测试

用假的 uploader 替掉真实的阿里云 OSS，全程不联网：
- 凭证签发、存在性判断、删除的转发是否正确；
- 底层异常是否被翻译成业务异常；
- 配置缺失时是否给出明确提示。
"""

from typing import Any

import pytest

from app.exception import UploadException
from app.service import upload_service
from app.service.upload_service import UploadService

CREDENTIALS: dict[str, str] = {
    "host": "https://test-bucket.oss-cn-hangzhou.aliyuncs.com",
    "access_id": "test-access-key-id",
    "policy": "dGVzdA==",
    "signature": "c2lnbmF0dXJl",
    "key": "uploads/2025/06/26/a1b2c3d4e5f6.png",
    "content_type": "image/png",
}


class FakeUploader:
    """假的 uploader：只记录调用，不发网络请求"""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.deleted: list[str] = []
        self.existing: set[str] = set()

    def generate_upload_credentials(self, filename: str, file_size: int) -> dict[str, str]:
        if self.error is not None:
            raise self.error
        return dict(CREDENTIALS)

    async def exists(self, object_key: str) -> bool:
        if self.error is not None:
            raise self.error
        return object_key in self.existing

    async def delete(self, object_key: str) -> None:
        if self.error is not None:
            raise self.error
        self.deleted.append(object_key)


class TestCreateCredentials:
    def test_returns_uploader_credentials(self) -> None:
        service = UploadService(FakeUploader())  # type: ignore[arg-type]

        result = service.create_credentials("photo.png", 1024)

        assert result == CREDENTIALS

    def test_unsupported_type_becomes_business_error(self) -> None:
        uploader = FakeUploader(error=ValueError("不支持的文件类型: .xyz"))
        service = UploadService(uploader)  # type: ignore[arg-type]

        with pytest.raises(UploadException, match="不支持的文件类型"):
            service.create_credentials("file.xyz", 1024)

    def test_missing_suffix_becomes_business_error(self) -> None:
        uploader = FakeUploader(error=ValueError("无法获取文件后缀: noext"))
        service = UploadService(uploader)  # type: ignore[arg-type]

        with pytest.raises(UploadException, match="无法获取文件后缀"):
            service.create_credentials("noext", 1024)


class TestObjectExists:
    async def test_returns_true_for_existing_key(self) -> None:
        uploader = FakeUploader()
        uploader.existing.add("uploads/2025/06/26/a1b2c3d4e5f6.png")
        service = UploadService(uploader)  # type: ignore[arg-type]

        assert await service.object_exists("uploads/2025/06/26/a1b2c3d4e5f6.png") is True

    async def test_returns_false_for_missing_key(self) -> None:
        service = UploadService(FakeUploader())  # type: ignore[arg-type]

        assert await service.object_exists("uploads/2025/06/26/nope.png") is False

    async def test_backend_error_becomes_business_error(self) -> None:
        uploader = FakeUploader(error=RuntimeError("oss 连接超时"))
        service = UploadService(uploader)  # type: ignore[arg-type]

        with pytest.raises(UploadException, match="文件状态查询失败"):
            await service.object_exists("uploads/2025/06/26/a.png")


class TestDeleteObject:
    async def test_deletes_requested_key(self) -> None:
        uploader = FakeUploader()
        service = UploadService(uploader)  # type: ignore[arg-type]

        await service.delete_object("uploads/2025/06/26/a1b2c3d4e5f6.png")

        assert uploader.deleted == ["uploads/2025/06/26/a1b2c3d4e5f6.png"]

    async def test_backend_error_becomes_business_error(self) -> None:
        uploader = FakeUploader(error=RuntimeError("oss 连接超时"))
        service = UploadService(uploader)  # type: ignore[arg-type]

        with pytest.raises(UploadException, match="文件删除失败"):
            await service.delete_object("uploads/2025/06/26/a.png")


class TestBuildUploader:
    def test_missing_config_raises_business_error(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(upload_service.oss_settings, "access_key_id", "")
        monkeypatch.setattr(upload_service.oss_settings, "access_key_secret", "")
        monkeypatch.setattr(upload_service.oss_settings, "bucket_name", "")
        monkeypatch.setattr(upload_service.oss_settings, "endpoint", "")

        with pytest.raises(UploadException, match="未配置完整"):
            upload_service._build_uploader()

    def test_mime_types_are_parsed_from_csv(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(upload_service.oss_settings, "access_key_id", "ak")
        monkeypatch.setattr(upload_service.oss_settings, "access_key_secret", "sk")
        monkeypatch.setattr(upload_service.oss_settings, "bucket_name", "bucket")
        monkeypatch.setattr(upload_service.oss_settings, "endpoint", "oss-cn-hangzhou.aliyuncs.com")
        monkeypatch.setattr(upload_service.oss_settings, "mime_types", "image/png, image/jpeg")

        uploader = upload_service._build_uploader()

        assert uploader._config.mime_types == ["image/png", "image/jpeg"]

    def test_empty_mime_types_means_no_restriction(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(upload_service.oss_settings, "access_key_id", "ak")
        monkeypatch.setattr(upload_service.oss_settings, "access_key_secret", "sk")
        monkeypatch.setattr(upload_service.oss_settings, "bucket_name", "bucket")
        monkeypatch.setattr(upload_service.oss_settings, "endpoint", "oss-cn-hangzhou.aliyuncs.com")
        monkeypatch.setattr(upload_service.oss_settings, "mime_types", "")

        uploader = upload_service._build_uploader()

        assert uploader._config.mime_types is None

    def test_flat_dir_strategy_is_selectable(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(upload_service.oss_settings, "access_key_id", "ak")
        monkeypatch.setattr(upload_service.oss_settings, "access_key_secret", "sk")
        monkeypatch.setattr(upload_service.oss_settings, "bucket_name", "bucket")
        monkeypatch.setattr(upload_service.oss_settings, "endpoint", "oss-cn-hangzhou.aliyuncs.com")
        monkeypatch.setattr(upload_service.oss_settings, "dir_strategy", "flat")

        uploader = upload_service._build_uploader()

        assert uploader._config.dir_strategy() == "uploads/"
