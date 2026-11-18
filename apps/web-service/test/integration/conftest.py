"""PostgreSQL 集成测试夹具

与 `test/conftest.py` 的分工：

- 单元测试走内存 SQLite，零依赖；
- 这里的用例需要真实 PostgreSQL，用 `postgres` 标记，覆盖 SQLite 测不了的部分：
  迁移脚本、数据库级约束/级联、`server_default`、`JSON` 字段等。

准备方式是自动的：使用独立测试库（默认 `tm_db_test`，可用 `TEST_DB_NAME` 覆盖，
必须以 `_test` 结尾），库不存在则创建，并对它执行 `alembic upgrade head`。
每个用例跑在事务里，结束后回滚，用例之间互不影响。

连不上 PostgreSQL 时默认跳过（`make test` 在没装库的机器上仍能全绿）；
`REQUIRE_PG=1`（`make test-pg`）时改为失败，避免 CI 静默跳过。
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator, Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg2
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg2 import sql
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import db_settings
from app.core.database import get_db
from app.main import app
from app.model import Base

# test/integration/conftest.py -> test/integration -> test -> web-service -> apps -> 项目根目录
PROJECT_ROOT: Path = Path(__file__).resolve().parents[4]
WEB_SERVICE_DIR: Path = PROJECT_ROOT / "apps" / "web-service"
ALEMBIC_INI: Path = WEB_SERVICE_DIR / "alembic.ini"

# 建库/删库必须连到系统维护库
MAINTENANCE_DB: str = "postgres"

TEST_DB_NAME: str = os.environ["DB_NAME"]  # test/conftest.py 已强制改写

# 测试库名称必须以 TEST_DB_NAME 开头，杜绝误删开发库
def _assert_safe_db_name(name: str) -> None:
    if not name.startswith(TEST_DB_NAME):
        raise RuntimeError(
            f"拒绝操作非测试库 {name!r}：名称必须以 {TEST_DB_NAME!r} 开头"
        )


def _connect_kwargs(database: str) -> dict[str, Any]:
    """psycopg2 连接参数（同步驱动，用于建库、DDL、检查）"""
    return {
        "host": db_settings.host or "localhost",
        "port": db_settings.port or "5432",
        "dbname": database,
        "user": db_settings.user,
        "password": db_settings.password,
        "connect_timeout": 3,
    }


def _async_url(database: str) -> URL:
    """asyncpg 连接串（应用侧连接池用）"""
    return URL.create(
        "postgresql+asyncpg",
        username=db_settings.user,
        password=db_settings.password,
        host=db_settings.host or "localhost",
        port=int(db_settings.port or "5432"),
        database=database,
    )


def _admin_connection() -> psycopg2.extensions.connection:
    """连接维护库（自动提交，CREATE/DROP DATABASE 不能跑在事务里）"""
    conn = psycopg2.connect(**_connect_kwargs(MAINTENANCE_DB))
    conn.autocommit = True
    return conn


def _ensure_database(name: str) -> None:
    """目标库不存在则创建"""
    _assert_safe_db_name(name)
    conn = _admin_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            if cur.fetchone() is None:
                cur.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
                )
    finally:
        conn.close()


def _drop_database(name: str) -> None:
    """删除测试库（先踢掉连接，避免 DROP 被阻塞）"""
    _assert_safe_db_name(name)
    conn = _admin_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (name,),
            )
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name))
            )
    finally:
        conn.close()


def _postgres_available() -> tuple[bool, str]:
    """探测 PostgreSQL 是否可用，返回 (是否可用, 原因)"""
    try:
        conn = _admin_connection()
    except psycopg2.OperationalError as exc:
        return False, str(exc).strip()
    conn.close()
    return True, ""


def _require_postgres() -> None:
    """PostgreSQL 不可用时跳过；REQUIRE_PG=1 时失败"""
    available, reason = _postgres_available()
    if available:
        return
    if os.environ.get("REQUIRE_PG") == "1":
        pytest.fail(f"REQUIRE_PG=1，但 PostgreSQL 不可用：{reason}")
    pytest.skip(f"PostgreSQL 不可用，跳过集成测试：{reason}")


def _alembic_env(dbname: str) -> dict[str, str]:
    """执行 alembic 子进程时的环境变量（显式覆盖，绝不继承开发库配置）"""
    env = os.environ.copy()
    env.update(
        {
            "DB_HOST": db_settings.host or "localhost",
            "DB_PORT": db_settings.port or "5432",
            "DB_NAME": dbname,
            "DB_USER": db_settings.user,
            "DB_PASSWORD": db_settings.password,
            "ENVIRONMENT": "test",
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(WEB_SERVICE_DIR), env.get("PYTHONPATH", "")])
            ),
        }
    )
    return env


def _run_alembic(dbname: str, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    """在指定测试库上执行 alembic 命令，非 0 退出直接让用例失败"""
    _assert_safe_db_name(dbname)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_INI),
            command,
            *args,
        ],
        cwd=PROJECT_ROOT,
        env=_alembic_env(dbname),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"alembic {command} {' '.join(args)} 在 {dbname} 上执行失败\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def _table_names(dbname: str) -> set[str]:
    """当前库 public schema 下的表名"""
    conn = psycopg2.connect(**_connect_kwargs(dbname))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def _current_revision(dbname: str) -> str | None:
    """alembic_version 里记录的版本号（没有版本表时返回 None）"""
    conn = psycopg2.connect(**_connect_kwargs(dbname))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.alembic_version')")
            if cur.fetchone()[0] is None:
                return None
            cur.execute("SELECT version_num FROM alembic_version")
            row = cur.fetchone()
            return None if row is None else str(row[0])
    finally:
        conn.close()


def _missing_server_defaults(dbname: str) -> list[str]:
    """模型声明了 server_default、但数据库里没有默认值的列

    `alembic check` 默认不比较服务端默认值（PostgreSQL 的 JSON 列也没有 `=` 运算符，
    开启比较会直接报错），所以这里单独对比 information_schema。
    """
    conn = psycopg2.connect(**_connect_kwargs(dbname))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name, column_name, column_default "
                "FROM information_schema.columns WHERE table_schema = 'public'"
            )
            db_defaults = {
                (table, column): default for table, column, default in cur.fetchall()
            }
    finally:
        conn.close()

    missing: list[str] = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if column.server_default is None:
                continue
            if db_defaults.get((table.name, column.name)) is None:
                missing.append(f"{table.name}.{column.name}")
    return missing


def _head_revision() -> str:
    """迁移链的 head 版本号（要求只有一个 head）"""
    proc = _run_alembic(TEST_DB_NAME, "heads")
    heads = [
        line.split()[0]
        for line in proc.stdout.splitlines()
        if line.strip() and "(head)" in line
    ]
    if len(heads) != 1:
        pytest.fail(
            "迁移链应当只有一个 head，当前为："
            f"{heads or proc.stdout.strip()}"
        )
    return heads[0]


def _empty_all_tables() -> None:
    """清空测试库数据并重置自增序列（会话开始时执行一次）"""
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    if not tables:
        return
    conn = psycopg2.connect(**_connect_kwargs(TEST_DB_NAME))
    try:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[AsyncEngine]:
    """指向测试库的异步引擎；建库 + 迁移 + 清数据只做一次

    用 NullPool：不同用例跑在不同事件循环里，连接不能跨循环复用。
    """
    _require_postgres()
    _ensure_database(TEST_DB_NAME)
    _run_alembic(TEST_DB_NAME, "upgrade", "head")
    _empty_all_tables()

    engine = create_async_engine(_async_url(TEST_DB_NAME), poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.sync_engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """每个用例一个事务，结束后回滚，避免用例间互相污染

    `join_transaction_mode="create_savepoint"` 让业务代码里的 `commit()`
    只提交到保存点，外层事务回滚时一起撤销。
    """
    async with pg_engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


@pytest_asyncio.fixture
async def pg_client(pg_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """数据库依赖指向 PostgreSQL 事务会话的 HTTP 客户端"""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def scratch_database() -> Iterator[str]:
    """一次性数据库：用例开始时创建，结束时删除"""
    _require_postgres()
    name = f"{TEST_DB_NAME}_mig_{uuid.uuid4().hex[:8]}"
    _ensure_database(name)
    try:
        yield name
    finally:
        _drop_database(name)


@pytest.fixture
def run_alembic() -> Callable[..., subprocess.CompletedProcess[str]]:
    """在指定数据库上执行 alembic 命令的工厂

    用法：`run_alembic("upgrade", "head", dbname=scratch_database)`
    """

    def _run(
        command: str, *args: str, dbname: str = TEST_DB_NAME
    ) -> subprocess.CompletedProcess[str]:
        return _run_alembic(dbname, command, *args)

    return _run


@pytest.fixture
def database_state() -> SimpleNamespace:
    """读取测试库结构的辅助方法"""
    return SimpleNamespace(
        table_names=_table_names,
        current_revision=_current_revision,
        head_revision=_head_revision,
        missing_server_defaults=_missing_server_defaults,
    )
