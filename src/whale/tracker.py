"""
Gheezy Crypto - Трекер китов

Отслеживание крупных транзакций китов на 7 блокчейнах:
- Ethereum (Etherscan V2)
- Bitcoin (mempool.space - no key needed)
- BSC (Free public RPC with rotation - no key needed)
- Arbitrum (Etherscan V2)
- Polygon (Etherscan V2 with delay)
- Avalanche (Snowtrace - no key needed)
- TON (TON Center API - no key needed)

Removed chains (API issues):
- Base (chainid=8453 requires paid Etherscan plan)
- SOL (Solscan returns 404)

Использует несколько источников данных с приоритетом:
- Etherscan V2 API (3 ключа с ротацией для ETH, Arbitrum, Polygon)
- Snowtrace API (бесплатный для Avalanche)
- mempool.space для Bitcoin
- Публичные RPC ноды для BSC (ротация 5 endpoints)

Особенности:
- Ротация 3 API ключей Etherscan (9 req/sec вместо 3)
- Ротация 5 RPC endpoints для BSC с автоматическим failover
- Кэширование транзакций (последние 1000, TTL 1 час)
- Кэширование цен криптовалют
- Retry логика с exponential backoff
- Параллельные запросы ко всем сетям
- Единая статистика по всем сетям
- DeFi трекинг (Uniswap, Aave, Lido)
- SQLite база данных для сохранения транзакций
"""

import asyncio
import time as time_module
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import structlog

from config import settings
from database.whale_db import init_whale_db, save_transaction
from whale.ethereum import EthereumTracker
from whale.bitcoin import BitcoinTracker
from whale.bsc import BSCTracker
# New chain trackers using Etherscan V2
from whale.arbitrum import ArbitrumTracker
from whale.polygon import PolygonTracker
from whale.avalanche import AvalancheTracker
# Base chain removed - requires paid Etherscan plan
# TON tracker
from whale.ton import TONTracker
# DeFi tracker
from whale.defi import DeFiTracker
# Transaction cache
from whale.cache import get_transaction_cache
from whale.known_wallets import (
    is_exchange_address,
    get_short_address,
)
from whale.alerts import (
    WhaleAlert,
    format_whale_summary,
    format_stats_message,
)
from whale.stats import (
    WhaleStats,
    NetworkStats,
    format_whale_stats_message,
    format_network_stats_message,
    format_top_transactions_message,
    format_24h_summary_message,
    format_db_stats_message,
)
from whale.whale_cache import get_whale_cache
from database.whale_db import (
    get_transactions as get_db_transactions,
    get_multi_period_stats,
    get_transaction_count,
)

logger = structlog.get_logger()

# Network priority order (fastest first)
NETWORK_PRIORITY = ["btc", "avax", "bsc", "eth", "arb", "polygon", "ton"]

# Timeouts per network
NETWORK_TIMEOUTS = {
    "btc": 8,
    "avax": 10,
    "bsc": 10,
    "eth": 12,
    "arb": 10,
    "polygon": 10,
    "ton": 12,
}


class TransactionType(str, Enum):
    """Типы транзакций."""
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    EXCHANGE_TRANSFER = "EXCHANGE_TRANSFER"
    WHALE_TRANSFER = "WHALE_TRANSFER"
    DEX_SWAP = "DEX_SWAP"
    UNKNOWN = "UNKNOWN"


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

    def get_transaction_type(self) -> TransactionType:
        """Определить тип транзакции."""
        from_is_exchange = is_exchange_address(self.from_address, self.blockchain)
        to_is_exchange = is_exchange_address(self.to_address, self.blockchain)

        if from_is_exchange and to_is_exchange:
            return TransactionType.EXCHANGE_TRANSFER
        if to_is_exchange:
            return TransactionType.DEPOSIT
        if from_is_exchange:
            return TransactionType.WITHDRAWAL
        if self.from_label or self.to_label:
            return TransactionType.WHALE_TRANSFER
        return TransactionType.UNKNOWN


