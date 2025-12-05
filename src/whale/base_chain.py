"""
Gheezy Crypto - Base Chain Whale Tracker

Отслеживание крупных транзакций на Base через Basescan API.
Работает в России без VPN.

Возможности:
- Basescan API (требуется API ключ)
- Публичные RPC ноды для работы без ключа
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
from whale.etherscan_v2 import get_etherscan_key, get_etherscan_v2_url

logger = structlog.get_logger()

# ===== API URLs =====
# Use Etherscan V2 API with chainid=8453 for Base
ETHERSCAN_V2_URL = get_etherscan_v2_url("base") or "https://api.etherscan.io/v2/api?chainid=8453"
# Fallback to direct Basescan API
BASESCAN_API_URL = "https://api.basescan.org/api"

# ===== Публичные RPC URL для Base =====
PUBLIC_BASE_RPC_URLS = [
    "https://mainnet.base.org",
    "https://rpc.ankr.com/base",
    "https://base.publicnode.com",
    "https://base-mainnet.public.blastapi.io",
    "https://base.meowrpc.com",
]

# ===== Минимальный порог для китов =====
MIN_WHALE_ETH = 50

# ===== Известные адреса Base =====
BASE_EXCHANGES: dict[str, str] = {
    # Coinbase (Base = Coinbase L2)
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase 2",

    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",

    # Base Bridge
    "0x3154cf16ccdb4c6d922629664174b904d80f2c35": "Base Bridge",
    "0x49048044d57e1c92a77f79988d21fa8faf74e97e": "Base Bridge 2",

    # Uniswap
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": "Uniswap Universal Router",
    "0x2626664c2603336e57b271c5c0b26f421741e481": "Uniswap V3 Router",

    # Aerodrome (Base native DEX)
    "0xcf77a3ba9a5ca399b7c97c74d54e5b1beb874e43": "Aerodrome Router",
    "0x420dd381b31aef6683db6b902084cb0ffece40da": "Aerodrome Factory",

    # Balancer
    "0xba12222222228d8ba445958a75a0704d566bf2c8": "Balancer Vault",

    # Aave
    "0xa238dd80c259a72e81d7e4664a9801593f98d1c5": "Aave Base Pool",

    # SushiSwap
    "0xfb7edc6f4d33f8b6d5d6f3a2d8bbc7b9b7b9b7b9": "SushiSwap Router",

    # Maverick
    "0x32aed3bce901da12ca8f29dc8fbf6b54ba8d3e6b": "Maverick Router",
}

TRACKED_BASE_ADDRESSES = list(BASE_EXCHANGES.keys())


def get_base_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для Base адреса.

    Args:
        address: Адрес кошелька

    Returns:
        str: Метка адреса или None
    """
    return BASE_EXCHANGES.get(address.lower())


@dataclass
class BaseTransaction:
    """
    Транзакция на Base.

    Attributes:
        tx_hash: Хэш транзакции
        from_address: Адрес отправителя
        to_address: Адрес получателя
        value_eth: Сумма в ETH
        value_usd: Сумма в USD
        token_symbol: Символ токена
        timestamp: Время транзакции
        block_number: Номер блока
    """

    tx_hash: str
    from_address: str
    to_address: str
    value_eth: float
    value_usd: float
    token_symbol: str = "ETH"
    timestamp: Optional[datetime] = None
    block_number: Optional[int] = None

    @property
    def from_label(self) -> Optional[str]:
        """Метка отправителя."""
        return get_base_wallet_label(self.from_address)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_base_wallet_label(self.to_address)


