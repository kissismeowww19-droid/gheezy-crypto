"""
Gheezy Crypto - Система Copy-Trading

Копирование сигналов лучших трейдеров с отслеживанием производительности.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import structlog

from src.database.models import SignalType

logger = structlog.get_logger()


@dataclass
class TraderStats:
    """
    Статистика трейдера.
    
    Attributes:
        total_trades: Общее количество сделок
        winning_trades: Количество прибыльных сделок
        total_profit_percent: Общая прибыль в процентах
        avg_trade_duration: Средняя длительность сделки
        max_drawdown: Максимальная просадка
    """

    total_trades: int = 0
    winning_trades: int = 0
    total_profit_percent: float = 0.0
    avg_trade_duration: float = 0.0
    max_drawdown: float = 0.0

    @property
    def win_rate(self) -> float:
        """Процент выигрышных сделок."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100


@dataclass
class Trader:
    """
    Трейдер для копирования.
    
    Attributes:
        trader_id: Уникальный ID трейдера
        name: Имя/никнейм трейдера
        description: Описание стратегии
        risk_level: Уровень риска (1-5)
        is_verified: Верифицированный трейдер
        followers_count: Количество подписчиков
        stats: Статистика трейдера
        min_copy_amount: Минимальная сумма для копирования
        created_at: Дата создания профиля
    """

    trader_id: str
    name: str
    description: str
    risk_level: int
    is_verified: bool = False
    followers_count: int = 0
    stats: TraderStats = field(default_factory=TraderStats)
    min_copy_amount: float = 100.0
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def risk_emoji(self) -> str:
        """Эмодзи уровня риска."""
        risk_emojis = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", 5: "⚫"}
        return risk_emojis.get(self.risk_level, "⚪")

    @property
    def risk_label(self) -> str:
        """Текстовое описание уровня риска."""
        labels = {
            1: "Низкий",
            2: "Умеренный",
            3: "Средний",
            4: "Высокий",
            5: "Очень высокий",
        }
        return labels.get(self.risk_level, "Неизвестно")


@dataclass
class CopyTrade:
    """
    Скопированная сделка.
    
    Attributes:
        trade_id: ID сделки
        trader_id: ID трейдера-источника
        user_id: ID пользователя-копировщика
        symbol: Символ криптовалюты
        side: Направление (buy/sell)
        amount: Сумма сделки
        entry_price: Цена входа
        exit_price: Цена выхода (если закрыта)
        profit_loss: Прибыль/убыток
        status: Статус сделки
        created_at: Время создания
        closed_at: Время закрытия
    """

    trade_id: str
    trader_id: str
    user_id: int
    symbol: str
    side: SignalType
    amount: Decimal
    entry_price: Decimal
    exit_price: Optional[Decimal] = None
    profit_loss: Optional[Decimal] = None
    status: str = "open"
    created_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None