class WhaleTracker:
    """
    Трекер крупных транзакций китов на нескольких блокчейнах.

    Отслеживает большие переводы на Ethereum, BSC, Bitcoin, Arbitrum, Polygon и Avalanche.

    Источники данных (в порядке приоритета):
    - Ethereum: Etherscan V2 API (3 keys rotation)
    - BSC: Free public RPC with automatic rotation (5 endpoints)
    - Bitcoin: mempool.space (no key needed)
    - Arbitrum: Etherscan V2 API (3 keys rotation)
    - Polygon: Etherscan V2 API (3 keys rotation with delay)
    - Avalanche: Snowtrace API (no key needed)

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

        # Инициализация SQLite базы данных для транзакций
        init_whale_db()

        # Получаем глобальный кеш транзакций
        self._tx_cache = get_transaction_cache()
        
        # Получаем глобальный кеш результатов китов (2 минуты)
        self._whale_cache = get_whale_cache()

        # Инициализация трекеров для работающих блокчейнов
        # Using Etherscan V2 API (3 keys with rotation for ETH, Arbitrum, Polygon)
        self._eth_tracker = EthereumTracker()
        self._btc_tracker = BitcoinTracker()  # mempool.space - no key needed
        self._bsc_tracker = BSCTracker()  # Free public RPC with rotation - no key needed

        # Etherscan V2 supported chains
        self._arb_tracker = ArbitrumTracker()
        self._polygon_tracker = PolygonTracker()
        self._avax_tracker = AvalancheTracker()  # Snowtrace - no key needed
        # Base chain removed - requires paid Etherscan plan
        
        # TON tracker
        self._ton_tracker = TONTracker()

        # DeFi трекер
        self._defi_tracker = DeFiTracker()

        # Кэш последних транзакций
        self._last_transactions: list[WhaleTransaction] = []
        self._stats_cache: Optional[WhaleStats] = None
        self._stats_cache_time: float = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None

        logger.info(
            "WhaleTracker инициализирован",
            min_transaction_usd=self.min_transaction,
            check_interval=self.check_interval,
            use_demo_data=self.use_demo_data,
            etherscan_key="настроен" if settings.etherscan_api_key else "не настроен",
            networks=["ETH", "BTC", "BSC", "ARB", "POLYGON", "AVAX", "TON"],
            database="SQLite",
            defi_tracking="enabled",
            tx_cache="enabled",
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

        # Закрываем трекеры
        await self._eth_tracker.close()
        await self._btc_tracker.close()
        await self._bsc_tracker.close()
        await self._arb_tracker.close()
        await self._polygon_tracker.close()
        await self._avax_tracker.close()
        # Base tracker removed
        await self._ton_tracker.close()

        # Закрываем DeFi трекер
        await self._defi_tracker.close()

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

    def _prepare_tx_for_db(self, tx: "WhaleTransaction") -> dict:
        """
        Подготовить транзакцию для сохранения в базу данных.

        Args:
            tx: Транзакция для сохранения

        Returns:
            dict: Данные транзакции для сохранения
        """
        # Определяем тип транзакции
        tx_type = tx.get_transaction_type().value

        # Преобразуем blockchain в chain
        chain_map = {
            "Ethereum": "ETH",
            "BSC": "BSC",
            "Bitcoin": "BTC",
            "Solana": "SOL",
            "TON": "TON",
            "Arbitrum": "ARB",
            "Polygon": "POLYGON",
            "Avalanche": "AVAX",
            "Base": "BASE",
        }
        chain = chain_map.get(tx.blockchain, tx.blockchain)

        return {
            "tx_hash": tx.tx_hash,
            "chain": chain,
            "from_address": tx.from_address,
            "to_address": tx.to_address,
            "amount": tx.amount,
            "amount_usd": tx.amount_usd,
            "token": tx.token_symbol,
            "timestamp": tx.timestamp,
            "from_label": tx.from_label,
            "to_label": tx.to_label,
            "tx_type": tx_type,
        }

    async def _save_to_db_async(self, tx: "WhaleTransaction") -> bool:
        """
        Асинхронно сохранить транзакцию в SQLite базу данных.

        Args:
            tx: Транзакция для сохранения

        Returns:
            bool: True если сохранено успешно
        """
        tx_data = self._prepare_tx_for_db(tx)
        return await asyncio.to_thread(save_transaction, tx_data)

    async def _monitoring_loop(self) -> None:
        """Цикл мониторинга транзакций."""
        while self._running:
            try:
                transactions = await self.get_all_transactions()
                self._last_transactions = transactions

                # Сохраняем каждую транзакцию в базу данных асинхронно
                saved_count = 0
                for tx in transactions:
                    if await self._save_to_db_async(tx):
                        saved_count += 1

                logger.info(
                    "Проверка китов завершена",
                    total=len(transactions),
                    saved=saved_count,
                    eth=len([t for t in transactions if t.blockchain == "Ethereum"]),
                    btc=len([t for t in transactions if t.blockchain == "Bitcoin"]),
                    bsc=len([t for t in transactions if t.blockchain == "BSC"]),
                    arb=len([t for t in transactions if t.blockchain == "Arbitrum"]),
                    polygon=len([t for t in transactions if t.blockchain == "Polygon"]),
                    avax=len([t for t in transactions if t.blockchain == "Avalanche"]),
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
        Получение крупных BNB транзакций на BSC через публичные RPC.

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

    async def get_solana_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Solana removed - Solscan API returns 404.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Empty list (Solana disabled)
        """
        logger.debug("Solana трекер отключен - Solscan API недоступен")
        return []

    async def get_ton_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение крупных TON транзакций через TON Center API.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Список транзакций
        """
        try:
            ton_transactions = await self._ton_tracker.get_large_transactions(limit=limit)
            
            # Конвертируем TON транзакции в WhaleTransaction
            whale_transactions = []
            for tx in ton_transactions:
                whale_tx = WhaleTransaction(
                    tx_hash=tx.tx_hash,
                    blockchain="TON",
                    from_address=tx.from_address,
                    to_address=tx.to_address,
                    amount=tx.value_ton,
                    amount_usd=tx.value_usd,
                    token_symbol=tx.token_symbol,
                    timestamp=tx.timestamp,
                )
                whale_tx.tx_type = tx.tx_type
                whale_transactions.append(whale_tx)
            
            return whale_transactions
        except Exception as e:
            logger.error(
                "Ошибка получения TON транзакций",
                error=str(e),
            )
            return []

    # ===== Новые сети (Arbitrum, Polygon, Avalanche, Base) =====

    async def get_arbitrum_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение крупных ETH транзакций на Arbitrum.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Список транзакций
        """
        try:
            arb_txs = await self._arb_tracker.get_large_transactions(limit=limit)

            transactions = []
            for tx in arb_txs:
                transactions.append(
                    WhaleTransaction(
                        tx_hash=tx.tx_hash,
                        blockchain="Arbitrum",
                        token_symbol="ETH",
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
                "Получены Arbitrum транзакции",
                count=len(transactions),
            )
            return transactions

        except Exception as e:
            logger.error(
                "Ошибка Arbitrum трекера",
                error=str(e),
            )
            return []

    async def get_polygon_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение крупных MATIC транзакций на Polygon.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Список транзакций
        """
        try:
            polygon_txs = await self._polygon_tracker.get_large_transactions(limit=limit)

            transactions = []
            for tx in polygon_txs:
                transactions.append(
                    WhaleTransaction(
                        tx_hash=tx.tx_hash,
                        blockchain="Polygon",
                        token_symbol="MATIC",
                        amount=tx.value_matic,
                        amount_usd=tx.value_usd,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        from_label=tx.from_label,
                        to_label=tx.to_label,
                        timestamp=tx.timestamp,
                    )
                )

            logger.debug(
                "Получены Polygon транзакции",
                count=len(transactions),
            )
            return transactions

        except Exception as e:
            logger.error(
                "Ошибка Polygon трекера",
                error=str(e),
            )
            return []

    async def get_avalanche_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение крупных AVAX транзакций на Avalanche.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Список транзакций
        """
        try:
            avax_txs = await self._avax_tracker.get_large_transactions(limit=limit)

            transactions = []
            for tx in avax_txs:
                transactions.append(
                    WhaleTransaction(
                        tx_hash=tx.tx_hash,
                        blockchain="Avalanche",
                        token_symbol="AVAX",
                        amount=tx.value_avax,
                        amount_usd=tx.value_usd,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        from_label=tx.from_label,
                        to_label=tx.to_label,
                        timestamp=tx.timestamp,
                    )
                )

            logger.debug(
                "Получены Avalanche транзакции",
                count=len(transactions),
            )
            return transactions

        except Exception as e:
            logger.error(
                "Ошибка Avalanche трекера",
                error=str(e),
            )
            return []

    async def get_base_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Base removed - requires paid Etherscan API plan.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[WhaleTransaction]: Empty list (Base disabled)
        """
        logger.debug("Base трекер отключен - требуется платный API")
        return []

    async def get_defi_events(self, limit: int = 20) -> list:
        """
        Получение DeFi событий.

        Args:
            limit: Максимальное количество событий

        Returns:
            list: Список DeFi событий
        """
        return await self._defi_tracker.get_all_defi_events(limit=limit)

    async def format_defi_message(self) -> str:
        """
        Форматирование сообщения о DeFi событиях.

        Returns:
            str: Форматированное сообщение
        """
        return await self._defi_tracker.format_defi_message()

    async def get_all_transactions(
        self,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение транзакций со всех работающих блокчейнов (7 сетей).

        Working chains:
        - BTC (mempool.space - no key needed)
        - ETH (Etherscan V2 with key rotation)
        - BSC (Free public RPC with rotation - no key needed)
        - Arbitrum (Etherscan V2 with key rotation)
        - Polygon (Etherscan V2 with delay and key rotation)
        - AVAX (Snowtrace - no key needed)
        - TON (TON Center API - no key needed)

        Removed chains:
        - Base (requires paid API)
        - SOL (Solscan 404)

        Args:
            limit: Максимальное количество транзакций на блокчейн

        Returns:
            list[WhaleTransaction]: Список всех транзакций (без дубликатов)
        """
        # Hybrid parallel approach: run ALL networks in parallel with individual timeouts
        all_transactions = []
        
        # Helper to fetch with timeout
        async def fetch_with_timeout(name: str, coro, timeout: int):
            try:
                return await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"{name} timeout, skipping")
                return []
            except Exception as e:
                logger.error(f"{name} error: {e}")
                return []
        
        # All networks in parallel!
        results = await asyncio.gather(
            fetch_with_timeout("BTC", self.get_bitcoin_transactions(limit), 5),
            fetch_with_timeout("AVAX", self.get_avalanche_transactions(limit), 5),
            fetch_with_timeout("BSC", self.get_bsc_transactions(limit), 8),
            fetch_with_timeout("ETH", self.get_ethereum_transactions(limit), 10),
            fetch_with_timeout("ARB", self.get_arbitrum_transactions(limit), 10),
            fetch_with_timeout("POLYGON", self.get_polygon_transactions(limit), 8),
            fetch_with_timeout("TON", self.get_ton_transactions(limit), 8),
            return_exceptions=True
        )
        
        # Collect results
        for result in results:
            if isinstance(result, list):
                all_transactions.extend(result)

        # Фильтруем дубликаты с помощью кеша
        unique_transactions = []
        duplicates_count = 0
        
        for tx in all_transactions:
            if not self._tx_cache.contains(tx.tx_hash):
                # Новая транзакция, добавляем в кеш и результаты
                self._tx_cache.add(tx.tx_hash)
                unique_transactions.append(tx)
            else:
                duplicates_count += 1
        
        if duplicates_count > 0:
            logger.debug(
                "Отфильтровано дубликатов транзакций",
                duplicates=duplicates_count,
                unique=len(unique_transactions),
            )

        # Если нет реальных данных и включен демо-режим
        if not unique_transactions and self.use_demo_data:
            logger.warning(
                "⚠️ ВНИМАНИЕ: Используются демо-данные! "
                "Реальные API недоступны или не настроены. "
                "Установите WHALE_USE_DEMO_DATA=false для отключения."
            )
            return await self._get_demo_transactions()

        # Сортируем по времени
        unique_transactions.sort(
            key=lambda x: x.timestamp if x.timestamp else datetime.now(timezone.utc),
            reverse=True,
        )

        return unique_transactions

    async def get_transactions_by_blockchain(
        self,
        blockchain: str,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """
        Получение транзакций для конкретного блокчейна.

        Args:
            blockchain: Название блокчейна (eth, bsc, btc, sol, ton, arb, polygon, avax, base)
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
        elif blockchain_lower in ("sol", "solana"):
            return await self.get_solana_transactions(limit=limit)
        elif blockchain_lower == "ton":
            return await self.get_ton_transactions(limit=limit)
        elif blockchain_lower in ("arb", "arbitrum"):
            return await self.get_arbitrum_transactions(limit=limit)
        elif blockchain_lower in ("polygon", "matic"):
            return await self.get_polygon_transactions(limit=limit)
        elif blockchain_lower in ("avax", "avalanche"):
            return await self.get_avalanche_transactions(limit=limit)
        elif blockchain_lower == "base":
            # Base disabled - requires paid Etherscan plan
            logger.debug("Base трекер отключен - требуется платный API")
            return []
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
        btc_count = len([tx for tx in transactions if tx.blockchain == "Bitcoin"])
        bsc_count = len([tx for tx in transactions if tx.blockchain == "BSC"])
        arb_count = len([tx for tx in transactions if tx.blockchain == "Arbitrum"])
        polygon_count = len([tx for tx in transactions if tx.blockchain == "Polygon"])
        avax_count = len([tx for tx in transactions if tx.blockchain == "Avalanche"])
        ton_count = len([tx for tx in transactions if tx.blockchain == "TON"])

        return {
            "total_transactions": len(transactions),
            "exchange_deposits": deposits,
            "exchange_withdrawals": withdrawals,
            "total_volume_usd": total_volume,
            "eth_transactions": eth_count,
            "bsc_transactions": bsc_count,  # Re-enabled with Blockscout
            "btc_transactions": btc_count,
            "sol_transactions": 0,  # Disabled
            "ton_transactions": ton_count,  # Enabled
            "arb_transactions": arb_count,
            "polygon_transactions": polygon_count,
            "avax_transactions": avax_count,
            "base_transactions": 0,  # Disabled - requires paid API
            "sentiment": "bearish" if deposits > withdrawals else "bullish",
        }

    async def format_whale_message(
        self,
        blockchain: Optional[str] = None,
    ) -> str:
        """
        Форматирование сообщения о движениях китов для Telegram с кешированием.

        Args:
            blockchain: Блокчейн для отображения (None для всех)

        Returns:
            str: Форматированное сообщение
        """
        # Определяем ключ кеша
        cache_key = blockchain if blockchain else "all"
        
        # Проверяем кеш
        cached_result = self._whale_cache.get(cache_key)
        if cached_result:
            logger.debug(
                "Используем кешированные whale данные",
                network=cache_key,
            )
            return cached_result
        
        # Данных в кеше нет, получаем свежие
        if blockchain:
            transactions = await self.get_transactions_by_blockchain(
                blockchain, limit=10
            )
        else:
            transactions = await self.get_all_transactions(limit=10)

        # Конвертируем в WhaleAlert для форматирования
        alerts = [tx.to_alert() for tx in transactions]

        result = format_whale_summary(alerts, period="последний час")
        
        # Сохраняем в кеш
        self._whale_cache.set(cache_key, result)
        
        return result

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
            sol_transactions=analysis["sol_transactions"],
            ton_transactions=analysis["ton_transactions"],
            arb_transactions=analysis["arb_transactions"],
            polygon_transactions=analysis["polygon_transactions"],
            avax_transactions=analysis["avax_transactions"],
            base_transactions=analysis["base_transactions"],
        )

    async def get_all_networks_stats(self) -> WhaleStats:
        """
        Получение статистики по всем сетям.

        Returns:
            WhaleStats: Объединённая статистика по всем сетям
        """
        # Проверяем кэш (1 минута)
        current_time = time_module.time()
        if (
            self._stats_cache is not None
            and current_time - self._stats_cache_time < 60
        ):
            return self._stats_cache

        stats = WhaleStats()

        # Получаем транзакции со всех сетей параллельно
        transactions = await self.get_all_transactions(limit=50)

        # Группируем по сетям (только работающие)
        network_map = {
            "Ethereum": "ETH",
            "Bitcoin": "BTC",
            "BSC": "BSC",
            "Arbitrum": "ARB",
            "Polygon": "POLYGON",
            "Avalanche": "AVAX",
            "TON": "TON",
        }

        for network_name, network_key in network_map.items():
            network_txs = [
                tx for tx in transactions
                if tx.blockchain == network_name
            ]

            ns = stats.networks[network_key]
            ns.transactions_24h = len(network_txs)
            ns.volume_24h_usd = sum(tx.amount_usd for tx in network_txs)

            if network_txs:
                largest_tx = max(network_txs, key=lambda x: x.amount_usd)
                ns.largest_tx_usd = largest_tx.amount_usd
                ns.largest_tx_hash = largest_tx.tx_hash
                ns.top_from_label = largest_tx.from_label or ""
                ns.top_to_label = largest_tx.to_label or ""

            if ns.transactions_24h > 0:
                ns.average_tx_usd = ns.volume_24h_usd / ns.transactions_24h

            ns.deposits_count = sum(
                1 for tx in network_txs if tx.is_exchange_deposit
            )
            ns.withdrawals_count = sum(
                1 for tx in network_txs if tx.is_exchange_withdrawal
            )

            # Топ транзакции
            ns.top_transactions = [
                {
                    "tx_hash": tx.tx_hash,
                    "amount_usd": tx.amount_usd,
                    "from_label": tx.from_label,
                    "to_label": tx.to_label,
                    "tx_type": tx.tx_type,
                }
                for tx in sorted(
                    network_txs, key=lambda x: x.amount_usd, reverse=True
                )[:10]
            ]

        # Кэшируем результат
        self._stats_cache = stats
        self._stats_cache_time = current_time

        return stats

    async def get_network_stats(self, network: str) -> Optional[NetworkStats]:
        """
        Получение статистики по одной сети.

        Args:
            network: Название сети (BTC, ETH, BSC, SOL, TON)

        Returns:
            NetworkStats: Статистика сети или None
        """
        stats = await self.get_all_networks_stats()
        return stats.get_network_stats(network)

    async def get_top_transactions(self, limit: int = 10) -> list[dict]:
        """
        Получение топ транзакций всех сетей.

        Args:
            limit: Количество транзакций

        Returns:
            list[dict]: Топ транзакций
        """
        transactions = await self.get_all_transactions(limit=limit * 2)

        # Сортируем по сумме
        sorted_txs = sorted(
            transactions,
            key=lambda x: x.amount_usd,
            reverse=True,
        )[:limit]

        return [
            {
                "tx_hash": tx.tx_hash,
                "network": tx.blockchain,
                "amount_usd": tx.amount_usd,
                "from_label": tx.from_label,
                "to_label": tx.to_label,
                "tx_type": tx.get_transaction_type().value,
            }
            for tx in sorted_txs
        ]

    async def get_24h_summary(self) -> str:
        """
        Получение сводки за 24 часа.

        Returns:
            str: Форматированное сообщение сводки
        """
        stats = await self.get_all_networks_stats()
        return format_24h_summary_message(stats)

    async def format_all_networks_stats_message(self) -> str:
        """
        Форматирование сообщения статистики всех сетей.

        Returns:
            str: Форматированное сообщение
        """
        stats = await self.get_all_networks_stats()
        return format_whale_stats_message(stats)

    async def format_network_stats_message(self, network: str) -> str:
        """
        Форматирование сообщения статистики одной сети.

        Args:
            network: Название сети

        Returns:
            str: Форматированное сообщение
        """
        ns = await self.get_network_stats(network)
        if ns:
            return format_network_stats_message(ns)
        return f"❌ Сеть {network} не найдена"

    async def format_top_transactions_message(self, limit: int = 10) -> str:
        """
        Форматирование топ транзакций.

        Args:
            limit: Количество транзакций

        Returns:
            str: Форматированное сообщение
        """
        txs = await self.get_top_transactions(limit)
        return format_top_transactions_message(txs, limit)

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

    async def get_stats_from_db(
        self,
        chain: Optional[str] = None,
    ) -> dict[str, dict]:
        """
        Получение статистики из базы данных за 24ч/7д/30д.

        Args:
            chain: Фильтр по сети (BTC, ETH, BSC, SOL, TON)

        Returns:
            dict: Статистика по периодам
        """
        return await asyncio.to_thread(get_multi_period_stats, chain)

    async def format_stats_from_db_message(
        self,
        chain: Optional[str] = None,
    ) -> str:
        """
        Форматирование статистики из базы данных.

        Args:
            chain: Фильтр по сети

        Returns:
            str: Форматированное сообщение для Telegram
        """
        stats = await asyncio.to_thread(get_multi_period_stats, chain)
        return format_db_stats_message(
            stats_24h=stats["24h"],
            stats_7d=stats["7d"],
            stats_30d=stats["30d"],
            chain=chain,
        )

    async def get_db_transaction_count_async(self) -> int:
        """
        Асинхронное получение количества транзакций в базе данных.

        Returns:
            int: Количество транзакций
        """
        return await asyncio.to_thread(get_transaction_count)

    async def get_db_transactions(
        self,
        chain: Optional[str] = None,
        limit: int = 100,
        hours: int = 24,
    ) -> list[dict]:
        """
        Получение транзакций из базы данных.

        Args:
            chain: Фильтр по сети
            limit: Максимальное количество
            hours: Период в часах

        Returns:
            list[dict]: Список транзакций
        """
        return await asyncio.to_thread(
            get_db_transactions, chain, limit, hours
        )

    async def _get_demo_transactions(self) -> list[WhaleTransaction]:
        """
        Получение демо-транзакций для отображения функционала.

        Returns:
            list[WhaleTransaction]: Список демо-транзакций
        """
        import uuid
        current_time = datetime.now(timezone.utc)

        # Generate unique demo transaction hashes using UUID
        demo_data = [
            WhaleTransaction(
                tx_hash=f"0xdemo_eth_{uuid.uuid4().hex[:56]}",
                blockchain="Ethereum",
                token_symbol="ETH",
                amount=5000,
                amount_usd=10_000_000,
                from_address="0x1234567890abcdef1234567890abcdef12345678",
                to_address="0x28c6c06298d514db089934071355e5743bf21d60",
                from_label=None,
                to_label="Binance",
                timestamp=current_time,
                tx_type="DEPOSIT",
            ),
            WhaleTransaction(
                tx_hash=f"demo_btc_{uuid.uuid4().hex[:58]}",
                blockchain="Bitcoin",
                token_symbol="BTC",
                amount=500,
                amount_usd=20_000_000,
                from_address="bc1qxyz1234567890abcdef1234567890abcdef",
                to_address="34xp4vrocgjym3xr7ycvpfhocnxv4twseo",
                from_label="Unknown Whale",
                to_label="Binance",
                timestamp=current_time,
                tx_type="DEPOSIT",
            ),
            WhaleTransaction(
                tx_hash=f"0xdemo_arb_{uuid.uuid4().hex[:54]}",
                blockchain="Arbitrum",
                token_symbol="ETH",
                amount=2000,
                amount_usd=4_000_000,
                from_address="0xb38e8c17e38363af6ebdcb3dae12e0243582891d",
                to_address="0xe592427a0aece92de3edee1f18e0157c05861564",
                from_label="Binance Arbitrum",
                to_label="Uniswap V3 Router",
                timestamp=current_time,
                tx_type="DEX_SWAP",
            ),
            WhaleTransaction(
                tx_hash=f"0xdemo_poly_{uuid.uuid4().hex[:53]}",
                blockchain="Polygon",
                token_symbol="MATIC",
                amount=5000000,
                amount_usd=2_500_000,
                from_address="0xf977814e90da44bfa03b6295a0616a897441acec",
                to_address="0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff",
                from_label="Binance",
                to_label="QuickSwap Router",
                timestamp=current_time,
                tx_type="DEX_SWAP",
            ),
            WhaleTransaction(
                tx_hash=f"0xdemo_avax_{uuid.uuid4().hex[:53]}",
                blockchain="Avalanche",
                token_symbol="AVAX",
                amount=100000,
                amount_usd=3_500_000,
                from_address="0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                to_address="0x60ae616a2155ee3d9a68541ba4544862310933d4",
                from_label="Binance AVAX",
                to_label="TraderJoe Router",
                timestamp=current_time,
                tx_type="DEX_SWAP",
            ),
        ]
        return demo_data
