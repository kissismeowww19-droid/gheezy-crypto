"""
Gheezy Crypto - Bitcoin Whale Tracker

Отслеживание крупных транзакций на Bitcoin через Blockchair API.
Работает в России без VPN и без API ключа (30 запросов/мин).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import aiohttp
import structlog

from src.config import settings
from src.whale.known_wallets import get_bitcoin_wallet_label

logger = structlog.get_logger()

# Blockchair API URL (работает без ключа, 30 req/min)
BLOCKCHAIR_API_URL = "https://api.blockchair.com/bitcoin"


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

    Использует Blockchair API для мониторинга.
    Работает без API ключа (лимит 30 запросов в минуту).
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
        Получение крупных BTC транзакций через Blockchair.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[BitcoinTransaction]: Список транзакций
        """
        await self._update_btc_price()

        min_value_btc = self.min_value_usd / self._btc_price

        return await self._get_from_blockchair(min_value_btc, limit)

    async def _get_from_blockchair(
        self,
        min_value_btc: float,
        limit: int,
    ) -> list[BitcoinTransaction]:
        """
        Получение транзакций через Blockchair API.

        Args:
            min_value_btc: Минимальная сумма в BTC
            limit: Максимальное количество транзакций

        Returns:
            list[BitcoinTransaction]: Список транзакций
        """
        try:
            session = await self._get_session()

            # Конвертируем BTC в сатоши для запроса
            min_value_satoshi = int(min_value_btc * 100_000_000)

            # Запрос крупных транзакций
            url = f"{BLOCKCHAIR_API_URL}/transactions"
            params = {
                "q": f"output_total(>{min_value_satoshi})",
                "s": "time(desc)",
                "limit": limit * 2,  # Запрашиваем больше на случай фильтрации
            }

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status != 200:
                    logger.error(f"Blockchair error: {response.status}")
                    return []

                data = await response.json()

                if "data" not in data or not data["data"]:
                    logger.warning("No data from Blockchair")
                    return []

                transactions = []
                for tx_data in data["data"]:
                    # Blockchair возвращает сумму в сатоши
                    output_total = tx_data.get("output_total", 0)
                    value_btc = output_total / 100_000_000
                    value_usd = value_btc * self._btc_price

                    if value_btc < min_value_btc:
                        continue

                    # Парсим временную метку
                    timestamp = None
                    time_str = tx_data.get("time")
                    if time_str:
                        try:
                            timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        except (ValueError, AttributeError):
                            pass

                    transactions.append(
                        BitcoinTransaction(
                            tx_hash=tx_data.get("hash", ""),
                            from_addresses=[],  # Blockchair не даёт детали в списке
                            to_addresses=[],
                            value_btc=value_btc,
                            value_usd=value_usd,
                            timestamp=timestamp,
                            block_height=tx_data.get("block_id"),
                        )
                    )

                    if len(transactions) >= limit:
                        break

                return transactions

        except Exception as e:
            logger.error(f"Blockchair error: {e}")
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

            url = f"{BLOCKCHAIR_API_URL}/dashboards/transaction/{tx_hash}"

            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    return None

                data = await response.json()

                if "data" not in data or tx_hash not in data["data"]:
                    return None

                tx_info = data["data"][tx_hash]
                tx_data = tx_info.get("transaction", {})

                # Получаем адреса входов и выходов
                inputs = tx_info.get("inputs", [])
                outputs = tx_info.get("outputs", [])

                from_addresses = list(set(inp.get("recipient", "") for inp in inputs if inp.get("recipient")))
                to_addresses = list(set(out.get("recipient", "") for out in outputs if out.get("recipient")))

                output_total = tx_data.get("output_total", 0)
                value_btc = output_total / 100_000_000
                value_usd = value_btc * self._btc_price

                timestamp = None
                time_str = tx_data.get("time")
                if time_str:
                    try:
                        timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                return BitcoinTransaction(
                    tx_hash=tx_hash,
                    from_addresses=from_addresses,
                    to_addresses=to_addresses,
                    value_btc=value_btc,
                    value_usd=value_usd,
                    timestamp=timestamp,
                    block_height=tx_data.get("block_id"),
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

            url = f"{BLOCKCHAIR_API_URL}/dashboards/address/{address}"
            params = {"limit": limit, "offset": 0}

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    return []

                data = await response.json()

                if "data" not in data or address not in data["data"]:
                    return []

                addr_data = data["data"][address]
                tx_hashes = addr_data.get("transactions", [])[:limit]

                # Получаем детали для каждой транзакции
                transactions = []
                for tx_hash in tx_hashes:
                    tx = await self.get_transaction_details(tx_hash)
                    if tx and tx.value_usd >= self.min_value_usd:
                        transactions.append(tx)

                return transactions

        except Exception as e:
            logger.error(f"Address transactions error: {e}")
            return []
