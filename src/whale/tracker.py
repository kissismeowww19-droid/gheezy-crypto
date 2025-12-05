"""
Gheezy Crypto - Трекер китов

Отслеживание крупных транзакций китов на Ethereum, BSC и Bitcoin.
Использует несколько источников данных с приоритетом:
- Etherscan/BscScan API (если есть ключи)
- Blockscout API (бесплатный)
- Публичные RPC ноды
- mempool.space / blockstream.info для Bitcoin

Особенности:
- Кэширование цен криптовалют
- Retry логика с exponential backoff
- Fallback на демо-данные (опционально, с предупреждением)
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import structlog

from config import settings
from whale.ethereum import EthereumTracker
from whale.bsc import BSCTracker
from whale.bitcoin import BitcoinTracker
from whale.known_wallets import (
    is_exchange_address,
    get_short_address,
)
from whale.alerts import (
    WhaleAlert,
    format_whale_summary,
    format_stats_message,
)

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
        return get_short_address(self.from_address)

    @property
    def short_to(self) -> str:
        """Сокращённый адрес получателя."""
        if self.to_label:
            return self.to_label
        return get_short_address(self.to_address)

    @property
    def is_exchange_deposit(self) -> bool:
        """Проверка, является ли транзакция депозитом на биржу."""
        return is_exchange_address(self.to_address, self.blockchain)

    @property
    def is_exchange_withdrawal(self) -> bool:
        """Проверка, является ли транзакция выводом с биржи."""
        return is_exchange_address(self.from_address, self.blockchain)

    def to_alert(self) -> WhaleAlert:
        """Конвертация в WhaleAlert для форматирования."""
        return WhaleAlert(
            tx_hash=self.tx_hash,
            blockchain=self.blockchain,
            token_symbol=self.token_symbol,
            amount=self.amount,
            amount_usd=self.amount_usd,
            from_address=self.from_address,
            to_address=self.to_address,
            timestamp=self.timestamp,
        )


class WhaleTracker:
    """
    Трекер крупных транзакций китов на нескольких блокчейнах.

    Отслеживает большие переводы на Ethereum, BSC и Bitcoin.

    Источники данных (в порядке приоритета):
    - Ethereum: Etherscan API → Blockscout API → Публичные RPC
    - BSC: BscScan API → Публичные RPC
    - Bitcoin: mempool.space → blockstream.info

    Все источники работают в России без VPN.

    Настройки:
    - WHALE_MIN_TRANSACTION: минимальная сумма транзакции в USD
    - WHALE_USE_DEMO_DATA: использовать демо-данные если API недоступны
    - WHALE_BLOCKS_TO_ANALYZE: количество блоков для анализа
    """

    def __init__(self):
        """Инициализация трекера."""
        self.min_transaction = settings.whale_min_transaction
        self.check_interval = getattr(settings, "whale_check_interval", 60)
        self.use_demo_data = getattr(settings, "whale_use_demo_data", False)

        # Инициализация трекеров для каждого блокчейна
        self._eth_tracker = EthereumTracker()
        self._bsc_tracker = BSCTracker()
        self._btc_tracker = BitcoinTracker()

        # Кэш последних транзакций
        self._last_transactions: list[WhaleTransaction] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

        logger.info(
            "WhaleTracker инициализирован",
            min_transaction_usd=self.min_transaction,
            check_interval=self.check_interval,
            use_demo_data=self.use_demo_data,
            etherscan_key="настроен" if settings.etherscan_api_key else "не настроен",
            bscscan_key="настроен" if settings.bscscan_api_key else "не настроен",
        )

    async def close(self) -> None:
        """Закрытие всех HTTP сессий."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self._eth_tracker.close()
        await self._bsc_tracker.close()
        await self._btc_tracker.close()

    async def start(self) -> None:
        """Запуск периодического мониторинга."""
        if self._running:
            logger.warning("Whale tracker уже запущен")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info(
            "Whale tracker запущен",
            interval=self.check_interval,
            min_usd=self.min_transaction,
            demo_mode=self.use_demo_data,
        )

    async def stop(self) -> None:
        """Остановка мониторинга."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Whale tracker остановлен")

    async def _monitoring_loop(self) -> None:
        """Цикл мониторинга транзакций."""
        while self._running:
            try:
                transactions = await self.get_all_transactions()
                self._last_transactions = transactions
                logger.info(
                    "Проверка китов завершена",
                    total=len(transactions),
                    eth=len([t for t in transactions if t.blockchain == "Ethereum"]),
                    bsc=len([t for t in transactions if t.blockchain == "BSC"]),
                    btc=len([t for t in transactions if t.blockchain == "Bitcoin"]),
                )
            except Exception as e:
                logger.error(
                    "Ошибка мониторинга",
                    error=str(e),
                )

            await asyncio.sleep(self.check_interval)

    async def get_ethereum_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение крупных ETH транзакций.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Список транзакций
        """
        try:
            eth_txs = await self._eth_tracker.get_large_transactions(limit=limit)

            transactions = []
            for tx in eth_txs:
                transactions.append(
                    WhaleTransaction(
                        tx_hash=tx.tx_hash,
                        blockchain="Ethereum",
                        token_symbol=tx.token_symbol,
                        amount=tx.value_eth,
                        amount_usd=tx.value_usd,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        from_label=tx.from_label,
                        to_label=tx.to_label,
                        timestamp=tx.timestamp,
                    )
                )

            logger.debug(
                "Получены ETH транзакции",
                count=len(transactions),
            )
            return transactions

        except Exception as e:
            logger.error(
                "Ошибка Ethereum трекера",
                error=str(e),
            )
            return []

    async def get_bsc_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение крупных BSC транзакций.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Список транзакций
        """
        try:
            bsc_txs = await self._bsc_tracker.get_large_transactions(limit=limit)

            transactions = []
            for tx in bsc_txs:
                transactions.append(
                    WhaleTransaction(
                        tx_hash=tx.tx_hash,
                        blockchain="BSC",
                        token_symbol=tx.token_symbol,
                        amount=tx.value_bnb,
                        amount_usd=tx.value_usd,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        from_label=tx.from_label,
                        to_label=tx.to_label,
                        timestamp=tx.timestamp,
                    )
                )

            logger.debug(
                "Получены BSC транзакции",
                count=len(transactions),
            )
            return transactions

        except Exception as e:
            logger.error(
                "Ошибка BSC трекера",
                error=str(e),
            )
            return []

    async def get_bitcoin_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение крупных BTC транзакций.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Список транзакций
        """
        try:
            btc_txs = await self._btc_tracker.get_large_transactions(limit=limit)

            transactions = []
            for tx in btc_txs:
                transactions.append(
                    WhaleTransaction(
                        tx_hash=tx.tx_hash,
                        blockchain="Bitcoin",
                        token_symbol="BTC",
                        amount=tx.value_btc,
                        amount_usd=tx.value_usd,
                        from_address=tx.primary_from,
                        to_address=tx.primary_to,
                        from_label=tx.from_label,
                        to_label=tx.to_label,
                        timestamp=tx.timestamp,
                    )
                )

            logger.debug(
                "Получены BTC транзакции",
                count=len(transactions),
            )
            return transactions

        except Exception as e:
            logger.error(
                "Ошибка Bitcoin трекера",
                error=str(e),
            )
            return []

    async def get_all_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение транзакций со всех блокчейнов.

        Если реальные данные недоступны и включен режим демо-данных,
        возвращает демо-транзакции с предупреждением.

        Args:
            limit: Максимальное количество транзакций на блокчейн

        Returns:
            list[WhaleTransaction]: Список всех транзакций
        """
        # Запускаем все запросы параллельно
        eth_task = self.get_ethereum_transactions(limit=limit)
        bsc_task = self.get_bsc_transactions(limit=limit)
        btc_task = self.get_bitcoin_transactions(limit=limit)

        results = await asyncio.gather(
            eth_task, bsc_task, btc_task,
            return_exceptions=True
        )

        all_transactions = []
        for result in results:
            if isinstance(result, list):
                all_transactions.extend(result)
            elif isinstance(result, Exception):
                logger.error(
                    "Ошибка получения транзакций",
                    error=str(result),
                )

        # Если нет реальных данных и включен демо-режим
        if not all_transactions and self.use_demo_data:
            logger.warning(
                "⚠️ ВНИМАНИЕ: Используются демо-данные! "
                "Реальные API недоступны или не настроены. "
                "Установите WHALE_USE_DEMO_DATA=false для отключения."
            )
            return await self._get_demo_transactions()

        # Сортируем по времени
        all_transactions.sort(
            key=lambda x: x.timestamp if x.timestamp else datetime.now(),
            reverse=True,
        )

        return all_transactions

    async def get_transactions_by_blockchain(
        self,
        blockchain: str,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение транзакций для конкретного блокчейна.

        Args:
            blockchain: Название блокчейна (eth, bsc, btc)
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Список транзакций
        """
        blockchain_lower = blockchain.lower()

        if blockchain_lower in ("eth", "ethereum"):
            return await self.get_ethereum_transactions(limit=limit)
        elif blockchain_lower in ("bsc", "bnb", "binance"):
            return await self.get_bsc_transactions(limit=limit)
        elif blockchain_lower in ("btc", "bitcoin"):
            return await self.get_bitcoin_transactions(limit=limit)
        else:
            logger.warning(f"Unknown blockchain: {blockchain}")
            return []

    async def analyze_whale_activity(
        self,
        blockchain: Optional[str] = None,
    ) -> dict:
        """
        Анализ активности китов.

        Args:
            blockchain: Блокчейн для анализа (None для всех)

        Returns:
            dict: Статистика по активности китов
        """
        if blockchain:
            transactions = await self.get_transactions_by_blockchain(blockchain)
        else:
            transactions = await self.get_all_transactions()

        deposits = sum(1 for tx in transactions if tx.is_exchange_deposit)
        withdrawals = sum(1 for tx in transactions if tx.is_exchange_withdrawal)
        total_volume = sum(tx.amount_usd for tx in transactions)

        eth_count = len([tx for tx in transactions if tx.blockchain == "Ethereum"])
        bsc_count = len([tx for tx in transactions if tx.blockchain == "BSC"])
        btc_count = len([tx for tx in transactions if tx.blockchain == "Bitcoin"])

        return {
            "total_transactions": len(transactions),
            "exchange_deposits": deposits,
            "exchange_withdrawals": withdrawals,
            "total_volume_usd": total_volume,
            "eth_transactions": eth_count,
            "bsc_transactions": bsc_count,
            "btc_transactions": btc_count,
            "sentiment": "bearish" if deposits > withdrawals else "bullish",
        }

    async def format_whale_message(
        self,
        blockchain: Optional[str] = None,
    ) -> str:
        """
        Форматирование сообщения о движениях китов для Telegram.

        Args:
            blockchain: Блокчейн для отображения (None для всех)

        Returns:
            str: Форматированное сообщение
        """
        if blockchain:
            transactions = await self.get_transactions_by_blockchain(blockchain, limit=10)
        else:
            transactions = await self.get_all_transactions(limit=10)

        # Конвертируем в WhaleAlert для форматирования
        alerts = [tx.to_alert() for tx in transactions]

        return format_whale_summary(alerts, period="последний час")

    async def format_stats_message(self) -> str:
        """
        Форматирование сообщения со статистикой.

        Returns:
            str: Форматированное сообщение статистики
        """
        analysis = await self.analyze_whale_activity()

        return format_stats_message(
            total_transactions=analysis["total_transactions"],
            total_volume_usd=analysis["total_volume_usd"],
            deposits=analysis["exchange_deposits"],
            withdrawals=analysis["exchange_withdrawals"],
            eth_transactions=analysis["eth_transactions"],
            bsc_transactions=analysis["bsc_transactions"],
            btc_transactions=analysis["btc_transactions"],
        )

    def get_last_transactions(self) -> list[WhaleTransaction]:
        """
        Получение последних закэшированных транзакций.

        Returns:
            list[WhaleTransaction]: Список последних транзакций
        """
        return self._last_transactions

    # Обратная совместимость со старым API
    async def get_large_eth_transfers(
        self,
        min_value_eth: float = 1000,
        limit: int = 10,
    ) -> list[WhaleTransaction]:
        """
        Получение крупных ETH переводов (для обратной совместимости).

        Args:
            min_value_eth: Минимальное значение в ETH (игнорируется)
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Список транзакций
        """
        return await self.get_ethereum_transactions(limit=limit)

    async def _get_demo_transactions(self) -> list[WhaleTransaction]:
        """
        Получение демо-транзакций для отображения функционала.

        Returns:
            list[WhaleTransaction]: Список демо-транзакций
        """
        # Ethereum/BSC tx hashes are 64 hex chars (66 with 0x prefix)
        # Bitcoin tx hashes are 64 hex chars
        # Demo hashes use padding to match realistic lengths
        demo_data = [
            WhaleTransaction(
                tx_hash="0xdemo1" + "a" * 58,  # 64 chars total (ETH format)
                blockchain="Ethereum",
                token_symbol="ETH",
                amount=5000,
                amount_usd=10_000_000,
                from_address="0x1234567890abcdef1234567890abcdef12345678",
                to_address="0x28c6c06298d514db089934071355e5743bf21d60",
                from_label=None,
                to_label="Binance",
                timestamp=datetime.now(),
                tx_type="deposit",
            ),
            WhaleTransaction(
                tx_hash="0xdemo2" + "b" * 58,  # 64 chars total (BSC format)
                blockchain="BSC",
                token_symbol="BNB",
                amount=30000,
                amount_usd=9_000_000,
                from_address="0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43",
                to_address="0x2345678901abcdef2345678901abcdef23456789",
                from_label="Coinbase",
                to_label=None,
                timestamp=datetime.now(),
                tx_type="withdrawal",
            ),
            WhaleTransaction(
                tx_hash="demo3" + "c" * 59,  # 64 chars total (BTC format)
                blockchain="Bitcoin",
                token_symbol="BTC",
                amount=500,
                amount_usd=20_000_000,
                from_address="bc1qxyz1234567890abcdef1234567890abcdef",
                to_address="34xp4vrocgjym3xr7ycvpfhocnxv4twseo",
                from_label="Unknown Whale",
                to_label="Binance",
                timestamp=datetime.now(),
                tx_type="deposit",
            ),
        ]
        return demo_data
