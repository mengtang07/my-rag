"""PostgreSQL 辅助工具

集成测试与端到端测试共用：建库、删库、跑迁移、清表。
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[3]
API_DIR = PROJECT_ROOT / "apps" / "api"
ALEMBIC_INI = API_DIR / "alembic.ini"
MAINTENANCE_DB: str = "postgres"

TEST_DB_NAME: str = os.environ.get("TEST_DB_NAME", "rag_db_test")


def app_db_settings() -> tuple[str, str, str, str, str]:
    """从应用配置里取数据库连接信息"""
    from config import db_settings

    return (
        db_settings.host,
        db_settings.port,
        db_settings.user,
        db_settings.password,
        db_settings.name,
    )


def maintenance_url() -> str:
    """连接到系统库的连接串"""
    host, port, user, password, _ = app_db_settings()
    return f"postgresql://{user}:{password}@{host}:{port}/{MAINTENANCE_DB}"


def async_url(name: str) -> str:
    """异步连接串"""
    host, port, user, password, _ = app_db_settings()
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


def postgres_available() -> tuple[bool, str]:
    """PostgreSQL 是否可用"""
    try:
        connection = psycopg2.connect(maintenance_url(), connect_timeout=3)
        connection.close()
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def require_postgres() -> None:
    """PostgreSQL 不可用时跳过；REQUIRE_PG=1 时失败"""
    available, reason = postgres_available()
    if available:
        return
    if os.environ.get("REQUIRE_PG") == "1":
        pytest.fail(f"REQUIRE_PG=1，但 PostgreSQL 不可用：{reason}")
    pytest.skip(f"PostgreSQL 不可用，跳过集成测试：{reason}")


def database_exists(name: str) -> bool:
    """数据库是否存在"""
    connection = psycopg2.connect(maintenance_url())
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            return cursor.fetchone() is not None
    finally:
        connection.close()


def create_database(name: str) -> None:
    """建库（不存在则建）"""
    if database_exists(name):
        return
    connection = psycopg2.connect(maintenance_url())
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{name}"')
    finally:
        connection.close()


def drop_database(name: str) -> None:
    """删库"""
    if not database_exists(name):
        return
    connection = psycopg2.connect(maintenance_url())
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                (name,),
            )
            cursor.execute(f'DROP DATABASE IF EXISTS "{name}"')
    finally:
        connection.close()


def run_alembic(command: str, *args: str, env: dict[str, str] | None = None) -> None:
    """跑一条 alembic 命令（子进程，失败即测试失败）"""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), command, *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        pytest.fail(f"alembic {command} 失败：\n{result.stdout}\n{result.stderr}")


async def truncate_all(session: AsyncSession) -> None:
    """清空所有表（不动 alembic_version）"""
    result = await session.execute(
        text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename NOT IN ('alembic_version')"
        )
    )
    tables = [row[0] for row in result.fetchall()]
    if tables:
        await session.execute(
            text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE")
        )
