"""
Gheezy Crypto - Подключение к базе данных

Асинхронное подключение к PostgreSQL через SQLAlchemy.
"""

import contextlib
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings

# Создаём асинхронный движок
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Фабрика сессий
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Получение асинхронной сессии базы данных.

    Используется как зависимость в FastAPI или вручную.

    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy.

    Example:
        async for session in get_session():
            result = await session.execute(select(User))
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@contextlib.asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Контекстный менеджер для получения сессии.

    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy.

    Example:
        async with get_session_context() as session:
            result = await session.execute(select(User))
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Инициализация базы данных.

    Создаёт все таблицы, определённые в моделях.
    Вызывается при запуске приложения.
    """
    from database.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Закрытие подключения к базе данных.

    Вызывается при остановке приложения.
    """
    await engine.dispose()
