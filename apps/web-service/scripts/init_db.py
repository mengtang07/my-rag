"""初始化数据库

用法：

    uv run --package web-service python apps/web-service/scripts/init_db.py
    uv run --package web-service python apps/web-service/scripts/init_db.py --drop

流程：

1. 连接维护库（postgres），目标库不存在则创建
2. 执行 Alembic 迁移，把表结构升到最新版本

加 `--drop` 会先删除目标库再重建，相当于把数据库恢复到全新状态。
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg2
from alembic import command
from alembic.config import Config
from psycopg2 import sql

from app.core.config import db_settings

# web-service 应用目录（脚本位于 <应用目录>/scripts/）
WEB_SERVICE_DIR: Path = Path(__file__).resolve().parent.parent

# 维护库：新建数据库时必须连到系统自带的 postgres 库
MAINTENANCE_DB: str = "postgres"


def _connect() -> psycopg2.extensions.connection:
    """连接维护库（自动提交模式）"""
    conn = psycopg2.connect(
        host=db_settings.host,
        port=db_settings.port,
        dbname=MAINTENANCE_DB,
        user=db_settings.user,
        password=db_settings.password,
    )
    # CREATE DATABASE / DROP DATABASE 不能跑在事务里，必须自动提交
    conn.autocommit = True
    return conn


def database_exists() -> bool:
    """目标数据库是否已存在"""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (db_settings.name,)
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def drop_database() -> None:
    """删除目标库

    删除前先踢掉连着这个库的连接，否则 DROP DATABASE 会被阻塞。
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                "FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (db_settings.name,),
            )
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(db_settings.name)
                )
            )
    finally:
        conn.close()
    print(f"[init_db] 已删除数据库 {db_settings.name}")


def create_database() -> None:
    """创建目标库"""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_settings.name))
            )
    finally:
        conn.close()
    print(f"[init_db] 已创建数据库 {db_settings.name}")


def run_migrations() -> None:
    """执行迁移，把表结构升到最新版本"""
    cfg = Config(str(WEB_SERVICE_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")
    print("[init_db] 迁移完成，表结构已升级到最新版本")


def main(argv: list[str]) -> int:
    """初始化入口"""
    if "--drop" in argv:
        drop_database()

    if database_exists():
        print(f"[init_db] 数据库 {db_settings.name} 已存在，跳过创建")
    else:
        create_database()

    run_migrations()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
