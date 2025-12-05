"""
Gheezy Crypto - Единая статистика для всех сетей

Модуль для сбора и форматирования статистики по транзакциям
китов на всех поддерживаемых блокчейнах: BTC, ETH, BSC, SOL, TON.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class NetworkStats:
    """
    Статистика по транзакциям для одной сети.

    Attributes:
        network: Название сети ("BTC", "ETH", "BSC", "SOL", "TON")
        emoji: Эмодзи сети ("🟠", "🔷", "🟡", "🟣", "💎")
        transactions_24h: Количество транзакций за 24ч
        volume_24h_usd: Объём в USD за 24ч
        largest_tx_usd: Крупнейшая транзакция в USD
        largest_tx_hash: Хэш крупнейшей транзакции
        average_tx_usd: Средний размер транзакции в USD
        deposits_count: Количество депозитов на биржи
        withdrawals_count: Количество выводов с бирж
        top_transactions: Топ-10 транзакций
    """

    network: str
    emoji: str
    transactions_24h: int = 0
    volume_24h_usd: float = 0.0
    largest_tx_usd: float = 0.0
    largest_tx_hash: str = ""
    average_tx_usd: float = 0.0
    deposits_count: int = 0
    withdrawals_count: int = 0
    top_transactions: list = field(default_factory=list)
    top_from_label: str = ""
    top_to_label: str = ""

    @property
    def formatted_volume(self) -> str:
        """Форматированный объём."""
        return format_usd_amount(self.volume_24h_usd)

    @property
    def formatted_largest(self) -> str:
        """Форматированная крупнейшая транзакция."""
        return format_usd_amount(self.largest_tx_usd)

    @property
    def formatted_average(self) -> str:
        """Форматированный средний размер."""
        return format_usd_amount(self.average_tx_usd)


@dataclass
class WhaleStats:
    """
    Объединённая статистика по всем сетям.

    Собирает и агрегирует данные по всем поддерживаемым блокчейнам.
    """

    networks: dict[str, NetworkStats] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Инициализация статистики для всех сетей."""
        if not self.networks:
            self.networks = {
                "BTC": NetworkStats(network="BTC", emoji="🟠"),
                "ETH": NetworkStats(network="ETH", emoji="🔷"),
                "BSC": NetworkStats(network="BSC", emoji="🟡"),
                "SOL": NetworkStats(network="SOL", emoji="🟣"),
                "TON": NetworkStats(network="TON", emoji="💎"),
            }

    @property
    def total_transactions(self) -> int:
        """Общее количество транзакций."""
        return sum(ns.transactions_24h for ns in self.networks.values())

    @property
    def total_volume_usd(self) -> float:
        """Общий объём в USD."""
        return sum(ns.volume_24h_usd for ns in self.networks.values())

    @property
    def total_deposits(self) -> int:
        """Общее количество депозитов."""
        return sum(ns.deposits_count for ns in self.networks.values())

    @property
    def total_withdrawals(self) -> int:
        """Общее количество выводов."""
        return sum(ns.withdrawals_count for ns in self.networks.values())

    @property
    def average_tx_usd(self) -> float:
        """Средний размер транзакции."""
        if self.total_transactions == 0:
            return 0.0
        return self.total_volume_usd / self.total_transactions

    @property
    def sentiment(self) -> str:
        """Сентимент рынка на основе депозитов/выводов."""
        if self.total_withdrawals > self.total_deposits * 1.2:
            return "bullish"
        elif self.total_deposits > self.total_withdrawals * 1.2:
            return "bearish"
        return "neutral"

    def get_network_stats(self, network: str) -> Optional[NetworkStats]:
        """Получить статистику по конкретной сети."""
        return self.networks.get(network.upper())

    def update_network(self, network: str, stats: NetworkStats) -> None:
        """Обновить статистику сети."""
        self.networks[network.upper()] = stats

    def get_largest_transaction(self) -> tuple[str, float, str]:
        """Получить крупнейшую транзакцию среди всех сетей."""
        largest_network = ""
        largest_amount = 0.0
        largest_hash = ""

        for name, stats in self.networks.items():
            if stats.largest_tx_usd > largest_amount:
                largest_amount = stats.largest_tx_usd
                largest_network = name
                largest_hash = stats.largest_tx_hash

        return largest_network, largest_amount, largest_hash


