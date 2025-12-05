"""
Gheezy Crypto - SQLite база данных для транзакций китов

Локальное хранение всех транзакций китов для:
- Сохранения данных между перезапусками
- Реальной статистики за 24ч/7д/30д
- Быстрого поиска по chain и времени
"""

import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

DATABASE_PATH = "data/whales.db"


def init_whale_db() -> None:
    """
    Инициализация SQLite базы данных для транзакций китов.

    Создаёт папку data/ и таблицу whale_transactions с индексами.
    """
    os.makedirs("data", exist_ok=True)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Таблица транзакций
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS whale_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_hash TEXT UNIQUE NOT NULL,
            chain TEXT NOT NULL,
            from_address TEXT,
            to_address TEXT,
            amount REAL NOT NULL,
            amount_usd REAL,
            token TEXT DEFAULT 'native',
            timestamp DATETIME NOT NULL,
            block_number INTEGER,
            from_label TEXT,
            to_label TEXT,
            tx_type TEXT,
            fee REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Индексы для быстрого поиска
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_chain ON whale_transactions(chain)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_timestamp ON whale_transactions(timestamp)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_amount_usd ON whale_transactions(amount_usd)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_chain_timestamp "
        "ON whale_transactions(chain, timestamp)"
    )

    conn.commit()
    conn.close()

    logger.info(
        "SQLite база данных инициализирована",
        path=DATABASE_PATH,
    )


def save_transaction(tx: dict[str, Any]) -> bool:
    """
    Сохранить транзакцию в базу данных.

    Args:
        tx: Словарь с данными транзакции:
            - tx_hash: Хэш транзакции (обязательно)
            - chain: Название блокчейна (обязательно)
            - amount: Сумма в нативной валюте (обязательно)
            - amount_usd: Сумма в USD
            - from_address: Адрес отправителя
            - to_address: Адрес получателя
            - token: Символ токена
            - timestamp: Время транзакции
            - block_number: Номер блока
            - from_label: Метка отправителя
            - to_label: Метка получателя
            - tx_type: Тип транзакции
            - fee: Комиссия

    Returns:
        bool: True если транзакция сохранена, False если дубликат или ошибка
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Получаем timestamp
        timestamp = tx.get("timestamp")
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        elif isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()

        cursor.execute(
            """
            INSERT OR IGNORE INTO whale_transactions (
                tx_hash, chain, from_address, to_address,
                amount, amount_usd, token, timestamp,
                block_number, from_label, to_label, tx_type, fee
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx.get("tx_hash"),
                tx.get("chain"),
                tx.get("from_address"),
                tx.get("to_address"),
                tx.get("amount", 0),
                tx.get("amount_usd", 0),
                tx.get("token", "native"),
                timestamp,
                tx.get("block_number"),
                tx.get("from_label"),
                tx.get("to_label"),
                tx.get("tx_type"),
                tx.get("fee"),
            ),
        )

        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()

        if rows_affected > 0:
            logger.debug(
                "Транзакция сохранена в базу",
                tx_hash=tx.get("tx_hash"),
                chain=tx.get("chain"),
            )
            return True
        return False

    except Exception as e:
        logger.error(
            "Ошибка сохранения транзакции",
            error=str(e),
            tx_hash=tx.get("tx_hash"),
        )
        return False


