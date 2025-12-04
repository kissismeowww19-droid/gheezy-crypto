"""
Gheezy Crypto - Bitcoin Whale Tracker

Отслеживание крупных транзакций на Bitcoin через mempool.space API.
Работает в России без VPN и без API ключа.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import aiohttp
import structlog

from src.config import settings
from src.whale.known_wallets import get_bitcoin_wallet_label

logger = structlog.get_logger()

# Mempool.space API URL (free, no API key required)
MEMPOOL_API_URL = "https://mempool.space/api"


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
    """

    tx_hash: str
    from_addresses: list[str]
    to_addresses: list[str]
    value_btc: float
    value_usd: float
    timestamp: Optional[datetime] = None
    block_height: Optional[int] = None

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

    Использует mempool.space API для мониторинга.
    Работает без API ключа.
    """

    def __init__(self):
        """Инициализация трекера."""
        self.min_value_usd = settings.whale_min_transaction
        self._session: Optional[aiohttp.ClientSession] = None
        self._btc_price: float = 40000.0  # Дефолтная цена BTC

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
        """Обновление цены BTC через CoinGecko."""
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
                        logger.info(f"BTC price updated: ${self._btc_price}")
        except Exception as e:
            logger.warning(f"Failed to update BTC price: {e}")

    async def get_large_transactions(
        self,
        limit: int = 20,
    ) -> list[BitcoinTransaction]:
        """
        Получение крупных BTC транзакций через mempool.space.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[BitcoinTransaction]: Список транзакций
        """
        await self._update_btc_price()

        min_value_btc = self.min_value_usd / self._btc_price

        return await self._get_from_mempool(min_value_btc, limit)

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
            session = await self._get_session()

            # Получаем последние блоки для анализа подтверждённых транзакций
            blocks_url = f"{MEMPOOL_API_URL}/blocks"

            async with session.get(
                blocks_url, timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status != 200:
                    logger.error(f"Mempool.space blocks error: {response.status}")
                    return []

                blocks = await response.json()

                if not blocks:
                    logger.warning("No blocks from mempool.space")
                    return []

            transactions = []
            # Анализируем последние несколько блоков
            for block in blocks[:3]:
                block_hash = block.get("id")
                if not block_hash:
                    continue

                # Получаем транзакции блока
                txs_url = f"{MEMPOOL_API_URL}/block/{block_hash}/txs"

                async with session.get(
                    txs_url, timeout=aiohttp.ClientTimeout(total=20)
                ) as response:
                    if response.status != 200:
                        continue

                    block_txs = await response.json()

                    if not block_txs:
                        continue

                    for tx_data in block_txs:
                        if tx_data is None:
                            continue

                        # Суммируем все выходы транзакции
                        outputs = tx_data.get("vout", []) or []
                        output_total = sum((out.get("value", 0) or 0) for out in outputs if out)
                        value_btc = output_total / 100_000_000
                        value_usd = value_btc * self._btc_price

                        if value_btc < min_value_btc:
                            continue

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
                            timestamp = datetime.fromtimestamp(block_time)

                        transactions.append(
                            BitcoinTransaction(
                                tx_hash=tx_data.get("txid", ""),
                                from_addresses=from_addresses,
                                to_addresses=to_addresses,
                                value_btc=value_btc,
                                value_usd=value_usd,
                                timestamp=timestamp,
                                block_height=status.get("block_height"),
                            )
                        )

                        if len(transactions) >= limit:
                            break

                if len(transactions) >= limit:
                    break

            return transactions[:limit]

        except Exception as e:
            logger.error(f"Mempool.space error: {e}")
            return []

    async def get_transaction_details(self, tx_hash: str) -> Optional[BitcoinTransaction]:
        """
        Получение деталей конкретной транзакции.

        Args:
            tx_hash: Хэш транзакции

        Returns:
            BitcoinTransaction: Детали транзакции или None
        """
        try:
            session = await self._get_session()

            url = f"{MEMPOOL_API_URL}/tx/{tx_hash}"

            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    return None

                tx_data = await response.json()

                # Получаем адреса входов и выходов из mempool.space формата
                inputs = tx_data.get("vin", []) or []
                outputs = tx_data.get("vout", []) or []

                # Use dict.fromkeys to preserve order while removing duplicates
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

                # Сумма выходов в сатоши
                output_total = sum((out.get("value", 0) or 0) for out in outputs if out)
                value_btc = output_total / 100_000_000
                value_usd = value_btc * self._btc_price

                # Время подтверждения
                timestamp = None
                status = tx_data.get("status", {}) or {}
                block_time = status.get("block_time")
                if block_time:
                    timestamp = datetime.fromtimestamp(block_time)

                return BitcoinTransaction(
                    tx_hash=tx_hash,
                    from_addresses=from_addresses,
                    to_addresses=to_addresses,
                    value_btc=value_btc,
                    value_usd=value_usd,
                    timestamp=timestamp,
                    block_height=status.get("block_height"),
                )

        except Exception as e:
            logger.error(f"Transaction details error: {e}")
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
            session = await self._get_session()

            url = f"{MEMPOOL_API_URL}/address/{address}/txs"

            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    return []

                data = await response.json()

                if not data:
                    return []

                transactions = []
                for tx_data in data[:limit]:
                    if tx_data is None:
                        continue

                    # Получаем адреса входов и выходов
                    inputs = tx_data.get("vin", []) or []
                    outputs = tx_data.get("vout", []) or []

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

                    # Сумма выходов в сатоши
                    output_total = sum((out.get("value", 0) or 0) for out in outputs if out)
                    value_btc = output_total / 100_000_000
                    value_usd = value_btc * self._btc_price

                    if value_usd < self.min_value_usd:
                        continue

                    # Время подтверждения
                    timestamp = None
                    status = tx_data.get("status", {}) or {}
                    block_time = status.get("block_time")
                    if block_time:
                        timestamp = datetime.fromtimestamp(block_time)

                    transactions.append(
                        BitcoinTransaction(
                            tx_hash=tx_data.get("txid", ""),
                            from_addresses=from_addresses,
                            to_addresses=to_addresses,
                            value_btc=value_btc,
                            value_usd=value_usd,
                            timestamp=timestamp,
                            block_height=status.get("block_height"),
                        )
                    )

                return transactions

        except Exception as e:
            logger.error(f"Address transactions error: {e}")
            return []
