"""迁移脚本测试（需要 PostgreSQL）

这组用例验证的是「`alembic upgrade head` 能不能把空库变成模型定义的样子」，
和 `test_model_orm.py` 用 `create_all` 建表是两回事：

- `create_all` 只证明模型自洽；
- 这里的用例证明**迁移脚本**自洽，能发现「改了模型忘了生成迁移」「迁移脚本
  手写错了」「downgrade 写反了」这类问题。

每个用例都在一次性数据库上执行，结束后自动删除，不会碰 `tm_db`。
"""

import subprocess
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from app.model import Base

pytestmark = pytest.mark.postgres

# conftest.py 里 run_alembic 夹具的类型：command, *args, dbname=...
AlembicRunner = Callable[..., subprocess.CompletedProcess[str]]


def test_upgrade_head_from_scratch(
    scratch_database: str,
    run_alembic: AlembicRunner,
    database_state: SimpleNamespace,
) -> None:
    """空库执行 upgrade head：表齐全，版本号停在 head"""
    run_alembic("upgrade", "head", dbname=scratch_database)

    expected_tables = {table.name for table in Base.metadata.sorted_tables}
    actual_tables = database_state.table_names(scratch_database)

    assert expected_tables <= actual_tables
    assert "alembic_version" in actual_tables
    assert database_state.current_revision(
        scratch_database
    ) == database_state.head_revision()


def test_migrations_match_models(
    scratch_database: str, run_alembic: AlembicRunner
) -> None:
    """模型与迁移一致：`alembic check` 不应检测到新的 upgrade 操作

    改了模型但忘了 `make db-migrate` 时，这个用例会失败并打印 diff。
    """
    run_alembic("upgrade", "head", dbname=scratch_database)
    run_alembic("check", dbname=scratch_database)


def test_server_defaults_are_applied(
    scratch_database: str,
    run_alembic: AlembicRunner,
    database_state: SimpleNamespace,
) -> None:
    """模型声明了 server_default 的列，数据库里必须真有默认值

    `alembic check` 默认不比较 server_default，这类漂移只能单独查。
    之前 `product.description` 就是这么漏掉的：模型写了默认值，迁移没写，
    数据库侧直接 INSERT 会因 NOT NULL 失败。
    """
    run_alembic("upgrade", "head", dbname=scratch_database)

    assert database_state.missing_server_defaults(scratch_database) == []


def test_downgrade_to_base_then_upgrade_again(
    scratch_database: str,
    run_alembic: AlembicRunner,
    database_state: SimpleNamespace,
) -> None:
    """downgrade base 清空表，再 upgrade 能恢复到 head（校验 downgrade 脚本没写坏）"""
    run_alembic("upgrade", "head", dbname=scratch_database)
    run_alembic("downgrade", "base", dbname=scratch_database)

    assert database_state.table_names(scratch_database) == {"alembic_version"}
    assert database_state.current_revision(scratch_database) is None

    run_alembic("upgrade", "head", dbname=scratch_database)
    assert database_state.current_revision(
        scratch_database
    ) == database_state.head_revision()