def get_stats(
    chain: Optional[str] = None,
    hours: int = 24,
) -> dict[str, Any]:
    """
    Получить статистику транзакций за период.

    Args:
        chain: Фильтр по блокчейну (None для всех)
        hours: Количество часов для анализа

    Returns:
        dict: Статистика:
            - chain: Название блокчейна
            - period: Период статистики
            - tx_count: Количество транзакций
            - total_volume_usd: Общий объём в USD
            - avg_tx_usd: Средняя транзакция в USD
            - largest_tx_usd: Крупнейшая транзакция в USD
            - deposits_count: Количество депозитов
            - withdrawals_count: Количество выводов
            - deposits_volume: Объём депозитов
            - withdrawals_volume: Объём выводов
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Время начала периода
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        start_time_str = start_time.isoformat()

        # Базовый запрос для статистики
        base_query = """
            SELECT
                COUNT(*) as tx_count,
                COALESCE(SUM(amount_usd), 0) as total_volume,
                COALESCE(AVG(amount_usd), 0) as avg_tx,
                COALESCE(MAX(amount_usd), 0) as largest_tx
            FROM whale_transactions
            WHERE timestamp >= ?
        """

        params: list[Any] = [start_time_str]
        if chain:
            base_query += " AND chain = ?"
            params.append(chain)

        cursor.execute(base_query, params)
        row = cursor.fetchone()
        tx_count, total_volume, avg_tx, largest_tx = row

        # Получаем количество депозитов и выводов
        deposits_query = """
            SELECT
                COUNT(*) as count,
                COALESCE(SUM(amount_usd), 0) as volume
            FROM whale_transactions
            WHERE timestamp >= ? AND tx_type = 'DEPOSIT'
        """
        deposits_params: list[Any] = [start_time_str]
        if chain:
            deposits_query += " AND chain = ?"
            deposits_params.append(chain)

        cursor.execute(deposits_query, deposits_params)
        deposits_row = cursor.fetchone()
        deposits_count, deposits_volume = deposits_row

        withdrawals_query = """
            SELECT
                COUNT(*) as count,
                COALESCE(SUM(amount_usd), 0) as volume
            FROM whale_transactions
            WHERE timestamp >= ? AND tx_type = 'WITHDRAWAL'
        """
        withdrawals_params: list[Any] = [start_time_str]
        if chain:
            withdrawals_query += " AND chain = ?"
            withdrawals_params.append(chain)

        cursor.execute(withdrawals_query, withdrawals_params)
        withdrawals_row = cursor.fetchone()
        withdrawals_count, withdrawals_volume = withdrawals_row

        conn.close()

        # Форматирование периода
        if hours == 24:
            period = "24h"
        elif hours == 168:
            period = "7d"
        elif hours == 720:
            period = "30d"
        else:
            period = f"{hours}h"

        return {
            "chain": chain or "ALL",
            "period": period,
            "tx_count": tx_count,
            "total_volume_usd": total_volume,
            "avg_tx_usd": avg_tx,
            "largest_tx_usd": largest_tx,
            "deposits_count": deposits_count,
            "withdrawals_count": withdrawals_count,
            "deposits_volume": deposits_volume,
            "withdrawals_volume": withdrawals_volume,
        }

    except Exception as e:
        logger.error(
            "Ошибка получения статистики",
            error=str(e),
            chain=chain,
            hours=hours,
        )
        return {
            "chain": chain or "ALL",
            "period": f"{hours}h",
            "tx_count": 0,
            "total_volume_usd": 0,
            "avg_tx_usd": 0,
            "largest_tx_usd": 0,
            "deposits_count": 0,
            "withdrawals_count": 0,
            "deposits_volume": 0,
            "withdrawals_volume": 0,
        }


def get_transactions(
    chain: Optional[str] = None,
    limit: int = 100,
    hours: int = 24,
) -> list[dict[str, Any]]:
    """
    Получить транзакции за период.

    Args:
        chain: Фильтр по блокчейну (None для всех)
        limit: Максимальное количество транзакций
        hours: Количество часов для анализа

    Returns:
        list[dict]: Список транзакций
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Время начала периода
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        start_time_str = start_time.isoformat()

        query = """
            SELECT
                tx_hash, chain, from_address, to_address,
                amount, amount_usd, token, timestamp,
                from_label, to_label, tx_type
            FROM whale_transactions
            WHERE timestamp >= ?
        """
        params: list[Any] = [start_time_str]

        if chain:
            query += " AND chain = ?"
            params.append(chain)

        query += " ORDER BY amount_usd DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "tx_hash": row["tx_hash"],
                "chain": row["chain"],
                "from_address": row["from_address"],
                "to_address": row["to_address"],
                "amount": row["amount"],
                "amount_usd": row["amount_usd"],
                "token": row["token"],
                "timestamp": row["timestamp"],
                "from_label": row["from_label"],
                "to_label": row["to_label"],
                "tx_type": row["tx_type"],
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(
            "Ошибка получения транзакций",
            error=str(e),
            chain=chain,
            hours=hours,
        )
        return []


def get_multi_period_stats(chain: Optional[str] = None) -> dict[str, dict[str, Any]]:
    """
    Получить статистику за несколько периодов (24ч, 7д, 30д).

    Args:
        chain: Фильтр по блокчейну (None для всех)

    Returns:
        dict: Статистика по периодам:
            - 24h: Статистика за 24 часа
            - 7d: Статистика за 7 дней
            - 30d: Статистика за 30 дней
    """
    return {
        "24h": get_stats(chain=chain, hours=24),
        "7d": get_stats(chain=chain, hours=168),
        "30d": get_stats(chain=chain, hours=720),
    }


def get_transaction_count() -> int:
    """
    Получить общее количество транзакций в базе.

    Returns:
        int: Количество транзакций
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM whale_transactions")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0
