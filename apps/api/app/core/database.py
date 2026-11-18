"""数据库引擎与会话管理

连接串**手工拼接**（没有 DATABASE_URL 这个环境变量），与项目配置一一对应。
引擎和 session factory 都是模块级懒加载单例。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import db_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """拼出异步连接串"""
    return (
        f"postgresql+asyncpg://{db_settings.user}:{db_settings.password}"
        f"@{db_settings.host}:{db_settings.port}/{db_settings.name}"
    )


def get_engine() -> AsyncEngine:
    """获取数据库引擎（懒加载单例）"""
    global _engine

    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=db_settings.echo,
        )

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取 session 工厂（懒加载单例）"""
    global _session_factory

    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,  # 明确指定使用异步 Session
            expire_on_commit=False,
            autoflush=True,
        )

    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供一个请求级数据库会话

    请求正常结束 → 提交事务；抛出异常 → 回滚；无论如何都会关闭会话。
    （会话不关闭会一直占着连接池，事务不提交则数据会随会话关闭被回滚。）
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def reset_engine() -> None:
    """重置引擎与 session 工厂（测试用：切库、清理连接）"""
    global _engine, _session_factory

    if _engine is not None:
        _engine.sync_engine.dispose()

    _engine = None
    _session_factory = None
