"""端到端测试夹具

与其它夹具的分工：

- `test/conftest.py`：单元测试，内存 SQLite，零依赖；
- `test/integration/conftest.py`：进程内集成测试，真实 PostgreSQL，事务回滚；
- 这里的用例走 HTTP：测试服务器是**独立进程**（真实启动 uvicorn），请求用
  httpx 发出去，覆盖中间件、异常处理、路由注册等只有真实进程才会暴露的问题。

准备方式全自动：创建独立测试库（默认 `tm_db_e2e_test`，必须以 `_test` 结尾）、
执行 `alembic upgrade head`、拉起测试服务器，结束后删库并关掉服务器。

PostgreSQL 不可用时整体跳过（`make test` 在没装库的机器上仍能全绿）。
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# ─── 必须在导入 app 之前设置环境变量 ───

from dotenv import load_dotenv

# test/e2e/conftest.py -> test/e2e -> test -> web-service -> apps -> 项目根目录
PROJECT_ROOT: Path = Path(__file__).resolve().parents[4]
WEB_SERVICE_DIR: Path = PROJECT_ROOT / "apps" / "web-service"

load_dotenv(PROJECT_ROOT / ".env.test")

E2E_DB_NAME: str = os.environ.get("E2E_DB_NAME", "tm_db_e2e_test")
if not E2E_DB_NAME.endswith("_test"):
    raise RuntimeError(
        f"E2E_DB_NAME 必须以 `_test` 结尾（当前为 {E2E_DB_NAME!r}）："
        "测试库和开发库必须分开，避免测试写坏开发数据"
    )

# 注意：这里不改写 os.environ["DB_NAME"]。本文件会被 pytest 在
# test/integration/conftest.py 之前导入，改写全局环境变量会把集成测试的库名
# 顶成 e2e 库名。e2e 库名只在本文件内部和测试服务器子进程里使用。

from app.core.config import db_settings

import psycopg2
import pytest

TEST_SERVER_PORT = os.environ.get("E2E_SERVER_PORT", "18000")

_server_process: subprocess.Popen[bytes] | None = None
_log_file: Any = None


@contextmanager
def _create_cur() -> Any:
    conn = psycopg2.connect(
        host=db_settings.host or "localhost",
        port=db_settings.port or "5432",
        user=db_settings.user,
        password=db_settings.password,
        dbname="postgres",
        connect_timeout=3,
    )
    conn.autocommit = True
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()
        conn.close()


def _postgres_available() -> tuple[bool, str]:
    """探测 PostgreSQL 是否可用，返回 (是否可用, 原因)"""
    try:
        with _create_cur() as cur:
            cur.execute("SELECT 1")
    except psycopg2.OperationalError as exc:
        return False, str(exc).strip()
    return True, ""


def _reset_database() -> None:
    """删掉遗留的测试库并重建"""
    with _create_cur() as cur:
        cur.execute(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{E2E_DB_NAME}' AND pid <> pg_backend_pid()"
        )
        cur.execute(f"DROP DATABASE IF EXISTS {E2E_DB_NAME}")
        cur.execute(f"CREATE DATABASE {E2E_DB_NAME}")


def _run_migrations() -> None:
    """对 e2e 测试库执行 alembic upgrade head"""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option(
        "script_location", str(WEB_SERVICE_DIR / "migrations")
    )
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        f"postgresql://{db_settings.user}:{db_settings.password}"
        f"@{db_settings.host}:{db_settings.port}/{E2E_DB_NAME}",
    )
    command.upgrade(alembic_cfg, "head")


def _server_env() -> dict[str, str]:
    """测试服务器进程的环境变量：强制指向 e2e 测试库"""
    env = os.environ.copy()
    env.update(
        {
            "DB_HOST": db_settings.host or "localhost",
            "DB_PORT": db_settings.port or "5432",
            "DB_NAME": E2E_DB_NAME,
            "DB_USER": db_settings.user,
            "DB_PASSWORD": db_settings.password,
            "ENVIRONMENT": "test",
        }
    )
    return env


def _start_server() -> None:
    """拉起测试服务器进程，等 /docs 可访问后再返回"""
    global _server_process, _log_file

    tmp_dir = PROJECT_ROOT / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    _log_file = open(tmp_dir / "test_server.log", "w")
    _server_process = subprocess.Popen(
        [
            "uv",
            "run",
            "--package",
            "web-service",
            "fastapi",
            "dev",
            str(WEB_SERVICE_DIR / "app" / "main.py"),
            "--port",
            TEST_SERVER_PORT,
        ],
        cwd=PROJECT_ROOT,
        env=_server_env(),
        stdout=_log_file,
        stderr=subprocess.STDOUT,
    )

    import httpx

    for _ in range(100):
        try:
            resp = httpx.get(f"http://localhost:{TEST_SERVER_PORT}/docs")
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"测试服务器启动超时，日志见 {tmp_dir / 'test_server.log'}")


def _stop_server() -> None:
    global _server_process, _log_file

    if _server_process is not None:
        _server_process.terminate()
        _server_process.wait(timeout=10)
        _server_process = None
    if _log_file is not None:
        _log_file.close()
        _log_file = None


def pytest_sessionstart(session: pytest.Session) -> None:
    available, reason = _postgres_available()
    if not available:
        # 不可用时不动数据库、不起服务器，用例层面统一跳过
        return

    _reset_database()
    _run_migrations()
    _start_server()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _stop_server()

    available, _ = _postgres_available()
    if not available:
        return

    with _create_cur() as cur:
        cur.execute(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{E2E_DB_NAME}' AND pid <> pg_backend_pid()"
        )
        cur.execute(f"DROP DATABASE IF EXISTS {E2E_DB_NAME}")


@pytest.fixture(scope="session")
def event_loop() -> Any:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def base_url() -> str:
    return f"http://localhost:{TEST_SERVER_PORT}"


@pytest.fixture
async def async_client() -> Any:
    """指向独立测试服务器的 HTTP 客户端"""
    available, reason = _postgres_available()
    if not available:
        pytest.skip(f"PostgreSQL 不可用，跳过端到端测试：{reason}")

    from httpx import AsyncClient

    async with AsyncClient(base_url=f"http://localhost:{TEST_SERVER_PORT}") as client:
        yield client


@pytest.fixture(autouse=True)
async def cleanup_db(async_client: Any) -> Any:
    """每个用例结束后清空数据，用例之间互不影响"""
    yield

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.model.base import Base

    url = (
        f"postgresql+asyncpg://{db_settings.user}:{db_settings.password}"
        f"@{db_settings.host}:{db_settings.port}/{E2E_DB_NAME}"
    )
    engine = create_async_engine(url, poolclass=NullPool, echo=False)

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )
    await engine.dispose()
