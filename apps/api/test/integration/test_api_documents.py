"""文档入库 → 检索 → 删除 全链路"""

from httpx import AsyncClient

from test.fakes import FakeVectorStore

MARKDOWN = """# 部署手册

## 前置条件

需要 Docker 29 以上版本与 8GB 内存。

## 安装步骤

执行 `docker compose up -d` 启动依赖服务。

### 数据库初始化

用 `make db-init` 初始化数据库。
"""


async def test_ingest_document_creates_chunks_and_vectors(
    client: AsyncClient, fake_vector_store: FakeVectorStore
) -> None:
    """上传文档会切块、落库、写向量"""
    response = await client.post(
        "/api/documents",
        files={"file": ("部署手册.md", MARKDOWN.encode("utf-8"), "text/markdown")},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "ready"
    assert data["chunk_count"] >= 1
    assert data["reused"] is False

    # 向量确实写进去了，条数与切块数一致
    assert len(fake_vector_store.rows) == data["chunk_count"]


async def test_ingest_same_content_is_idempotent(
    client: AsyncClient, fake_vector_store: FakeVectorStore
) -> None:
    """相同内容重复摄入是幂等的"""
    payload = {"file": ("部署手册.md", MARKDOWN.encode("utf-8"), "text/markdown")}

    first = await client.post("/api/documents", files=payload)
    second = await client.post("/api/documents", files=payload)

    assert first.json()["data"]["document_id"] == second.json()["data"]["document_id"]
    assert second.json()["data"]["reused"] is True
    assert len(fake_vector_store.rows) == first.json()["data"]["chunk_count"]


async def test_list_and_detail(client: AsyncClient) -> None:
    """文档列表与详情"""
    await client.post(
        "/api/documents",
        files={"file": ("部署手册.md", MARKDOWN.encode("utf-8"), "text/markdown")},
    )

    listing = await client.get("/api/documents")
    assert listing.json()["data"]["total"] == 1
    document_id = listing.json()["data"]["items"][0]["id"]

    detail = await client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "部署手册"

    chunks = await client.get(f"/api/documents/{document_id}/chunks")
    assert chunks.status_code == 200
    assert chunks.json()["data"]["total"] >= 1


async def test_delete_document_removes_vectors(
    client: AsyncClient, fake_vector_store: FakeVectorStore
) -> None:
    """删文档会连带删掉 Milvus 里的向量"""
    await client.post(
        "/api/documents",
        files={"file": ("部署手册.md", MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    document_id = (await client.get("/api/documents")).json()["data"]["items"][0]["id"]

    assert len(fake_vector_store.rows) > 0

    response = await client.delete(f"/api/documents/{document_id}")
    assert response.status_code == 204

    assert fake_vector_store.rows == {}
    assert (await client.get("/api/documents")).json()["data"]["total"] == 0


async def test_ingest_unsupported_format(client: AsyncClient) -> None:
    """不支持的格式返回 422002"""
    response = await client.post(
        "/api/documents",
        files={"file": ("archive.zip", b"PK\x03\x04binary", "application/zip")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "422002"


async def test_search_finds_ingested_document(client: AsyncClient) -> None:
    """检索能命中刚入库的文档"""
    await client.post(
        "/api/documents",
        files={"file": ("部署手册.md", MARKDOWN.encode("utf-8"), "text/markdown")},
    )

    response = await client.post("/api/search", json={"query": "Docker 内存要求", "top_k": 3})

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["hits"]) >= 1
    assert data["hits"][0]["document_title"] == "部署手册"
    assert data["hits"][0]["heading_path"] == "部署手册 > 前置条件"
