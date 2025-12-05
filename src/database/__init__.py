"""
Gheezy Crypto - Модуль базы данных

Подключение к PostgreSQL и модели SQLAlchemy.
SQLite база данных для транзакций китов.
"""

from database.db import (
    async_session_factory,
    engine,
    get_session,
    init_db,
)
from database.models import (
    Alert,
    Base,
    Portfolio,
    Signal,
    Trade,
    User,
    WhaleTx,
)
from database.whale_db import (
    init_whale_db,
    save_transaction,
    get_stats,
    get_transactions,
    get_multi_period_stats,
    get_transaction_count,
)

__all__ = [
    # PostgreSQL (async)
    "engine",
    "async_session_factory",
    "get_session",
    "init_db",
    "Base",
    "User",
    "Portfolio",
    "Trade",
    "Signal",
    "WhaleTx",
    "Alert",
    # SQLite для китов
    "init_whale_db",
    "save_transaction",
    "get_stats",
    "get_transactions",
    "get_multi_period_stats",
    "get_transaction_count",
]