def format_usd_amount(amount: float) -> str:
    """
    Форматирование суммы в USD.

    Args:
        amount: Сумма в USD

    Returns:
        str: Форматированная строка
    """
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:,.2f}B"
    elif amount >= 1_000_000:
        return f"${amount / 1_000_000:,.2f}M"
    elif amount >= 1_000:
        return f"${amount / 1_000:,.2f}K"
    else:
        return f"${amount:,.2f}"


def format_whale_stats_message(stats: WhaleStats, period: str = "24ч") -> str:
    """
    Форматирование полного сообщения статистики для Telegram.

    Args:
        stats: Статистика по всем сетям
        period: Период статистики

    Returns:
        str: Форматированное сообщение
    """
    # Определяем сентимент
    if stats.sentiment == "bullish":
        sentiment_text = "📈 *Бычий* (больше выводов с бирж)"
        sentiment_emoji = "🟢"
    elif stats.sentiment == "bearish":
        sentiment_text = "📉 *Медвежий* (больше депозитов на биржи)"
        sentiment_emoji = "🔴"
    else:
        sentiment_text = "↔️ *Нейтральный*"
        sentiment_emoji = "🟡"

    message = (
        f"📊 *WHALE СТАТИСТИКА ({period})*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{sentiment_emoji} *Сентимент:* {sentiment_text}\n\n"
    )

    # Статистика по каждой сети
    network_order = ["BTC", "ETH", "BSC", "SOL", "TON"]

    for network in network_order:
        ns = stats.networks.get(network)
        if not ns:
            continue

        # Формируем топ транзакцию
        top_tx = ""
        if ns.top_from_label or ns.top_to_label:
            from_lbl = ns.top_from_label or "Unknown"
            to_lbl = ns.top_to_label or "Unknown"
            top_tx = f"{from_lbl} → {to_lbl}"
        else:
            top_tx = "—"

        message += (
            f"{ns.emoji} *{ns.network}*\n"
            f"├ 🔢 Транзакций: *{ns.transactions_24h}*\n"
            f"├ 💰 Объём: *{ns.formatted_volume}*\n"
            f"├ 🔝 Крупнейшая: *{ns.formatted_largest}*\n"
            f"├ 📥 Депозитов: *{ns.deposits_count}*\n"
            f"├ 📤 Выводов: *{ns.withdrawals_count}*\n"
            f"└ 📍 Топ: {top_tx}\n\n"
        )

    # Общая сводка
    message += (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *ВСЕГО:* {format_usd_amount(stats.total_volume_usd)}\n"
        f"🐋 *Транзакций:* {stats.total_transactions}\n"
        f"📈 *Средняя:* {format_usd_amount(stats.average_tx_usd)}\n"
    )

    return message


def format_network_stats_message(network_stats: NetworkStats) -> str:
    """
    Форматирование сообщения статистики для одной сети.

    Args:
        network_stats: Статистика сети

    Returns:
        str: Форматированное сообщение
    """
    ns = network_stats

    # Определяем сентимент для сети
    if ns.withdrawals_count > ns.deposits_count * 1.2:
        sentiment = "📈 *Бычий* (больше выводов)"
    elif ns.deposits_count > ns.withdrawals_count * 1.2:
        sentiment = "📉 *Медвежий* (больше депозитов)"
    else:
        sentiment = "↔️ *Нейтральный*"

    message = (
        f"{ns.emoji} *{ns.network} WHALE СТАТИСТИКА*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Сентимент:* {sentiment}\n\n"
        f"🔢 Всего транзакций: *{ns.transactions_24h}*\n"
        f"💰 Общий объём: *{ns.formatted_volume}*\n"
        f"🔝 Крупнейшая TX: *{ns.formatted_largest}*\n"
        f"📈 Средняя TX: *{ns.formatted_average}*\n\n"
        f"📥 Депозиты на биржи: *{ns.deposits_count}*\n"
        f"📤 Выводы с бирж: *{ns.withdrawals_count}*\n\n"
    )

    # Топ транзакции
    if ns.top_transactions:
        message += "🔔 *Топ транзакции:*\n\n"
        for i, tx in enumerate(ns.top_transactions[:5], 1):
            amount_str = format_usd_amount(tx.get("amount_usd", 0))
            from_lbl = tx.get("from_label", "Unknown")[:15]
            to_lbl = tx.get("to_label", "Unknown")[:15]
            message += f"{i}. {amount_str}: {from_lbl} → {to_lbl}\n"

    return message


