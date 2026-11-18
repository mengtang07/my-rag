from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 从项目配置中读取数据库连接信息
from app.core.config import db_settings

# 导入模型**包**（不是 app.model.base）：
# `app.model.__init__` 会把全部模型注册到 Base.metadata，
# 只导入 base 会导致 autogenerate 漏掉所有表。
from app.model import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 用项目配置覆盖 alembic.ini 中的 sqlalchemy.url
# 使用同步驱动 postgresql://（不需要 +asyncpg）
config.set_main_option(
    "sqlalchemy.url",
    f"postgresql://{db_settings.user}:{db_settings.password}"
    f"@{db_settings.host}:{db_settings.port}/{db_settings.name}",
)

# 告诉 Alembic 你的模型元数据，用于自动生成迁移
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL 不连数据库"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连上数据库执行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
