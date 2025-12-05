"""
Gheezy Crypto - Система оповещений о транзакциях китов

Формирование сообщений для Telegram с полным анализом и рекомендациями.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from whale.known_wallets import (
    get_wallet_label,
    is_exchange_address,
    get_short_address,
)


@dataclass
class WhaleAlert:
    """
    Данные для формирования оповещения о транзакции кита.

    Attributes:
        tx_hash: Хэш транзакции
        blockchain: Название блокчейна
        token_symbol: Символ токена
        amount: Количество токенов
        amount_usd: Сумма в USD
        from_address: Адрес отправителя
        to_address: Адрес получателя
        timestamp: Время транзакции
    """

    tx_hash: str
    blockchain: str
    token_symbol: str
    amount: float
    amount_usd: float
    from_address: str
    to_address: str
    timestamp: Optional[datetime] = None

    @property
    def from_label(self) -> Optional[str]:
        """Метка отправителя."""
        return get_wallet_label(self.from_address, self.blockchain)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_wallet_label(self.to_address, self.blockchain)

    @property
    def is_exchange_deposit(self) -> bool:
        """Является ли транзакция депозитом на биржу."""
        return is_exchange_address(self.to_address, self.blockchain)

    @property
    def is_exchange_withdrawal(self) -> bool:
        """Является ли транзакция выводом с биржи."""
        return is_exchange_address(self.from_address, self.blockchain)


def format_amount(amount: float, symbol: str) -> str:
    """
    Форматирование суммы токенов.

    Args:
        amount: Количество токенов
        symbol: Символ токена

    Returns:
        str: Форматированная строка
    """
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:,.2f}M {symbol}"
    elif amount >= 1_000:
        return f"{amount / 1_000:,.2f}K {symbol}"
    elif amount >= 1:
        return f"{amount:,.2f} {symbol}"
    else:
        return f"{amount:.6f} {symbol}"


def format_usd(amount_usd: float) -> str:
    """
    Форматирование суммы в USD.

    Args:
        amount_usd: Сумма в USD

    Returns:
        str: Форматированная строка
    """
    if amount_usd >= 1_000_000_000:
        return f"${amount_usd / 1_000_000_000:,.2f}B"
    elif amount_usd >= 1_000_000:
        return f"${amount_usd / 1_000_000:,.2f}M"
    elif amount_usd >= 1_000:
        return f"${amount_usd / 1_000:,.2f}K"
    else:
        return f"${amount_usd:,.2f}"


def get_blockchain_explorer_url(tx_hash: str, blockchain: str) -> str:
    """
    Получить ссылку на транзакцию в блокчейн-эксплорере.

    Args:
        tx_hash: Хэш транзакции
        blockchain: Название блокчейна

    Returns:
        str: URL транзакции
    """
    blockchain_lower = blockchain.lower()
    if blockchain_lower in ("ethereum", "eth"):
        return f"https://etherscan.io/tx/{tx_hash}"
    elif blockchain_lower in ("bsc", "bnb", "binance"):
        return f"https://bscscan.com/tx/{tx_hash}"
    elif blockchain_lower in ("bitcoin", "btc"):
        return f"https://blockchair.com/bitcoin/transaction/{tx_hash}"
    elif blockchain_lower in ("solana", "sol"):
        return f"https://solscan.io/tx/{tx_hash}"
    elif blockchain_lower == "ton":
        return f"https://tonviewer.com/transaction/{tx_hash}"
    return f"https://blockchair.com/{blockchain_lower}/transaction/{tx_hash}"


def get_blockchain_emoji(blockchain: str) -> str:
    """
    Получить эмодзи для блокчейна.

    Args:
        blockchain: Название блокчейна

    Returns:
        str: Эмодзи блокчейна
    """
    blockchain_lower = blockchain.lower()
    emojis = {
        "ethereum": "🔷",
        "eth": "🔷",
        "bsc": "🟡",
        "bnb": "🟡",
        "binance": "🟡",
        "bitcoin": "🟠",
        "btc": "🟠",
        "solana": "🟣",
        "sol": "🟣",
        "ton": "💎",
    }
    return emojis.get(blockchain_lower, "💰")


def analyze_transaction(alert: WhaleAlert) -> tuple[str, str]:
    """
    Анализ транзакции и формирование рекомендации.

    Args:
        alert: Данные транзакции

    Returns:
        tuple: (анализ, рекомендация)
    """
    analysis = ""
    recommendation = ""

    if alert.is_exchange_deposit:
        analysis = "📥 Депозит на биржу"
        if alert.amount_usd >= 10_000_000:
            recommendation = (
                "⚠️ *ВНИМАНИЕ!* Крупный депозит на биржу!\n"
                "Возможна продажа. Следите за ценой."
            )
        else:
            recommendation = (
                "⚠️ Возможная продажа!\n"
                "Кит может планировать продажу."
            )
    elif alert.is_exchange_withdrawal:
        analysis = "📤 Вывод с биржи"
        if alert.amount_usd >= 10_000_000:
            recommendation = (
                "🟢 *ПОЗИТИВНО!* Крупный вывод с биржи!\n"
                "Кит выводит на холодное хранение."
            )
        else:
            recommendation = (
                "🟢 Позитивный сигнал!\n"
                "Кит накапливает на долгосрочное хранение."
            )
    else:
        analysis = "↔️ Перевод между кошельками"
        if alert.from_label and "Foundation" in alert.from_label:
            recommendation = (
                "ℹ️ Информация\n"
                "Перемещение средств фонда. Следите за новостями."
            )
        elif alert.amount_usd >= 50_000_000:
            recommendation = (
                "👀 Внимание!\n"
                "Крупное перемещение средств. Возможна подготовка к продаже."
            )
        else:
            recommendation = (
                "ℹ️ Информация\n"
                "Перемещение между кошельками кита."
            )

    return analysis, recommendation


def format_whale_alert_message(alert: WhaleAlert) -> str:
    """
    Форматирование полного сообщения об оповещении для Telegram.

    Args:
        alert: Данные транзакции кита

    Returns:
        str: Форматированное сообщение для Telegram
    """
    blockchain_emoji = get_blockchain_emoji(alert.blockchain)
    amount_str = format_amount(alert.amount, alert.token_symbol)
    usd_str = format_usd(alert.amount_usd)

    # Определяем отправителя
    from_display = alert.from_label if alert.from_label else "Unknown Wallet"
    from_addr_short = get_short_address(alert.from_address)

    # Определяем получателя
    to_display = alert.to_label if alert.to_label else "Unknown Wallet"
    to_addr_short = get_short_address(alert.to_address)

    # Анализ и рекомендация
    analysis, recommendation = analyze_transaction(alert)

    # Ссылка на транзакцию
    tx_url = get_blockchain_explorer_url(alert.tx_hash, alert.blockchain)

    # Время транзакции
    time_str = ""
    if alert.timestamp:
        time_str = alert.timestamp.strftime("%H:%M:%S %d.%m.%Y")
    else:
        time_str = datetime.now().strftime("%H:%M:%S %d.%m.%Y")

    message = (
        f"🐋 *WHALE ALERT!* {blockchain_emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *Сумма:* {amount_str} ({usd_str})\n\n"
        f"📤 *Отправитель:* {from_display}\n"
        f"   `{from_addr_short}`\n\n"
        f"📥 *Получатель:* {to_display}\n"
        f"   `{to_addr_short}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Анализ:* {analysis}\n\n"
        f"{recommendation}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 [Посмотреть транзакцию]({tx_url})\n"
        f"⏰ {time_str}"
    )

    return message


def format_whale_summary(alerts: list[WhaleAlert], period: str = "24ч") -> str:
    """
    Форматирование сводки по транзакциям китов.

    Args:
        alerts: Список транзакций
        period: Период сводки

    Returns:
        str: Форматированное сообщение сводки
    """
    if not alerts:
        return (
            "🐋 *Whale Tracker*\n\n"
            "📊 Нет крупных транзакций за указанный период."
        )

    total_volume = sum(a.amount_usd for a in alerts)
    deposits = [a for a in alerts if a.is_exchange_deposit]
    withdrawals = [a for a in alerts if a.is_exchange_withdrawal]
    transfers = [
        a for a in alerts
        if not a.is_exchange_deposit and not a.is_exchange_withdrawal
    ]

    # Определяем сентимент
    deposit_volume = sum(a.amount_usd for a in deposits)
    withdrawal_volume = sum(a.amount_usd for a in withdrawals)

    if withdrawal_volume > deposit_volume * 1.2:
        sentiment = "📈 *Бычий* (больше выводов с бирж)"
        sentiment_emoji = "🟢"
    elif deposit_volume > withdrawal_volume * 1.2:
        sentiment = "📉 *Медвежий* (больше депозитов на биржи)"
        sentiment_emoji = "🔴"
    else:
        sentiment = "↔️ *Нейтральный*"
        sentiment_emoji = "🟡"

    # Статистика по блокчейнам
    eth_count = len([a for a in alerts if a.blockchain.lower() in ("ethereum", "eth")])
    bsc_count = len([a for a in alerts if a.blockchain.lower() in ("bsc", "bnb")])
    btc_count = len([a for a in alerts if a.blockchain.lower() in ("bitcoin", "btc")])
    sol_count = len([a for a in alerts if a.blockchain.lower() in ("solana", "sol")])
    ton_count = len([a for a in alerts if a.blockchain.lower() == "ton"])

    message = (
        f"🐋 *Whale Tracker - Сводка за {period}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{sentiment_emoji} *Сентимент:* {sentiment}\n\n"
        f"📊 *Статистика:*\n"
        f"• Всего транзакций: *{len(alerts)}*\n"
        f"• Общий объём: *{format_usd(total_volume)}*\n"
        f"• Депозиты на биржи: *{len(deposits)}* ({format_usd(deposit_volume)})\n"
        f"• Выводы с бирж: *{len(withdrawals)}* ({format_usd(withdrawal_volume)})\n"
        f"• Переводы: *{len(transfers)}*\n\n"
        f"🔗 *По блокчейнам:*\n"
        f"• 🟠 Bitcoin: *{btc_count}*\n"
        f"• 🔷 Ethereum: *{eth_count}*\n"
        f"• 🟡 BSC: *{bsc_count}*\n"
        f"• 🟣 Solana: *{sol_count}*\n"
        f"• 💎 TON: *{ton_count}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    )

    # Последние 5 транзакций
    recent = sorted(
        alerts,
        key=lambda x: x.timestamp if x.timestamp else datetime.now(),
        reverse=True
    )[:5]

    if recent:
        message += "*🔔 Последние транзакции:*\n\n"
        for alert in recent:
            emoji = get_blockchain_emoji(alert.blockchain)
            direction = "📥" if alert.is_exchange_deposit else (
                "📤" if alert.is_exchange_withdrawal else "↔️"
            )
            message += (
                f"{emoji} {direction} "
                f"*{format_amount(alert.amount, alert.token_symbol)}* "
                f"({format_usd(alert.amount_usd)})\n"
            )

    message += (
        "\n💡 _Депозиты на биржи могут указывать на намерение продать. "
        "Выводы — на долгосрочное хранение._"
    )

    return message


def format_stats_message(
    total_transactions: int,
    total_volume_usd: float,
    deposits: int,
    withdrawals: int,
    eth_transactions: int,
    bsc_transactions: int,
    btc_transactions: int,
    sol_transactions: int = 0,
    ton_transactions: int = 0,
) -> str:
    """
    Форматирование сообщения со статистикой.

    Args:
        total_transactions: Общее количество транзакций
        total_volume_usd: Общий объём в USD
        deposits: Количество депозитов на биржи
        withdrawals: Количество выводов с бирж
        eth_transactions: Количество ETH транзакций
        bsc_transactions: Количество BSC транзакций
        btc_transactions: Количество BTC транзакций
        sol_transactions: Количество SOL транзакций
        ton_transactions: Количество TON транзакций

    Returns:
        str: Форматированное сообщение статистики
    """
    return (
        "🐋 *Whale Tracker - Статистика за день*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Общая статистика:*\n"
        f"• Всего транзакций: *{total_transactions}*\n"
        f"• Общий объём: *{format_usd(total_volume_usd)}*\n\n"
        f"📈 *Движения:*\n"
        f"• 📥 Депозиты на биржи: *{deposits}*\n"
        f"• 📤 Выводы с бирж: *{withdrawals}*\n\n"
        f"🔗 *По блокчейнам:*\n"
        f"• 🟠 Bitcoin: *{btc_transactions}*\n"
        f"• 🔷 Ethereum: *{eth_transactions}*\n"
        f"• 🟡 BSC: *{bsc_transactions}*\n"
        f"• 🟣 Solana: *{sol_transactions}*\n"
        f"• 💎 TON: *{ton_transactions}*\n"
    )