def format_top_transactions_message(
    transactions: list,
    limit: int = 10,
) -> str:
    """
    Форматирование топ транзакций всех сетей.

    Args:
        transactions: Список транзакций
        limit: Количество транзакций

    Returns:
        str: Форматированное сообщение
    """
    if not transactions:
        return (
            "🐋 *Топ транзакции*\n\n"
            "_Нет данных о транзакциях_"
        )

    # Сортируем по сумме
    sorted_txs = sorted(
        transactions,
        key=lambda x: x.get("amount_usd", 0),
        reverse=True,
    )[:limit]

    message = (
        "🐋 *ТОП ТРАНЗАКЦИИ КИТОВ*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Эмодзи для сетей
    network_emojis = {
        "BTC": "🟠",
        "Bitcoin": "🟠",
        "ETH": "🔷",
        "Ethereum": "🔷",
        "BSC": "🟡",
        "SOL": "🟣",
        "Solana": "🟣",
        "TON": "💎",
    }

    for i, tx in enumerate(sorted_txs, 1):
        network = tx.get("network", "Unknown")
        emoji = network_emojis.get(network, "💰")
        amount_str = format_usd_amount(tx.get("amount_usd", 0))
        from_lbl = tx.get("from_label") or "Unknown"
        to_lbl = tx.get("to_label") or "Unknown"

        # Определяем тип транзакции
        tx_type = tx.get("tx_type", "")
        if tx_type == "DEPOSIT":
            direction = "📥"
        elif tx_type == "WITHDRAWAL":
            direction = "📤"
        elif tx_type == "DEX_SWAP":
            direction = "🔄"
        else:
            direction = "↔️"

        message += (
            f"*{i}.* {emoji} {direction} *{amount_str}*\n"
            f"   {from_lbl} → {to_lbl}\n\n"
        )

    return message


def format_24h_summary_message(stats: WhaleStats) -> str:
    """
    Форматирование сводки за 24 часа.

    Args:
        stats: Статистика по всем сетям

    Returns:
        str: Форматированное сообщение
    """
    # Определяем сентимент
    if stats.sentiment == "bullish":
        sentiment_text = "📈 *БЫЧИЙ*"
        sentiment_desc = "Киты активно выводят с бирж — накопление!"
    elif stats.sentiment == "bearish":
        sentiment_text = "📉 *МЕДВЕЖИЙ*"
        sentiment_desc = "Киты депозитят на биржи — возможны продажи!"
    else:
        sentiment_text = "↔️ *НЕЙТРАЛЬНЫЙ*"
        sentiment_desc = "Баланс между депозитами и выводами"

    # Находим крупнейшую транзакцию
    largest_network, largest_amount, _ = stats.get_largest_transaction()
    network_emojis = {
        "BTC": "🟠", "ETH": "🔷", "BSC": "🟡", "SOL": "🟣", "TON": "💎"
    }
    largest_emoji = network_emojis.get(largest_network, "💰")

    message = (
        "🐋 *СВОДКА ЗА 24 ЧАСА*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 *Сентимент:* {sentiment_text}\n"
        f"_{sentiment_desc}_\n\n"
        f"💰 *Общий объём:* {format_usd_amount(stats.total_volume_usd)}\n"
        f"🐋 *Транзакций:* {stats.total_transactions}\n"
        f"📈 *Средняя TX:* {format_usd_amount(stats.average_tx_usd)}\n\n"
        f"📥 *Депозиты:* {stats.total_deposits}\n"
        f"📤 *Выводы:* {stats.total_withdrawals}\n\n"
        f"🏆 *Крупнейшая:* {largest_emoji} {format_usd_amount(largest_amount)}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "*По сетям:*\n\n"
    )

    # Краткая статистика по сетям
    for network in ["BTC", "ETH", "BSC", "SOL", "TON"]:
        ns = stats.networks.get(network)
        if not ns:
            continue
        message += (
            f"{ns.emoji} {ns.network}: *{ns.transactions_24h}* TX "
            f"({ns.formatted_volume})\n"
        )

    return message
