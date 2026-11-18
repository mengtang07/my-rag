"""文件上传接口

前端直传（PostObject）流程：

1. 前端调用 `POST /api/upload/credentials` 申请上传凭证；
2. 前端用凭证向 OSS 发起 `multipart/form-data` POST，文件不经过应用服务器；
3. 需要清理文件时调用 `DELETE /api/upload/object/{key}`。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.schema.upload import (
    UploadCredentialRequest,
    UploadCredentialResponse,
    UploadObjectExistsResponse,
)
from app.service.upload_service import UploadService, get_upload_service

router = APIRouter(prefix="/api/upload", tags=["文件上传"])


@router.post(
    "/credentials",
    response_model=UploadCredentialResponse,
    summary="申请上传凭证",
)
async def create_upload_credentials(
    data: UploadCredentialRequest,
    service: Annotated[UploadService, Depends(get_upload_service)],
) -> UploadCredentialResponse:
    """签发阿里云 OSS 直传凭证"""
    credentials = service.create_credentials(data.filename, data.file_size)
    return UploadCredentialResponse(**credentials)


@router.get(
    "/object/{key:path}",
    response_model=UploadObjectExistsResponse,
    summary="查询文件是否存在",
)
async def get_upload_object(
    key: str,
    service: Annotated[UploadService, Depends(get_upload_service)],
) -> UploadObjectExistsResponse:
    """按 key 查询文件是否已上传成功"""
    exists = await service.object_exists(key)
    return UploadObjectExistsResponse(key=key, exists=exists)


@router.delete("/object/{key:path}", status_code=204, summary="删除文件")
async def delete_upload_object(
    key: str,
    service: Annotated[UploadService, Depends(get_upload_service)],
) -> None:
    """删除 OSS 中的文件"""
    await service.delete_object(key)
