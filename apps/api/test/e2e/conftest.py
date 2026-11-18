"""端到端测试夹具：真起一个服务进程

这条链路是**唯一**能验证「写接口的数据真的落库了」的测试：
进程内的集成测试全程用同一个内存 session，看不出事务有没有提交。
"""

import os
import subprocess
import sys
import time
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv

from test.pg_helpers import (
    PROJECT_ROOT,
    create_database,
    drop_database,
    postgres_available,
    run_alembic,
    truncate_all,
)

API_DIR = PROJECT_ROOT / "apps" / "api"
TEST_SERVER_PORT: int = int(os.environ.get("E2E_SERVER_PORT", "18000"))
E2E_DB_NAME: str = os.environ.get("E2E_DB_NAME", "rag_db_e2e_test")
LOG_FILE = PROJECT_ROOT / "tmp" / "test_server.log"
SERVER_URL = f"http://127.0.0.1:{TEST_SERVER_PORT}"


def _load_env() -> None:
    """加载 .env（网关密钥、Milvus 地址都在这里）"""
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=False)


def _server_env() -> dict[str, str]:
    """服务进程的环境变量：数据库指向独立的 e2e 库"""
    env = {**os.environ, "ENVIRONMENT": "test", "DB_NAME": E2E_DB_NAME}
    return env


@pytest.fixture(scope="session", autouse=True)
def _server() -> Iterator[None]:
    """整个会话期间跑一个真实的服务进程"""
    _load_env()

    available, reason = postgres_available()
    if not available:
        pytest.skip(f"PostgreSQL 不可用，跳过端到端测试：{reason}")
    if not os.environ.get("LLM_API_KEY"):
        pytest.skip("缺少 LLM_API_KEY（.env），跳过端到端测试")

    create_database(E2E_DB_NAME)
    env = _server_env()
    run_alembic("upgrade", "head", env=env)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_FILE.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "fastapi",
            "dev",
            str(API_DIR / "app" / "main.py"),
            "--port",
            str(TEST_SERVER_PORT),
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )

    try:
        ready = False
        for _ in range(150):
            if process.poll() is not None:
                break
            try:
                if httpx.get(f"{SERVER_URL}/health", timeout=1).status_code == 200:
                    ready = True
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.2)

        if not ready:
            pytest.fail(f"服务进程没能起来，日志见 {LOG_FILE}")

        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log_handle.close()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """发真实 HTTP 请求的客户端"""
    async with httpx.AsyncClient(base_url=SERVER_URL, timeout=120) as client:
        yield client


@pytest_asyncio.fixture
async def clean_database() -> AsyncGenerator[None, None]:
    """每个用例前清空 e2e 库"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from test.pg_helpers import async_url

    engine = create_async_engine(async_url(E2E_DB_NAME), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await truncate_all(session)
        await session.commit()
    await engine.dispose()
    yield
