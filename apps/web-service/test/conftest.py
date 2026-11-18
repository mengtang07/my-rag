"""测试夹具（SQLite 内存库）

设计原则：

1. **默认零外部依赖**：用例使用 `sqlite+aiosqlite:///:memory:`，不连接任何真实
   数据库，跑测试前不需要执行 `make db-init`。表结构由夹具从 ORM 模型现建。
2. **配置自包含**：在导入应用之前固定测试用环境变量，用例结果不再受开发者本机
   `.env` 左右（比如把 `WEB_CORS_ORIGINS` 改成某个具体域名后，CORS 用例仍应通过）。
3. **绝不落到开发库**：数据库名被强制改写成 `tm_db_test`（可用 `TEST_DB_NAME` 覆盖，
   但必须以 `_test` 结尾）。即使有代码绕过夹具直接调用 `get_db`，也只会连测试库；
   `_guard_app_database` 还会在每个用例结束后兜底检查并把全局引擎清掉。

需要真实 PostgreSQL 的用例（迁移脚本、数据库级约束与级联）放在
`test/integration/` 目录，使用 `postgres` 标记，夹具见 `integration/conftest.py`。
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Iterator
from typing import Any

# ---------------------------------------------------------------------------
# 必须在导入 app 之前设置：pydantic-settings 在导入 app.core.config 时读取配置
# ---------------------------------------------------------------------------

TEST_DB_NAME: str = os.environ.get("TEST_DB_NAME", "tm_db_test")

if not TEST_DB_NAME.endswith("_test"):
    raise RuntimeError(
        f"TEST_DB_NAME 必须以 `_test` 结尾（当前为 {TEST_DB_NAME!r}）："
        "测试库和开发库必须分开，避免测试写坏开发数据"
    )

# 环境变量优先级高于 .env，因此下面这些值会覆盖本机 .env 里的开发配置。
# 这里用直接赋值而不是 setdefault：用例的期望值必须是确定的，
# 不能被开发者 shell 或 .env 里的临时改动带偏。
os.environ["ENVIRONMENT"] = "test"
os.environ["DB_NAME"] = TEST_DB_NAME

os.environ["WEB_CORS_ORIGINS"] = "*"
os.environ["WEB_CORS_ALLOW_METHODS"] = "*"
os.environ["WEB_CORS_ALLOW_HEADERS"] = "*"
os.environ["WEB_CORS_EXPOSE_HEADERS"] = "X-Process-Time,X-Request-ID"
os.environ["WEB_CORS_ALLOW_CREDENTIALS"] = "false"
os.environ["WEB_CORS_MAX_AGE"] = "600"

# ---------------------------------------------------------------------------

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.main import app
from app.model.base import Base


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


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """提供测试用的 HTTP 客户端（数据库依赖替换为内存 SQLite 会话）"""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        # 只清理自己注册的覆盖，不要 clear() 掉别的夹具/插件注册的依赖
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _guard_app_database() -> Iterator[None]:
    """兜底守卫：测试结束后不允许遗留指向开发库的全局引擎

    `app.core.database` 用模块级变量缓存 engine / session factory，一旦某个用例
    绕过夹具调用了 `get_db`，后续用例都会复用这条连接。这里在用例结束时检查并
    清理；如果发现连的不是测试库，直接让用例失败。
    """
    yield

    import app.core.database as database

    engine = database._engine
    if engine is None:
        return

    database._engine = None
    database._session_factory = None
    connected_db = engine.url.database
    engine.sync_engine.dispose()

    if connected_db != TEST_DB_NAME:
        pytest.fail(
            "测试进程中创建了指向非测试库的数据库连接："
            f"{connected_db!r}（期望 {TEST_DB_NAME!r}）。"
            "请通过 db_session / pg_session 夹具使用数据库，不要直接调用 get_db()"
        )
