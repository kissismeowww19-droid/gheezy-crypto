"""
Gheezy Crypto - SQLAlchemy модели

Определение таблиц базы данных для всех компонентов платформы.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""

    pass


class SignalType(str, Enum):
    """Типы торговых сигналов."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class AlertType(str, Enum):
    """Типы уведомлений."""

    PRICE = "price"
    SIGNAL = "signal"
    WHALE = "whale"
    DEFI = "defi"


class User(Base):
    """
    Модель пользователя.

    Хранит информацию о пользователях Telegram бота.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Связи
    portfolios: Mapped[list["Portfolio"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    trades: Mapped[list["Trade"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Portfolio(Base):
    """
    Модель портфеля пользователя.

    Хранит информацию о криптовалютных активах пользователя.
    """

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
    )
    avg_buy_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Связи
    user: Mapped["User"] = relationship(back_populates="portfolios")

    def __repr__(self) -> str:
        return f"<Portfolio(id={self.id}, symbol={self.symbol}, amount={self.amount})>"


class Trade(Base):
    """
    Модель торговой операции.

    Хранит историю сделок пользователей.
    """

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[SignalType] = mapped_column(
        SQLEnum(SignalType),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
    )
    fee: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        default=0,
    )
    is_copy_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    source_signal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("signals.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Связи
    user: Mapped["User"] = relationship(back_populates="trades")
    source_signal: Mapped[Optional["Signal"]] = relationship()

    def __repr__(self) -> str:
        return f"<Trade(id={self.id}, symbol={self.symbol}, side={self.side})>"


class Signal(Base):
    """
    Модель торгового сигнала.

    Хранит AI-генерированные сигналы с объяснениями.
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    signal_type: Mapped[SignalType] = mapped_column(
        SQLEnum(SignalType),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=False,
    )
    price_at_signal: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
    )
    target_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
    )
    stop_loss: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
    )

    # Технические индикаторы
    rsi_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=True,
    )
    macd_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=10, scale=4),
        nullable=True,
    )
    bb_position: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Объяснение сигнала
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Signal(id={self.id}, symbol={self.symbol}, type={self.signal_type})>"


class WhaleTx(Base):
    """
    Модель транзакции кита.

    Хранит информацию о крупных транзакциях.
    """

    __tablename__ = "whale_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tx_hash: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    blockchain: Mapped[str] = mapped_column(String(50), nullable=False)
    token_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=30, scale=8),
        nullable=False,
    )
    amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
    )
    from_address: Mapped[str] = mapped_column(String(100), nullable=False)
    to_address: Mapped[str] = mapped_column(String(100), nullable=False)
    is_exchange_deposit: Mapped[bool] = mapped_column(Boolean, default=False)
    is_exchange_withdrawal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<WhaleTx(id={self.id}, token={self.token_symbol}, amount_usd={self.amount_usd})>"


class Alert(Base):
    """
    Модель уведомления пользователя.

    Хранит настройки уведомлений для пользователей.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_type: Mapped[AlertType] = mapped_column(
        SQLEnum(AlertType),
        nullable=False,
    )
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    target_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=True,
    )
    condition: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Связи
    user: Mapped["User"] = relationship(back_populates="alerts")

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, type={self.alert_type}, symbol={self.symbol})>"
