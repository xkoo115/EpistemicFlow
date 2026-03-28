"""
数据库会话管理
提供异步SQLAlchemy会话工厂和连接管理
"""

from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool

from core.config import settings, Environment


class DatabaseManager:
    """数据库管理器

    负责管理数据库连接池和会话工厂
    """

    def __init__(self) -> None:
        """初始化数据库管理器"""
        self._engine: Optional[AsyncEngine] = None
        self._async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def init_engine(self) -> None:
        """初始化数据库引擎"""
        if self._engine is not None:
            return

        # 根据环境配置连接池
        pool_config = {}
        if settings.app.environment == Environment.TESTING:
            # 测试环境使用NullPool，避免连接泄漏
            pool_config["poolclass"] = NullPool
        else:
            pool_config.update(
                {
                    "pool_size": settings.database.pool_size,
                    "max_overflow": settings.database.max_overflow,
                    "pool_timeout": settings.database.pool_timeout,
                    "pool_recycle": 3600,  # 1小时回收连接
                }
            )

        # 创建异步引擎
        self._engine = create_async_engine(
            settings.database.url,
            echo=settings.database.echo,
            future=True,
            **pool_config,
        )

        # 创建会话工厂
        self._async_session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话

        Yields:
            AsyncSession: 异步数据库会话

        Raises:
            RuntimeError: 如果数据库未初始化
        """
        if self._async_session_factory is None:
            raise RuntimeError("数据库未初始化，请先调用 init_engine()")

        async with self._async_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._async_session_factory = None

    @property
    def engine(self) -> AsyncEngine:
        """获取数据库引擎"""
        if self._engine is None:
            raise RuntimeError("数据库未初始化")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """获取会话工厂"""
        if self._async_session_factory is None:
            raise RuntimeError("数据库未初始化")
        return self._async_session_factory


# 全局数据库管理器实例
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """依赖注入函数，用于FastAPI的依赖注入

    Yields:
        AsyncSession: 异步数据库会话
    """
    async for session in db_manager.get_session():
        yield session


async def init_database() -> None:
    """初始化数据库

    创建所有表（开发环境使用）
    """
    from models.workflow_state import Base

    # 初始化引擎
    db_manager.init_engine()

    # 创建所有表
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("数据库表创建完成")


async def close_database() -> None:
    """关闭数据库连接"""
    await db_manager.close()
