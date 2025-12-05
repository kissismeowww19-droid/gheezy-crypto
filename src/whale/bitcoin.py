"""
Gheezy Crypto - Bitcoin Whale Tracker

Отслеживание крупных транзакций на Bitcoin через mempool.space API.
Поддерживает резервный источник данных через blockstream.info.
Работает в России без VPN и без API ключа.

Возможности:
- mempool.space API (основной, без ключа)
- blockstream.info API (резервный, без ключа)
- Кэширование цен криптовалют
- Retry логика с exponential backoff
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import settings
from whale.known_wallets import get_bitcoin_wallet_label

logger = structlog.get_logger()

# ===== API URLs =====
# Mempool.space API URL (free, no API key required)
MEMPOOL_API_URL = "https://mempool.space/api"

# Blockstream.info API URL (free, no API key required) - резервный
BLOCKSTREAM_API_URL = "https://blockstream.info/api"

# Blockchain.info API URL (free, no API key required) - дополнительный
BLOCKCHAIN_INFO_API_URL = "https://blockchain.info"


@dataclass
class BitcoinTransaction:
    """
    Транзакция на Bitcoin.

    Attributes:
        tx_hash: Хэш транзакции
        from_addresses: Адреса отправителей
        to_addresses: Адреса получателей
        value_btc: Сумма в BTC
        value_usd: Сумма в USD
        timestamp: Время транзакции
        block_height: Высота блока
        fee_btc: Комиссия в BTC
        fee_usd: Комиссия в USD
        confirmations: Количество подтверждений
        size_bytes: Размер транзакции в байтах
        weight: Weight в виртуальных байтах (vbytes)
    """

    tx_hash: str
    from_addresses: list[str]
    to_addresses: list[str]
    value_btc: float
    value_usd: float
    timestamp: Optional[datetime] = None
    block_height: Optional[int] = None
    fee_btc: float = 0.0
    fee_usd: float = 0.0
    confirmations: int = 0
    size_bytes: int = 0
    weight: int = 0

    @property
    def primary_from(self) -> str:
        """Основной адрес отправителя."""
        return self.from_addresses[0] if self.from_addresses else "Unknown"

    @property
    def primary_to(self) -> str:
        """Основной адрес получателя."""
        return self.to_addresses[0] if self.to_addresses else "Unknown"

    @property
    def from_label(self) -> Optional[str]:
        """Метка отправителя."""
        for addr in self.from_addresses:
            label = get_bitcoin_wallet_label(addr)
            if label:
                return label
        return None

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        for addr in self.to_addresses:
            label = get_bitcoin_wallet_label(addr)
            if label:
                return label
        return None


class BitcoinTracker:
    """
    Трекер крупных транзакций на Bitcoin.

    Использует несколько источников данных:
    1. mempool.space API (основной)
    2. blockstream.info API (резервный)

    Все источники работают без API ключа.

    Особенности:
    - Кэширование цен криптовалют
    - Retry логика с exponential backoff
    """

    def __init__(self):
        """Инициализация трекера."""
        self.min_value_usd = settings.whale_min_transaction
        self.blocks_to_analyze = getattr(settings, "whale_blocks_to_analyze", 200)
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._btc_price: float = 40000.0  # Дефолтная цена BTC
        self._price_last_update: float = 0  # Время последнего обновления цены

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение HTTP сессии."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Закрытие HTTP сессии."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _update_btc_price(self) -> None:
        """
        Обновление цены BTC через CoinGecko с кэшированием.

        Цена кэшируется на время, заданное в whale_price_cache_ttl.
        """
        current_time = time.time()

        # Проверяем кэш
        if current_time - self._price_last_update < self.price_cache_ttl:
            logger.debug(
                "Используем кэшированную цену BTC",
                price=self._btc_price,
                cache_age=int(current_time - self._price_last_update),
            )
            return

        try:
            session = await self._get_session()
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "bitcoin", "vs_currencies": "usd"}
            timeout = aiohttp.ClientTimeout(total=10)

            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if "bitcoin" in data and "usd" in data["bitcoin"]:
                        self._btc_price = data["bitcoin"]["usd"]
                        self._price_last_update = current_time
                        logger.info(
                            "Цена BTC обновлена",
                            price=f"${self._btc_price}",
                        )
                else:
                    logger.warning(
                        "CoinGecko API вернул ошибку",
                        status=response.status,
                    )
        except asyncio.TimeoutError:
            logger.warning("Таймаут при получении цены BTC")
        except Exception as e:
            logger.warning(
                "Ошибка при обновлении цены BTC",
                error=str(e),
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _make_api_request(
        self,
        url: str,
        params: Optional[dict] = None,
    ) -> Optional[dict | list]:
        """
        Выполнение HTTP запроса с retry логикой.

        Args:
            url: URL для запроса
            params: GET параметры

        Returns:
            dict | list: Ответ API или None при ошибке
        """
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=20)

        async with session.get(url, params=params, timeout=timeout) as response:
            if response.status == 200:
                return await response.json()
            logger.warning(
                "API запрос вернул ошибку",
                url=url,
                status=response.status,
            )
            return None

    async def get_large_transactions(
        self,
        limit: int = 20,
    ) -> list[BitcoinTransaction]:
        """
        Получение крупных BTC транзакций.

        Использует несколько источников данных:
        1. mempool.space API (основной)
        2. blockchain.info API (резервный)
        3. blockstream.info API (запасной)

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[BitcoinTransaction]: Список транзакций
        """
        await self._update_btc_price()
        min_value_btc = self.min_value_usd / self._btc_price

        # Пробуем mempool.space (основной)
        logger.debug("Пробуем получить данные через mempool.space")
        transactions = await self._get_from_mempool(min_value_btc, limit)
        if transactions:
            logger.info(
                "Данные получены через mempool.space",
                count=len(transactions),
            )
            return transactions

        # Пробуем blockchain.info (резервный)
        logger.debug("Пробуем получить данные через blockchain.info")
        transactions = await self._get_from_blockchain_info(min_value_btc, limit)
        if transactions:
            logger.info(
                "Данные получены через blockchain.info",
                count=len(transactions),
            )
            return transactions

        # Резервный вариант через blockstream.info
        logger.warning("mempool.space и blockchain.info недоступны, пробуем blockstream.info")
        transactions = await self._get_from_blockstream(min_value_btc, limit)
        if transactions:
            logger.info(
                "Данные получены через blockstream.info",
                count=len(transactions),
            )
            return transactions

        logger.warning("Не удалось получить BTC транзакции")
        return []

    async def _get_from_mempool(
        self,
        min_value_btc: float,
        limit: int,
    ) -> list[BitcoinTransaction]:
        """
        Получение транзакций через mempool.space API.

        Получает последние блоки и анализирует их транзакции.

        Args:
            min_value_btc: Минимальная сумма в BTC
            limit: Максимальное количество транзакций

        Returns:
            list[BitcoinTransaction]: Список транзакций
        """
        try:
            # Получаем последние блоки для анализа подтверждённых транзакций
            blocks_url = f"{MEMPOOL_API_URL}/blocks"
            blocks = await self._make_api_request(blocks_url)

            if not blocks:
                logger.debug("mempool.space: не удалось получить блоки")
                return []

            transactions = []
            # Анализируем больше блоков для лучшего покрытия
            blocks_to_check = min(5, len(blocks))

            for block in blocks[:blocks_to_check]:
                block_hash = block.get("id")
                if not block_hash:
                    continue

                # Получаем транзакции блока
                txs_url = f"{MEMPOOL_API_URL}/block/{block_hash}/txs"
                block_txs = await self._make_api_request(txs_url)

                if not block_txs:
                    continue

                for tx_data in block_txs:
                    if tx_data is None:
                        continue

                    tx = self._parse_mempool_transaction(tx_data, min_value_btc)
                    if tx:
                        transactions.append(tx)

                    if len(transactions) >= limit * 2:
                        break

                # Небольшая задержка между запросами
                await asyncio.sleep(0.1)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.warning(
                "Ошибка mempool.space API",
                error=str(e),
            )
            return []

    def _parse_mempool_transaction(
        self,
        tx_data: dict,
        min_value_btc: float,
    ) -> Optional[BitcoinTransaction]:
        """
        Парсинг транзакции из формата mempool.space.

        Args:
            tx_data: Данные транзакции
            min_value_btc: Минимальная сумма в BTC

        Returns:
            BitcoinTransaction: Транзакция или None если не подходит
        """
        # Суммируем все выходы транзакции
        outputs = tx_data.get("vout", []) or []
        output_total = sum((out.get("value", 0) or 0) for out in outputs if out)
        value_btc = output_total / 100_000_000
        value_usd = value_btc * self._btc_price

        if value_btc < min_value_btc:
            return None

        # Получаем адреса входов и выходов
        inputs = tx_data.get("vin", []) or []

        from_addresses = list(dict.fromkeys(
            (inp.get("prevout") or {}).get("scriptpubkey_address", "")
            for inp in inputs
            if inp and (inp.get("prevout") or {}).get("scriptpubkey_address")
        ))
        to_addresses = list(dict.fromkeys(
            out.get("scriptpubkey_address", "")
            for out in outputs
            if out and out.get("scriptpubkey_address")
        ))

        # Время подтверждения
        timestamp = None
        status = tx_data.get("status", {}) or {}
        block_time = status.get("block_time")
        if block_time:
            try:
                timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc)
            except (ValueError, OSError):
                timestamp = datetime.now(timezone.utc)

        return BitcoinTransaction(
            tx_hash=tx_data.get("txid", ""),
            from_addresses=from_addresses,
            to_addresses=to_addresses,
            value_btc=value_btc,
            value_usd=value_usd,
            timestamp=timestamp,
            block_height=status.get("block_height"),
        )

    async def _get_from_blockstream(
        self,
        min_value_btc: float,
        limit: int,
    ) -> list[BitcoinTransaction]:
        """
        Резервное получение транзакций через blockstream.info API.

        Args:
            min_value_btc: Минимальная сумма в BTC
            limit: Максимальное количество транзакций

        Returns:
            list[BitcoinTransaction]: Список транзакций
        """
        try:
            # Получаем последние блоки
            blocks_url = f"{BLOCKSTREAM_API_URL}/blocks"
            blocks = await self._make_api_request(blocks_url)

            if not blocks:
                logger.debug("blockstream.info: не удалось получить блоки")
                return []

            transactions = []

            # Анализируем последние блоки
            for block in blocks[:3]:
                block_hash = block.get("id")
                if not block_hash:
                    continue

                # Получаем транзакции блока
                txs_url = f"{BLOCKSTREAM_API_URL}/block/{block_hash}/txs"
                block_txs = await self._make_api_request(txs_url)

                if not block_txs:
                    continue

                for tx_data in block_txs:
                    if tx_data is None:
                        continue

                    tx = self._parse_blockstream_transaction(tx_data, min_value_btc)
                    if tx:
                        transactions.append(tx)

                    if len(transactions) >= limit * 2:
                        break

                # Небольшая задержка
                await asyncio.sleep(0.1)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.warning(
                "Ошибка blockstream.info API",
                error=str(e),
            )
            return []

    def _parse_blockstream_transaction(
        self,
        tx_data: dict,
        min_value_btc: float,
    ) -> Optional[BitcoinTransaction]:
        """
        Парсинг транзакции из формата blockstream.info.

        Формат похож на mempool.space.

        Args:
            tx_data: Данные транзакции
            min_value_btc: Минимальная сумма в BTC

        Returns:
            BitcoinTransaction: Транзакция или None если не подходит
        """
        # Формат blockstream.info очень похож на mempool.space
        outputs = tx_data.get("vout", []) or []
        output_total = sum((out.get("value", 0) or 0) for out in outputs if out)
        value_btc = output_total / 100_000_000
        value_usd = value_btc * self._btc_price

        if value_btc < min_value_btc:
            return None

        inputs = tx_data.get("vin", []) or []

        from_addresses = list(dict.fromkeys(
            (inp.get("prevout") or {}).get("scriptpubkey_address", "")
            for inp in inputs
            if inp and (inp.get("prevout") or {}).get("scriptpubkey_address")
        ))
        to_addresses = list(dict.fromkeys(
            out.get("scriptpubkey_address", "")
            for out in outputs
            if out and out.get("scriptpubkey_address")
        ))

        timestamp = None
        status = tx_data.get("status", {}) or {}
        block_time = status.get("block_time")
        if block_time:
            try:
                timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc)
            except (ValueError, OSError):
                timestamp = datetime.now(timezone.utc)

        return BitcoinTransaction(
            tx_hash=tx_data.get("txid", ""),
            from_addresses=from_addresses,
            to_addresses=to_addresses,
            value_btc=value_btc,
            value_usd=value_usd,
            timestamp=timestamp,
            block_height=status.get("block_height"),
        )

    def _deduplicate_and_sort(
        self,
        transactions: list[BitcoinTransaction],
        limit: int,
    ) -> list[BitcoinTransaction]:
        """
        Удаление дубликатов и сортировка транзакций.

        Args:
            transactions: Список транзакций
            limit: Максимальное количество

        Returns:
            list[BitcoinTransaction]: Отсортированный список уникальных транзакций
        """
        seen_hashes = set()
        unique_transactions = []

        for tx in sorted(
            transactions,
            key=lambda x: x.value_usd,  # Сортируем по сумме для Bitcoin
            reverse=True,
        ):
            if tx.tx_hash not in seen_hashes:
                seen_hashes.add(tx.tx_hash)
                unique_transactions.append(tx)
                if len(unique_transactions) >= limit:
                    break

        return unique_transactions

    async def get_transaction_details(self, tx_hash: str) -> Optional[BitcoinTransaction]:
        """
        Получение деталей конкретной транзакции.

        Args:
            tx_hash: Хэш транзакции

        Returns:
            BitcoinTransaction: Детали транзакции или None
        """
        try:
            # Пробуем mempool.space
            url = f"{MEMPOOL_API_URL}/tx/{tx_hash}"
            tx_data = await self._make_api_request(url)

            if tx_data:
                # Используем парсер для mempool формата
                await self._update_btc_price()
                return self._parse_mempool_transaction(tx_data, 0)  # 0 = без фильтра

            # Пробуем blockstream.info
            url = f"{BLOCKSTREAM_API_URL}/tx/{tx_hash}"
            tx_data = await self._make_api_request(url)

            if tx_data:
                return self._parse_blockstream_transaction(tx_data, 0)

            return None

        except Exception as e:
            logger.error(
                "Ошибка при получении деталей транзакции",
                tx_hash=tx_hash,
                error=str(e),
            )
            return None

    async def get_address_transactions(
        self,
        address: str,
        limit: int = 10,
    ) -> list[BitcoinTransaction]:
        """
        Получение транзакций для конкретного адреса.

        Args:
            address: Bitcoin адрес
            limit: Максимальное количество транзакций

        Returns:
            list[BitcoinTransaction]: Список транзакций
        """
        try:
            await self._update_btc_price()

            # Пробуем mempool.space
            url = f"{MEMPOOL_API_URL}/address/{address}/txs"
            data = await self._make_api_request(url)

            if not data:
                # Пробуем blockstream.info
                url = f"{BLOCKSTREAM_API_URL}/address/{address}/txs"
                data = await self._make_api_request(url)

            if not data:
                return []

            transactions = []
            min_value_btc = self.min_value_usd / self._btc_price

            for tx_data in data[:limit * 2]:
                if tx_data is None:
                    continue

                tx = self._parse_mempool_transaction(tx_data, min_value_btc)
                if tx:
                    transactions.append(tx)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.error(
                "Ошибка при получении транзакций адреса",
                address=address,
                error=str(e),
            )
            return []
