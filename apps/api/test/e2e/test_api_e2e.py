"""端到端测试：真实服务进程 + 真实 PostgreSQL + 真实 Milvus + 真实网关

重点覆盖一条链路：**上传 → 落库 → 列表可见 → 检索命中 → 删除 → 列表为空**。

其中「列表可见」这一步是**回归防线**：老框架的 `get_db()` 从不提交事务，
写接口的数据实际会回滚 —— 而进程内的集成测试用同一个内存 session，
根本看不出这个问题，只有真起进程 + 真数据库才暴露得出来。
"""

import httpx
import pytest

MARKDOWN = """# 部署手册

## 前置条件

需要 Docker 29 以上版本与 8GB 内存。

## 安装步骤

执行 `docker compose up -d` 启动依赖服务。
"""


async def test_full_document_lifecycle(
    async_client: httpx.AsyncClient, clean_database: None
) -> None:
    """上传 → 落库 → 列表可见 → 检索命中 → 删除 → 列表为空"""
    # 1) 上传
    response = await async_client.post(
        "/api/documents",
        files={"file": ("部署手册.md", MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    document_id = data["document_id"]
    assert data["status"] == "ready"
    assert data["chunk_count"] >= 1

    # 2) 列表可见 —— 这一步验证数据真的提交进数据库了
    listing = await async_client.get("/api/documents")
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1
    assert listing.json()["data"]["items"][0]["id"] == document_id

    # 3) 详情与切块
    detail = await async_client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "部署手册"

    chunks = await async_client.get(f"/api/documents/{document_id}/chunks")
    assert chunks.json()["data"]["total"] >= 1

    # 4) 检索命中
    search = await async_client.post(
        "/api/search", json={"query": "部署需要什么前置条件", "top_k": 3}
    )
    assert search.status_code == 200
    hits = search.json()["data"]["hits"]
    assert len(hits) >= 1
    assert hits[0]["document_title"] == "部署手册"

    # 5) 删除
    deleted = await async_client.delete(f"/api/documents/{document_id}")
    assert deleted.status_code == 204

    # 6) 列表空了
    listing = await async_client.get("/api/documents")
    assert listing.json()["data"]["total"] == 0


async def test_chat_stream_end_to_end(
    async_client: httpx.AsyncClient, clean_database: None
) -> None:
    """流式问答：先推来源，再推增量，最后收尾"""
    await async_client.post(
        "/api/documents",
        files={"file": ("部署手册.md", MARKDOWN.encode("utf-8"), "text/markdown")},
    )

    async with async_client.stream(
        "POST", "/api/chat/stream", json={"question": "部署需要什么前置条件？"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: sources" in body
    assert "event: token" in body
    assert "event: done" in body
    # SSE 不能被统一信封包住
    assert not body.lstrip().startswith('{"code"')


async def test_system_status_reports_dependencies(
    async_client: httpx.AsyncClient, clean_database: None
) -> None:
    """系统状态接口会报告三个依赖的情况"""
    response = await async_client.get("/api/system/status")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["database"] == "ok"
    assert "collection_dim" in data["details"]["milvus"]