class BaseTracker:
    """
    Трекер крупных транзакций на Base.

    Использует Basescan API для получения данных.
    """

    def __init__(self):
        """Инициализация трекера."""
        # Use Etherscan V2 API key (shared across all EVM chains)
        self.api_key = get_etherscan_key() or getattr(settings, "etherscan_api_key", "")
        self.min_value_eth = MIN_WHALE_ETH
        self.min_value_usd = getattr(settings, "whale_min_transaction", 100_000)
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._eth_price: float = 2000.0  # Дефолтная цена ETH
        self._price_last_update: float = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение HTTP сессии."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Закрытие HTTP сессии."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _update_eth_price(self) -> None:
        """Обновление цены ETH через CoinGecko с кэшированием."""
        current_time = time.time()

        if current_time - self._price_last_update < self.price_cache_ttl:
            return

        try:
            session = await self._get_session()
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "ethereum", "vs_currencies": "usd"}
            timeout = aiohttp.ClientTimeout(total=10)

            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if "ethereum" in data and "usd" in data["ethereum"]:
                        self._eth_price = data["ethereum"]["usd"]
                        self._price_last_update = current_time
                        logger.info(
                            "Base: Цена ETH обновлена",
                            price=f"${self._eth_price}",
                        )
        except Exception as e:
            logger.warning(
                "Base: Ошибка при обновлении цены ETH",
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
        json_data: Optional[dict] = None,
    ) -> Optional[dict]:
        """Выполнение HTTP запроса с retry логикой."""
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=15)

        if json_data:
            async with session.post(
                url, json=json_data, timeout=timeout
            ) as response:
                if response.status == 200:
                    return await response.json()
                return None
        else:
            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    return await response.json()
                return None

    async def get_large_transactions(
        self,
        limit: int = 20,
    ) -> list[BaseTransaction]:
        """
        Получение крупных ETH транзакций на Base.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[BaseTransaction]: Список транзакций
        """
        await self._update_eth_price()

        # Пробуем Etherscan V2 API (один ключ для всех EVM сетей)
        logger.debug("Base: Пробуем получить данные через Etherscan V2")
        transactions = await self._get_from_etherscan_v2(limit)
        if transactions:
            logger.info(
                "Данные получены через Etherscan V2",
                chain="base",
                count=len(transactions),
            )
            return transactions

        # Fallback to direct Basescan API
        logger.debug("Base: Пробуем получить данные через Basescan API")
        transactions = await self._get_from_basescan(limit)
        if transactions:
            logger.info(
                "Base: Данные получены через Basescan",
                count=len(transactions),
            )
            return transactions

        # Пробуем публичные RPC
        logger.debug("Base: Пробуем получить данные через RPC")
        transactions = await self._get_from_rpc(limit)
        if transactions:
            logger.info(
                "Base: Данные получены через RPC",
                count=len(transactions),
            )
            return transactions

        logger.debug("Base: Не удалось получить транзакции")
        return []

    async def _get_from_etherscan_v2(
        self,
        limit: int,
    ) -> list[BaseTransaction]:
        """Получение транзакций через Etherscan V2 API."""
        if not self.api_key:
            return []

        try:
            transactions = []
            num_addresses = 10

            for address in TRACKED_BASE_ADDRESSES[:num_addresses]:
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": 50,
                    "sort": "desc",
                    "apikey": self.api_key,
                }

                data = await self._make_api_request(ETHERSCAN_V2_URL, params=params)
                if not data or data.get("status") != "1":
                    continue

                for tx in data.get("result", []):
                    value_wei = int(tx.get("value", 0))
                    value_eth = value_wei / 10**18
                    value_usd = value_eth * self._eth_price

                    if value_eth < self.min_value_eth:
                        continue

                    try:
                        timestamp = datetime.fromtimestamp(
                            int(tx.get("timeStamp", 0)), tz=timezone.utc
                        )
                    except (ValueError, OSError):
                        timestamp = datetime.now(timezone.utc)

                    transactions.append(
                        BaseTransaction(
                            tx_hash=tx.get("hash", ""),
                            from_address=tx.get("from", ""),
                            to_address=tx.get("to", ""),
                            value_eth=value_eth,
                            value_usd=value_usd,
                            timestamp=timestamp,
                            block_number=int(tx.get("blockNumber", 0)),
                        )
                    )

                await asyncio.sleep(0.2)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.debug("Base: Ошибка Etherscan V2 API", error=str(e))
            return []

    async def _get_from_basescan(
        self,
        limit: int,
    ) -> list[BaseTransaction]:
        """Получение транзакций через Basescan API (работает без ключа с rate limit)."""
        try:
            transactions = []
            # Limit addresses when no API key to avoid rate limiting
            num_addresses = 10 if self.api_key else 3

            for address in TRACKED_BASE_ADDRESSES[:num_addresses]:
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": 50,
                    "sort": "desc",
                }
                if self.api_key:
                    params["apikey"] = self.api_key

                data = await self._make_api_request(BASESCAN_API_URL, params=params)
                if not data or data.get("status") != "1":
                    # Rate limit delay without API key
                    if not self.api_key:
                        await asyncio.sleep(0.5)
                    continue

                for tx in data.get("result", []):
                    value_wei = int(tx.get("value", 0))
                    value_eth = value_wei / 10**18
                    value_usd = value_eth * self._eth_price

                    if value_eth < self.min_value_eth:
                        continue

                    try:
                        timestamp = datetime.fromtimestamp(
                            int(tx.get("timeStamp", 0)), tz=timezone.utc
                        )
                    except (ValueError, OSError):
                        timestamp = datetime.now(timezone.utc)

                    transactions.append(
                        BaseTransaction(
                            tx_hash=tx.get("hash", ""),
                            from_address=tx.get("from", ""),
                            to_address=tx.get("to", ""),
                            value_eth=value_eth,
                            value_usd=value_usd,
                            timestamp=timestamp,
                            block_number=int(tx.get("blockNumber", 0)),
                        )
                    )

                # Rate limit delay - longer without API key
                await asyncio.sleep(0.5 if not self.api_key else 0.2)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.error(f"Base: Ошибка Basescan API: {e}")
            return []

    async def _get_from_rpc(
        self,
        limit: int,
    ) -> list[BaseTransaction]:
        """Резервное получение через публичные RPC ноды."""
        for rpc_url in PUBLIC_BASE_RPC_URLS:
            try:
                transactions = await self._get_from_single_rpc(rpc_url, limit)
                if transactions:
                    return transactions
            except Exception as e:
                logger.debug(f"Base RPC недоступен: {rpc_url}, error: {e}")
                continue

        return []

    async def _get_from_single_rpc(
        self,
        rpc_url: str,
        limit: int,
    ) -> list[BaseTransaction]:
        """Получение транзакций через конкретную RPC ноду."""
        block_request = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1,
        }

        data = await self._make_api_request(rpc_url, json_data=block_request)
        if not data or "result" not in data:
            return []

        latest_block = int(data["result"], 16)
        transactions = []

        # Base has ~2s block time, 5 blocks = ~10 seconds of data
        for block_num in range(latest_block, max(latest_block - 5, 0), -1):
            block_request = {
                "jsonrpc": "2.0",
                "method": "eth_getBlockByNumber",
                "params": [hex(block_num), True],
                "id": 1,
            }

            block_data = await self._make_api_request(rpc_url, json_data=block_request)
            if not block_data or "result" not in block_data:
                continue

            block = block_data["result"]
            if not block or "transactions" not in block:
                continue

            block_timestamp = int(block.get("timestamp", "0x0"), 16)

            for tx in block["transactions"]:
                if isinstance(tx, str):
                    continue

                value_hex = tx.get("value", "0x0")
                value_wei = int(value_hex, 16)
                value_eth = value_wei / 10**18
                value_usd = value_eth * self._eth_price

                if value_eth < self.min_value_eth:
                    continue

                try:
                    timestamp = datetime.fromtimestamp(block_timestamp, tz=timezone.utc)
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                transactions.append(
                    BaseTransaction(
                        tx_hash=tx.get("hash", ""),
                        from_address=tx.get("from", ""),
                        to_address=tx.get("to", "") or "",
                        value_eth=value_eth,
                        value_usd=value_usd,
                        timestamp=timestamp,
                        block_number=block_num,
                    )
                )

                if len(transactions) >= limit:
                    break

            if len(transactions) >= limit:
                break

        return self._deduplicate_and_sort(transactions, limit)

    def _deduplicate_and_sort(
        self,
        transactions: list[BaseTransaction],
        limit: int,
    ) -> list[BaseTransaction]:
        """Удаление дубликатов и сортировка."""
        seen_hashes = set()
        unique_transactions = []

        for tx in sorted(
            transactions,
            key=lambda x: x.timestamp or datetime.now(timezone.utc),
            reverse=True,
        ):
            if tx.tx_hash not in seen_hashes:
                seen_hashes.add(tx.tx_hash)
                unique_transactions.append(tx)
                if len(unique_transactions) >= limit:
                    break

        return unique_transactions
