"""
Gheezy Crypto - Database модели для Whale Tracker

Модели для хранения транзакций китов в базе данных.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.database.models import Base


class WhaleTransaction(Base):
    """
    Модель транзакции кита в базе данных.

    Хранит информацию о крупных криптовалютных транзакциях
    на Ethereum, BSC и Bitcoin.
    """

    __tablename__ = "whale_transactions_v2"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Идентификация транзакции
    tx_hash: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    blockchain: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Данные токена
    token_symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=8),
        nullable=False,
    )
    amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
    )

    # Адреса
    from_address: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    to_address: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Метки адресов (если известны)
    from_label: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    to_label: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Тип транзакции
    is_exchange_deposit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    is_exchange_withdrawal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    # Блок
    block_number: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # Временные метки
    tx_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Дополнительные данные
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Индексы для быстрого поиска
    __table_args__ = (
        Index("ix_whale_tx_blockchain_timestamp", "blockchain", "tx_timestamp"),
        Index("ix_whale_tx_amount_usd", "amount_usd"),
    )

    def __repr__(self) -> str:
        return (
            f"<WhaleTransaction(id={self.id}, "
            f"blockchain={self.blockchain}, "
            f"token={self.token_symbol}, "
            f"amount_usd=${self.amount_usd})>"
        )


class WhaleAlertSubscription(Base):
    """
    Модель подписки пользователя на оповещения о китах.

    Хранит настройки уведомлений для каждого пользователя.
    """

    __tablename__ = "whale_alert_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Telegram ID пользователя
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    # Настройки подписки
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # Фильтры по блокчейнам
    track_ethereum: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    track_bsc: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    track_bitcoin: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # Минимальная сумма для оповещений (в USD)
    min_amount_usd: Mapped[int] = mapped_column(
        BigInteger,
        default=100000,
    )

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<WhaleAlertSubscription(id={self.id}, "
            f"telegram_id={self.telegram_id}, "
            f"active={self.is_active})>"
        )


class WhaleStats(Base):
    """
    Модель агрегированной статистики по транзакциям китов.

    Хранит ежедневную статистику для быстрого доступа.
    """

    __tablename__ = "whale_stats"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Дата статистики
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Блокчейн (или 'all' для общей статистики)
    blockchain: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Количество транзакций
    total_transactions: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    # Объём в USD
    total_volume_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        default=0,
    )

    # Депозиты и выводы
    deposits_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )
    withdrawals_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )
    deposits_volume_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        default=0,
    )
    withdrawals_volume_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        default=0,
    )

    # Временная метка создания
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_whale_stats_date_blockchain", "date", "blockchain", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<WhaleStats(id={self.id}, "
            f"date={self.date}, "
            f"blockchain={self.blockchain}, "
            f"transactions={self.total_transactions})>"
        )