class CopyTradingSystem:
    """
    Система копи-трейдинга.
    
    Позволяет пользователям копировать сделки успешных трейдеров
    и отслеживать их производительность.
    """

    def __init__(self):
        """Инициализация системы."""
        # В реальной системе это будет из БД
        self._traders: Dict[str, Trader] = {}
        self._user_subscriptions: Dict[int, List[str]] = {}
        self._active_trades: Dict[str, CopyTrade] = {}
        
        # Инициализируем демо-трейдерами
        self._init_demo_traders()

    def _init_demo_traders(self) -> None:
        """Инициализация демо-трейдеров для демонстрации."""
        demo_traders = [
            Trader(
                trader_id="crypto_whale_1",
                name="CryptoWhale",
                description="Долгосрочные инвестиции в топ-10 криптовалют",
                risk_level=2,
                is_verified=True,
                followers_count=1250,
                stats=TraderStats(
                    total_trades=156,
                    winning_trades=112,
                    total_profit_percent=45.7,
                    avg_trade_duration=72.0,
                    max_drawdown=8.5,
                ),
                min_copy_amount=50.0,
            ),
            Trader(
                trader_id="defi_master_2",
                name="DeFi Master",
                description="Стратегии с DeFi токенами и yield farming",
                risk_level=4,
                is_verified=True,
                followers_count=890,
                stats=TraderStats(
                    total_trades=423,
                    winning_trades=267,
                    total_profit_percent=89.3,
                    avg_trade_duration=12.0,
                    max_drawdown=22.1,
                ),
                min_copy_amount=100.0,
            ),
            Trader(
                trader_id="btc_hodler_3",
                name="BTC Hodler",
                description="Только Bitcoin, только HODL",
                risk_level=1,
                is_verified=False,
                followers_count=2100,
                stats=TraderStats(
                    total_trades=45,
                    winning_trades=38,
                    total_profit_percent=120.5,
                    avg_trade_duration=720.0,
                    max_drawdown=15.0,
                ),
                min_copy_amount=200.0,
            ),
            Trader(
                trader_id="scalper_pro_4",
                name="Scalper Pro",
                description="Краткосрочный скальпинг на волатильности",
                risk_level=5,
                is_verified=True,
                followers_count=560,
                stats=TraderStats(
                    total_trades=1890,
                    winning_trades=1134,
                    total_profit_percent=67.2,
                    avg_trade_duration=0.5,
                    max_drawdown=35.0,
                ),
                min_copy_amount=500.0,
            ),
            Trader(
                trader_id="alt_hunter_5",
                name="Alt Hunter",
                description="Поиск недооценённых альткоинов",
                risk_level=3,
                is_verified=False,
                followers_count=780,
                stats=TraderStats(
                    total_trades=234,
                    winning_trades=140,
                    total_profit_percent=156.8,
                    avg_trade_duration=48.0,
                    max_drawdown=28.5,
                ),
                min_copy_amount=75.0,
            ),
        ]

        for trader in demo_traders:
            self._traders[trader.trader_id] = trader

    async def get_top_traders(
        self,
        sort_by: str = "profit",
        limit: int = 10,
    ) -> List[Trader]:
        """
        Получение топ трейдеров.
        
        Args:
            sort_by: Сортировка (profit, win_rate, followers)
            limit: Максимальное количество
        
        Returns:
            List[Trader]: Список трейдеров
        """
        traders = list(self._traders.values())

        if sort_by == "profit":
            traders.sort(key=lambda t: t.stats.total_profit_percent, reverse=True)
        elif sort_by == "win_rate":
            traders.sort(key=lambda t: t.stats.win_rate, reverse=True)
        elif sort_by == "followers":
            traders.sort(key=lambda t: t.followers_count, reverse=True)

        return traders[:limit]

    async def get_trader(self, trader_id: str) -> Optional[Trader]:
        """
        Получение информации о трейдере.
        
        Args:
            trader_id: ID трейдера
        
        Returns:
            Trader: Информация о трейдере или None
        """
        return self._traders.get(trader_id)

    async def subscribe_to_trader(
        self,
        user_id: int,
        trader_id: str,
        copy_amount: float,
    ) -> bool:
        """
        Подписка на трейдера.
        
        Args:
            user_id: ID пользователя
            trader_id: ID трейдера
            copy_amount: Сумма для копирования
        
        Returns:
            bool: Успешность подписки
        """
        trader = await self.get_trader(trader_id)
        if not trader:
            logger.warning("Трейдер не найден", trader_id=trader_id)
            return False

        if copy_amount < trader.min_copy_amount:
            logger.warning(
                "Сумма ниже минимальной",
                copy_amount=copy_amount,
                min_amount=trader.min_copy_amount,
            )
            return False

        if user_id not in self._user_subscriptions:
            self._user_subscriptions[user_id] = []

        if trader_id not in self._user_subscriptions[user_id]:
            self._user_subscriptions[user_id].append(trader_id)
            trader.followers_count += 1
            logger.info(
                "Пользователь подписался на трейдера",
                user_id=user_id,
                trader_id=trader_id,
            )

        return True

    async def unsubscribe_from_trader(
        self,
        user_id: int,
        trader_id: str,
    ) -> bool:
        """
        Отписка от трейдера.
        
        Args:
            user_id: ID пользователя
            trader_id: ID трейдера
        
        Returns:
            bool: Успешность отписки
        """
        if user_id not in self._user_subscriptions:
            return False

        if trader_id in self._user_subscriptions[user_id]:
            self._user_subscriptions[user_id].remove(trader_id)
            trader = await self.get_trader(trader_id)
            if trader and trader.followers_count > 0:
                trader.followers_count -= 1
            return True

        return False

    async def get_user_subscriptions(self, user_id: int) -> List[Trader]:
        """
        Получение подписок пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            List[Trader]: Список трейдеров
        """
        if user_id not in self._user_subscriptions:
            return []

        traders = []
        for trader_id in self._user_subscriptions[user_id]:
            trader = await self.get_trader(trader_id)
            if trader:
                traders.append(trader)

        return traders

    async def format_traders_message(self) -> str:
        """
        Форматирование сообщения с топ трейдерами для Telegram.
        
        Returns:
            str: Форматированное сообщение
        """
        traders = await self.get_top_traders(sort_by="profit", limit=5)

        message = ["📊 **Copy-Trading - Топ трейдеры**\n"]
        message.append("_Копируйте сделки лучших трейдеров автоматически!_\n")

        for i, trader in enumerate(traders, 1):
            verified = "✅" if trader.is_verified else ""
            
            message.append(
                f"{i}. **{trader.name}** {verified} {trader.risk_emoji}"
            )
            message.append(f"   _{trader.description}_")
            message.append(
                f"   📈 Прибыль: +{trader.stats.total_profit_percent:.1f}% | "
                f"🎯 Win Rate: {trader.stats.win_rate:.1f}%"
            )
            message.append(
                f"   👥 Подписчики: {trader.followers_count} | "
                f"💰 Мин. сумма: ${trader.min_copy_amount:.0f}"
            )
            message.append("")

        message.append("ℹ️ **Уровни риска:**")
        message.append("🟢 Низкий | 🟡 Умеренный | 🟠 Средний | 🔴 Высокий | ⚫ Очень высокий")
        message.append(
            "\n⚠️ *Прошлые результаты не гарантируют будущей прибыли. "
            "Инвестируйте только то, что готовы потерять.*"
        )

        return "\n".join(message)

    async def format_trader_details(self, trader_id: str) -> str:
        """
        Форматирование детальной информации о трейдере.
        
        Args:
            trader_id: ID трейдера
        
        Returns:
            str: Форматированное сообщение
        """
        trader = await self.get_trader(trader_id)

        if not trader:
            return "❌ Трейдер не найден"

        verified = "✅ Верифицирован" if trader.is_verified else "❗ Не верифицирован"

        message = [
            f"👤 **{trader.name}** {trader.risk_emoji}",
            verified,
            f"\n📝 _{trader.description}_\n",
            "📊 **Статистика:**",
            f"• Всего сделок: {trader.stats.total_trades}",
            f"• Выигрышных: {trader.stats.winning_trades}",
            f"• Win Rate: {trader.stats.win_rate:.1f}%",
            f"• Общая прибыль: +{trader.stats.total_profit_percent:.1f}%",
            f"• Макс. просадка: -{trader.stats.max_drawdown:.1f}%",
            f"• Ср. длительность сделки: {trader.stats.avg_trade_duration:.1f}ч",
            f"\n👥 Подписчики: {trader.followers_count}",
            f"💰 Мин. сумма копирования: ${trader.min_copy_amount:.0f}",
            f"\n📅 Профиль создан: {trader.created_at.strftime('%d.%m.%Y')}",
        ]

        return "\n".join(message)
