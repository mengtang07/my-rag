"""文件上传接口测试

用假的 UploadService 替掉真实的上传服务，不连阿里云 OSS：
- 凭证接口返回统一响应结构；
- 参数校验失败走 422001；
- 业务异常（类型不支持、OSS 未配置）走 422002；
- 查询与删除接口按 key 定位文件。
"""

from typing import Any

import pytest
from httpx import AsyncClient

from app.exception import UploadException
from app.main import app
from app.service import upload_service
from app.service.upload_service import get_upload_service

CREDENTIALS: dict[str, str] = {
    "host": "https://test-bucket.oss-cn-hangzhou.aliyuncs.com",
    "access_id": "test-access-key-id",
    "policy": "dGVzdA==",
    "signature": "c2lnbmF0dXJl",
    "key": "uploads/2025/06/26/a1b2c3d4e5f6.png",
    "content_type": "image/png",
}


class StubUploadService:
    """假的上传服务：只记录调用，不发网络请求"""

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.deleted: list[str] = []
        self.existing: set[str] = set()

    def create_credentials(self, filename: str, file_size: int) -> dict[str, str]:
        if self.error is not None:
            raise self.error
        return dict(CREDENTIALS)

    async def object_exists(self, key: str) -> bool:
        return key in self.existing

    async def delete_object(self, key: str) -> None:
        self.deleted.append(key)


@pytest.fixture
def stub_service() -> Any:
    """用假的上传服务替换掉真实的依赖"""
    stub = StubUploadService()
    app.dependency_overrides[get_upload_service] = lambda: stub
    try:
        yield stub
    finally:
        app.dependency_overrides.pop(get_upload_service, None)


async def test_create_credentials_returns_unified_response(
    client: AsyncClient, stub_service: StubUploadService
) -> None:
    """申请凭证返回统一结构，业务数据在 data 里"""
    response = await client.post(
        "/api/upload/credentials", json={"filename": "photo.png", "file_size": 1024}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "0"
    assert body["message"] == "success"
    assert body["data"] == CREDENTIALS


async def test_create_credentials_validates_payload(
    client: AsyncClient, stub_service: StubUploadService
) -> None:
    """参数缺失/非法走 422001"""
    response = await client.post("/api/upload/credentials", json={"filename": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "422001"
    assert body["data"] is None
    assert "body.filename" in body["message"]


async def test_create_credentials_rejects_non_positive_size(
    client: AsyncClient, stub_service: StubUploadService
) -> None:
    """文件大小必须为正数"""
    response = await client.post(
        "/api/upload/credentials", json={"filename": "photo.png", "file_size": 0}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "422001"


async def test_unsupported_type_returns_business_error(
    client: AsyncClient, stub_service: StubUploadService
) -> None:
    """业务异常走 422002，错误信息透出"""
    stub_service.error = UploadException(message="不支持的文件类型: .xyz")

    response = await client.post(
        "/api/upload/credentials", json={"filename": "file.xyz", "file_size": 1024}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "422002"
    assert body["message"] == "不支持的文件类型: .xyz"
    assert body["data"] is None


async def test_oss_not_configured_returns_business_error(
    client: AsyncClient, monkeypatch: Any
) -> None:
    """OSS 没配置时给出明确提示，而不是 500"""
    monkeypatch.setattr(upload_service.oss_settings, "access_key_id", "")
    monkeypatch.setattr(upload_service.oss_settings, "access_key_secret", "")
    monkeypatch.setattr(upload_service.oss_settings, "bucket_name", "")
    monkeypatch.setattr(upload_service.oss_settings, "endpoint", "")
    upload_service.get_upload_service.cache_clear()

    response = await client.post(
        "/api/upload/credentials", json={"filename": "photo.png", "file_size": 1024}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "422002"
    assert "未配置完整" in body["message"]


async def test_check_object_exists(
    client: AsyncClient, stub_service: StubUploadService
) -> None:
    """按 key 查询文件是否存在，路径里的斜杠不会被截断"""
    stub_service.existing.add("uploads/2025/06/26/a1b2c3d4e5f6.png")

    response = await client.get("/api/upload/object/uploads/2025/06/26/a1b2c3d4e5f6.png")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "0"
    assert body["data"] == {"key": "uploads/2025/06/26/a1b2c3d4e5f6.png", "exists": True}


async def test_check_object_not_exists(
    client: AsyncClient, stub_service: StubUploadService
) -> None:
    """文件不存在时 exists 为 false"""
    response = await client.get("/api/upload/object/uploads/2025/06/26/nope.png")

    assert response.status_code == 200
    assert response.json()["data"]["exists"] is False


async def test_delete_object(
    client: AsyncClient, stub_service: StubUploadService
) -> None:
    """删除文件返回 204，且 key 原样传给上传服务"""
    response = await client.delete("/api/upload/object/uploads/2025/06/26/a1b2c3d4e5f6.png")

    assert response.status_code == 204
    assert stub_service.deleted == ["uploads/2025/06/26/a1b2c3d4e5f6.png"]
