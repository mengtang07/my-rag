"""迁移脚本测试（真实 PostgreSQL）"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from test.pg_helpers import create_database, drop_database, run_alembic

pytestmark = pytest.mark.postgres

SCRATCH_DB: str = "rag_db_migration_scratch_test"


async def test_migrations_roundtrip(pg_session: AsyncSession) -> None:
    """迁移脚本能升到最新、能校验一致、能回滚、能再升上来

    用一次性数据库跑，不会碰开发库。
    """
    drop_database(SCRATCH_DB)
    create_database(SCRATCH_DB)

    env = {**os.environ, "DB_NAME": SCRATCH_DB}
    try:
        run_alembic("upgrade", "head", env=env)
        run_alembic("check", env=env)
        run_alembic("downgrade", "base", env=env)
        run_alembic("upgrade", "head", env=env)
    finally:
        drop_database(SCRATCH_DB)


async def test_all_tables_exist(pg_session: AsyncSession) -> None:
    """迁移之后四张表都在"""
    result = await pg_session.execute(
        text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename IN ('document', 'chunk', 'conversation', 'message')"
        )
    )
    tables = {row[0] for row in result.fetchall()}

    assert tables == {"document", "chunk", "conversation", "message"}


async def test_pg_trgm_extension_installed(pg_session: AsyncSession) -> None:
    """pg_trgm 扩展装上了（关键词召回的底子）"""
    result = await pg_session.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
    )
    assert result.fetchone() is not None


async def test_unique_constraint_on_content_hash(pg_session: AsyncSession) -> None:
    """content_hash 唯一 —— 这是重复摄入幂等的基础"""
    from sqlalchemy.exc import IntegrityError

    from app.model.document import Document

    pg_session.add(
        Document(title="A", filename="a.md", content_hash="same-hash", status="ready")
    )
    await pg_session.flush()

    pg_session.add(
        Document(title="B", filename="b.md", content_hash="same-hash", status="ready")
    )
    try:
        await pg_session.flush()
    except IntegrityError:
        await pg_session.rollback()
        return
    raise AssertionError("重复的 content_hash 应当触发唯一约束")
