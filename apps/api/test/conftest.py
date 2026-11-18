"""测试夹具（SQLite 内存库）

设计原则：

1. **默认零外部依赖**：用例使用 `sqlite+aiosqlite:///:memory:`，不连接任何真实
   数据库，跑测试前不需要执行 `make db-init`。表结构由夹具从 ORM 模型现建。
2. **配置自包含**：在导入应用之前固定测试用环境变量，用例结果不再受开发者本机
   `.env` 左右
3. **绝不落到开发库**：数据库名被强制改写成 `rag_db_test`（可用 `TEST_DB_NAME` 覆盖，
   但必须以 `_test` 结尾）。
"""

import os
from collections.abc import AsyncGenerator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_NAME: str = os.environ.get("TEST_DB_NAME", "rag_db_test")

if not TEST_DB_NAME.endswith("_test"):
    raise RuntimeError(
        f"TEST_DB_NAME 必须以 `_test` 结尾（当前为 {TEST_DB_NAME!r}）："
        "测试库和开发库必须分开，避免测试写坏开发数据"
    )

# 环境变量优先级高于 .env ... 用直接赋值而不是 setdefault
os.environ["ENVIRONMENT"] = "test"
os.environ["DB_NAME"] = TEST_DB_NAME
os.environ["WEB_CORS_ORIGINS"] = "*"

# --- 下面的 import 必须在环境变量固定之后 ---

from app.core.database import get_db  # noqa: E402
from app.core.llm import get_llm_client  # noqa: E402
from app.core.vector_store import get_vector_store  # noqa: E402
from app.main import app  # noqa: E402
from app.model import Base  # noqa: E402
from test.fakes import FakeLLM, FakeVectorStore  # noqa: E402


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """提供测试用的数据库会话（内存 SQLite，每个用例一份）"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # SQLite 默认不校验外键，开启后模型里的 ondelete="CASCADE" 才与 PostgreSQL 行为一致
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(
        dbapi_connection: Any, _connection_record: Any
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def fake_llm() -> FakeLLM:
    """假的大模型客户端"""
    return FakeLLM()


@pytest.fixture
def fake_vector_store() -> FakeVectorStore:
    """假的向量库"""
    return FakeVectorStore()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    fake_llm: FakeLLM,
    fake_vector_store: FakeVectorStore,
) -> AsyncGenerator[AsyncClient, None]:
    """提供测试用的 HTTP 客户端（数据库、LLM、向量库全部换成假的）"""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    app.dependency_overrides[get_vector_store] = lambda: fake_vector_store
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        # 只清理自己注册的覆盖，不要 clear() 掉别的夹具/插件注册的依赖
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_llm_client, None)
        app.dependency_overrides.pop(get_vector_store, None)


@pytest.fixture(autouse=True)
def _guard_app_database() -> Iterator[None]:
    """兜底守卫：测试结束后不允许遗留指向开发库的全局引擎

    防止某个用例绕过夹具直接调用 `get_db()`，把数据写进开发库。
    """
    yield

    import app.core.database as database

    engine = database._engine
    if engine is None:
        return

    connected_db = engine.url.database
    database.reset_engine()

    if connected_db != TEST_DB_NAME:
        pytest.fail(
            "测试进程中创建了指向非测试库的数据库连接："
            f"{connected_db!r}（期望 {TEST_DB_NAME!r}）。"
            "请通过 db_session 夹具使用数据库，不要直接调用 get_db()"
        )
