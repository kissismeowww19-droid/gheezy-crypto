"""
Gheezy Crypto - Трекер китов

Отслеживание крупных транзакций китов на блокчейне.
Использует публичные API для мониторинга.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import aiohttp
import structlog

from src.config import settings

logger = structlog.get_logger()


@dataclass
class WhaleTransaction:
    """
    Транзакция кита.

    Attributes:
        tx_hash: Хэш транзакции
        blockchain: Название блокчейна
        token_symbol: Символ токена
        amount: Количество токенов
        amount_usd: Сумма в USD
        from_address: Адрес отправителя
        to_address: Адрес получателя
        from_label: Метка отправителя (если известна)
        to_label: Метка получателя (если известна)
        timestamp: Время транзакции
        tx_type: Тип транзакции
    """

    tx_hash: str
    blockchain: str
    token_symbol: str
    amount: float
    amount_usd: float
    from_address: str
    to_address: str
    from_label: Optional[str] = None
    to_label: Optional[str] = None
    timestamp: Optional[datetime] = None
    tx_type: Optional[str] = None

    @property
    def formatted_amount(self) -> str:
        """Форматированное количество токенов."""
        if self.amount >= 1_000_000:
            return f"{self.amount / 1_000_000:.2f}M"
        elif self.amount >= 1_000:
            return f"{self.amount / 1_000:.2f}K"
        return f"{self.amount:.4f}"

    @property
    def formatted_usd(self) -> str:
        """Форматированная сумма в USD."""
        if self.amount_usd >= 1_000_000_000:
            return f"${self.amount_usd / 1_000_000_000:.2f}B"
        elif self.amount_usd >= 1_000_000:
            return f"${self.amount_usd / 1_000_000:.2f}M"
        elif self.amount_usd >= 1_000:
            return f"${self.amount_usd / 1_000:.2f}K"
        return f"${self.amount_usd:.2f}"

    @property
    def short_from(self) -> str:
        """Сокращённый адрес отправителя."""
        if self.from_label:
            return self.from_label
        return f"{self.from_address[:8]}...{self.from_address[-6:]}"

    @property
    def short_to(self) -> str:
        """Сокращённый адрес получателя."""
        if self.to_label:
            return self.to_label
        return f"{self.to_address[:8]}...{self.to_address[-6:]}"

    @property
    def is_exchange_deposit(self) -> bool:
        """Проверка, является ли транзакция депозитом на биржу."""
        exchange_keywords = ["binance", "coinbase", "kraken", "okx", "kucoin", "ftx"]
        to_lower = (self.to_label or "").lower()
        return any(ex in to_lower for ex in exchange_keywords)

    @property
    def is_exchange_withdrawal(self) -> bool:
        """Проверка, является ли транзакция выводом с биржи."""
        exchange_keywords = ["binance", "coinbase", "kraken", "okx", "kucoin", "ftx"]
        from_lower = (self.from_label or "").lower()
        return any(ex in from_lower for ex in exchange_keywords)


class WhaleTracker:
    """
    Трекер крупных транзакций китов.

    Отслеживает большие переводы криптовалют
    и определяет их потенциальное влияние на рынок.
    """

    # Известные адреса бирж (сокращённый список)
    KNOWN_EXCHANGES = {
        "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
        "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
        "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance",
        "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance",
        "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
        "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase",
        "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase",
        "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": "Kraken",
        "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken",
    }

    def __init__(self):
        """Инициализация трекера."""
        self.min_transaction = settings.whale_min_transaction
        self.etherscan_api_key = settings.etherscan_api_key
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение HTTP сессии."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Закрытие HTTP сессии."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_address_label(self, address: str) -> Optional[str]:
        """
        Получение метки для известного адреса.

        Args:
            address: Адрес кошелька

        Returns:
            str: Метка адреса или None
        """
        return self.KNOWN_EXCHANGES.get(address.lower())

    async def get_large_eth_transfers(
        self,
        min_value_eth: float = 1000,
        limit: int = 10,
    ) -> List[WhaleTransaction]:
        """
        Получение крупных ETH переводов через Etherscan.

        Args:
            min_value_eth: Минимальное значение в ETH
            limit: Максимальное количество транзакций

        Returns:
            List[WhaleTransaction]: Список транзакций
        """
        if not self.etherscan_api_key:
            logger.warning("API ключ Etherscan не настроен")
            return await self._get_demo_transactions()

        try:
            session = await self._get_session()

            # Получаем последние блоки
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "txlist",
                "address": "0x0000000000000000000000000000000000000000",
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": 100,
                "sort": "desc",
                "apikey": self.etherscan_api_key,
            }

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error("Ошибка Etherscan API", status=response.status)
                    return await self._get_demo_transactions()

                data = await response.json()

                if data.get("status") != "1":
                    return await self._get_demo_transactions()

                transactions = []
                for tx in data.get("result", []):
                    value_wei = int(tx.get("value", 0))
                    value_eth = value_wei / 10**18

                    if value_eth < min_value_eth:
                        continue

                    from_addr = tx.get("from", "")
                    to_addr = tx.get("to", "")

                    transactions.append(
                        WhaleTransaction(
                            tx_hash=tx.get("hash", ""),
                            blockchain="Ethereum",
                            token_symbol="ETH",
                            amount=value_eth,
                            amount_usd=value_eth * 2000,  # Примерная цена
                            from_address=from_addr,
                            to_address=to_addr,
                            from_label=self._get_address_label(from_addr),
                            to_label=self._get_address_label(to_addr),
                            timestamp=datetime.fromtimestamp(
                                int(tx.get("timeStamp", 0))
                            ),
                        )
                    )

                    if len(transactions) >= limit:
                        break

                return transactions

        except Exception as e:
            logger.error("Ошибка при получении транзакций", error=str(e))
            return await self._get_demo_transactions()

    async def _get_demo_transactions(self) -> List[WhaleTransaction]:
        """
        Получение демо-транзакций для отображения функционала.

        Returns:
            List[WhaleTransaction]: Список демо-транзакций
        """
        # Демо данные для демонстрации функционала
        demo_data = [
            WhaleTransaction(
                tx_hash="0xdemo1..." + "a" * 54,
                blockchain="Ethereum",
                token_symbol="ETH",
                amount=5000,
                amount_usd=10_000_000,
                from_address="0x1234...5678",
                to_address="0xabcd...efgh",
                from_label=None,
                to_label="Binance",
                timestamp=datetime.now(),
                tx_type="deposit",
            ),
            WhaleTransaction(
                tx_hash="0xdemo2..." + "b" * 54,
                blockchain="Ethereum",
                token_symbol="USDT",
                amount=15_000_000,
                amount_usd=15_000_000,
                from_address="0x2345...6789",
                to_address="0xbcde...fghi",
                from_label="Coinbase",
                to_label=None,
                timestamp=datetime.now(),
                tx_type="withdrawal",
            ),
            WhaleTransaction(
                tx_hash="0xdemo3..." + "c" * 54,
                blockchain="Bitcoin",
                token_symbol="BTC",
                amount=500,
                amount_usd=20_000_000,
                from_address="bc1q...xyz",
                to_address="bc1q...abc",
                from_label="Unknown Whale",
                to_label="Kraken",
                timestamp=datetime.now(),
                tx_type="deposit",
            ),
        ]
        return demo_data

    async def analyze_whale_activity(self) -> dict:
        """
        Анализ активности китов.

        Returns:
            dict: Статистика по активности китов
        """
        transactions = await self.get_large_eth_transfers()

        deposits = sum(1 for tx in transactions if tx.is_exchange_deposit)
        withdrawals = sum(1 for tx in transactions if tx.is_exchange_withdrawal)
        total_volume = sum(tx.amount_usd for tx in transactions)

        return {
            "total_transactions": len(transactions),
            "exchange_deposits": deposits,
            "exchange_withdrawals": withdrawals,
            "total_volume_usd": total_volume,
            "sentiment": "bearish" if deposits > withdrawals else "bullish",
        }

    async def format_whale_message(self) -> str:
        """
        Форматирование сообщения о движениях китов для Telegram.

        Returns:
            str: Форматированное сообщение
        """
        transactions = await self.get_large_eth_transfers(limit=5)
        analysis = await self.analyze_whale_activity()

        message = ["🐋 **Whale Tracker - Крупные движения**\n"]

        # Сентимент
        if analysis["sentiment"] == "bullish":
            message.append("📈 **Сентимент: Бычий** (больше выводов с бирж)\n")
        else:
            message.append("📉 **Сентимент: Медвежий** (больше депозитов на биржи)\n")

        # Статистика
        message.append("📊 **Статистика:**")
        message.append(f"• Всего транзакций: {analysis['total_transactions']}")
        message.append(f"• Депозиты на биржи: {analysis['exchange_deposits']}")
        message.append(f"• Выводы с бирж: {analysis['exchange_withdrawals']}")

        total_vol = analysis["total_volume_usd"]
        if total_vol >= 1_000_000:
            message.append(f"• Общий объём: ${total_vol / 1_000_000:.2f}M\n")
        else:
            message.append(f"• Общий объём: ${total_vol:,.0f}\n")

        # Последние транзакции
        message.append("🔔 **Последние крупные переводы:**\n")
        for tx in transactions[:5]:
            direction = "➡️"
            if tx.is_exchange_deposit:
                direction = "📥"  # На биржу
            elif tx.is_exchange_withdrawal:
                direction = "📤"  # С биржи

            message.append(
                f"{direction} **{tx.token_symbol}** {tx.formatted_amount} "
                f"({tx.formatted_usd})"
            )
            message.append(f"   От: {tx.short_from} → К: {tx.short_to}")

        message.append(
            "\n💡 *Депозиты на биржи могут указывать на намерение продать. "
            "Выводы — на долгосрочное хранение.*"
        )

        return "\n".join(message)
