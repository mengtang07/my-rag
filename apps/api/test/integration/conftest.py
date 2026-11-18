"""集成测试夹具

两类夹具：

1. **进程内 ASGI**（用根 conftest 的内存 SQLite + 假 LLM/向量库）—— 零外部依赖
2. **真实 PostgreSQL / Milvus** —— 连不上时自动跳过；
   设了 `REQUIRE_PG=1` / `REQUIRE_MILVUS=1` 则改为失败（CI 用，避免静默跳过）
"""

import os
from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from test.pg_helpers import (
    TEST_DB_NAME,
    async_url,
    create_database,
    require_postgres,
    run_alembic,
    truncate_all,
)


@pytest_asyncio.fixture
async def pg_session() -> AsyncGenerator[AsyncSession, None]:
    """真实 PostgreSQL 的会话（每个用例前清空表）"""
    require_postgres()

    create_database(TEST_DB_NAME)
    run_alembic("upgrade", "head")

    engine = create_async_engine(async_url(TEST_DB_NAME), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await truncate_all(session)
        await session.commit()
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_client(pg_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """连真实 PostgreSQL 的 HTTP 客户端"""
    from app.core.database import get_db
    from app.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield pg_session
            await pg_session.commit()
        except Exception:
            await pg_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="session")
def milvus_available() -> Iterator[bool]:
    """Milvus 是否可用"""
    from pymilvus import MilvusClient

    from config import milvus_settings

    client = None
    try:
        client = MilvusClient(uri=milvus_settings.uri, timeout=5)
        client.list_collections()
        yield True
    except Exception:  # noqa: BLE001
        if os.environ.get("REQUIRE_MILVUS") == "1":
            pytest.fail("REQUIRE_MILVUS=1，但 Milvus 不可用")
        pytest.skip("Milvus 不可用，跳过向量库集成测试")
    finally:
        if client is not None:
            client.close()
