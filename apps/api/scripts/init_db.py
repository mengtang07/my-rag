"""初始化数据库：库不存在则创建，并执行迁移

用法：
    python apps/api/scripts/init_db.py           # 建库（不存在则建）+ 迁移
    python apps/api/scripts/init_db.py --drop    # 先删库再建（会清空数据）
"""

import argparse
import sys
from pathlib import Path

import psycopg2
from alembic import command
from alembic.config import Config
from loguru import logger

WEB_SERVICE_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = WEB_SERVICE_DIR / "alembic.ini"

# 导入项目配置（在 sys.path 调整之后）
sys.path.insert(0, str(WEB_SERVICE_DIR))

from config import db_settings  # noqa: E402


def _maintenance_url() -> str:
    """连接到系统库的连接串（用于 CREATE/DROP DATABASE）"""
    return (
        f"postgresql://{db_settings.user}:{db_settings.password}"
        f"@{db_settings.host}:{db_settings.port}/postgres"
    )


def database_exists() -> bool:
    """目标库是否已存在"""
    connection = psycopg2.connect(_maintenance_url())
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_settings.name,))
            return cursor.fetchone() is not None
    finally:
        connection.close()


def create_database() -> None:
    """创建目标库（已存在则跳过）"""
    if database_exists():
        logger.info(f"数据库 {db_settings.name} 已存在")
        return

    connection = psycopg2.connect(_maintenance_url())
    try:
        # CREATE DATABASE 不能在事务里执行
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{db_settings.name}"')
        logger.info(f"数据库 {db_settings.name} 创建成功")
    finally:
        connection.close()


def drop_database() -> None:
    """删除目标库（连同连接）"""
    if not database_exists():
        logger.info(f"数据库 {db_settings.name} 不存在，跳过删除")
        return

    connection = psycopg2.connect(_maintenance_url())
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                (db_settings.name,),
            )
            cursor.execute(f'DROP DATABASE IF EXISTS "{db_settings.name}"')
        logger.info(f"数据库 {db_settings.name} 已删除")
    finally:
        connection.close()


def run_migrations() -> None:
    """执行迁移，把表结构升到最新版本"""
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head")
    logger.info("迁移执行完成")


def main() -> None:
    """命令行入口"""
    parser = argparse.ArgumentParser(description="初始化数据库")
    parser.add_argument("--drop", action="store_true", help="先删库再建（会清空数据）")
    args = parser.parse_args()

    if args.drop:
        drop_database()

    create_database()
    run_migrations()

    logger.info(f"数据库 {db_settings.name} 就绪")


if __name__ == "__main__":
    main()
