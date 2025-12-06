"""
Gheezy Crypto - Polygon Whale Tracker

Отслеживание крупных транзакций на Polygon через Polygonscan API.
Работает в России без VPN.

Возможности:
- Polygonscan API (требуется API ключ)
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
from whale.api_keys import get_next_api_key

logger = structlog.get_logger()

# ===== API URLs =====
# Use Etherscan V2 API with chainid=137 for Polygon
ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api?chainid=137"
# Fallback to direct Polygonscan API
POLYGONSCAN_API_URL = "https://api.polygonscan.com/api"

# ===== Публичные RPC URL для Polygon =====
PUBLIC_POLYGON_RPC_URLS = [
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
    "https://polygon.publicnode.com",
    "https://polygon-mainnet.public.blastapi.io",
    "https://polygon-bor.publicnode.com",
]

# ===== Минимальный порог для китов =====
MIN_WHALE_MATIC = 100_000

# ===== Initial delay to avoid Etherscan V2 rate limit collision =====
# Polygon starts 2 seconds after other Etherscan V2 chains (ETH, Arbitrum)
# to prevent hitting 3 req/sec rate limit when all chains start simultaneously
POLYGON_STARTUP_DELAY_SECONDS = 2

# ===== Известные адреса Polygon =====
POLYGON_EXCHANGES: dict[str, str] = {
    # Binance
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance",
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance Hot",

    # Coinbase
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",

    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",

    # Polygon Bridge
    "0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf": "Polygon Bridge",
    "0xa0c68c638235ee32657e8f720a23cec1bfc77c77": "Polygon Bridge 2",

    # QuickSwap
    "0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff": "QuickSwap Router",
    "0xf5b509bb0909a69b1c207e495f687a596c168e12": "QuickSwap Factory",

    # Uniswap
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router 2",

    # SushiSwap
    "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506": "SushiSwap Router",

    # Aave
    "0x8dff5e27ea6b7ac08ebfdf9eb090f32ee9a30fcf": "Aave V2 Polygon",
    "0x794a61358d6845594f94dc1db02a252b5b4814ad": "Aave V3 Polygon",

    # Curve
    "0x445fe580ef8d70ff569ab36e80c647af338db351": "Curve Polygon",

    # Balancer
    "0xba12222222228d8ba445958a75a0704d566bf2c8": "Balancer Vault",
}

TRACKED_POLYGON_ADDRESSES = list(POLYGON_EXCHANGES.keys())


def get_polygon_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для Polygon адреса.

    Args:
        address: Адрес кошелька

    Returns:
        str: Метка адреса или None
    """
    return POLYGON_EXCHANGES.get(address.lower())


@dataclass
class PolygonTransaction:
    """
    Транзакция на Polygon.

    Attributes:
        tx_hash: Хэш транзакции
        from_address: Адрес отправителя
        to_address: Адрес получателя
        value_matic: Сумма в MATIC
        value_usd: Сумма в USD
        token_symbol: Символ токена
        timestamp: Время транзакции
        block_number: Номер блока
    """

    tx_hash: str
    from_address: str
    to_address: str
    value_matic: float
    value_usd: float
    token_symbol: str = "MATIC"
    timestamp: Optional[datetime] = None
    block_number: Optional[int] = None

    @property
    def from_label(self) -> Optional[str]:
        """Метка отправителя."""
        return get_polygon_wallet_label(self.from_address)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_polygon_wallet_label(self.to_address)


class PolygonTracker:
    """
    Трекер крупных транзакций на Polygon.

    Использует Polygonscan API для получения данных.
    """

    def __init__(self):
        """Инициализация трекера."""
        # Use Etherscan V2 API key (shared across all EVM chains)
        self.api_key = get_next_api_key()
        self.min_value_matic = MIN_WHALE_MATIC
        self.min_value_usd = getattr(settings, "whale_min_transaction", 100_000)
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._matic_price: float = 0.5  # Дефолтная цена MATIC
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

    async def _update_matic_price(self) -> None:
        """Обновление цены MATIC через CoinGecko с кэшированием."""
        current_time = time.time()

        if current_time - self._price_last_update < self.price_cache_ttl:
            return

        try:
            session = await self._get_session()
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "matic-network", "vs_currencies": "usd"}
            timeout = aiohttp.ClientTimeout(total=10)

            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if "matic-network" in data and "usd" in data["matic-network"]:
                        self._matic_price = data["matic-network"]["usd"]
                        self._price_last_update = current_time
                        logger.info(
                            "Polygon: Цена MATIC обновлена",
                            price=f"${self._matic_price}",
                        )
        except Exception as e:
            logger.warning(
                "Polygon: Ошибка при обновлении цены MATIC",
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
    ) -> list[PolygonTransaction]:
        """
        Получение крупных MATIC транзакций на Polygon.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[PolygonTransaction]: Список транзакций
        """
        # Add initial delay to avoid rate limit collision with other chains
        # Etherscan V2 has 3 req/sec rate limit shared across ETH, Arbitrum, and Polygon.
        # Without this delay, all three chains start simultaneously and exceed the limit.
        # 2-second delay ensures Polygon starts after ETH/Arbitrum finish initial requests.
        await asyncio.sleep(POLYGON_STARTUP_DELAY_SECONDS)
        
        await self._update_matic_price()

        # Пробуем Etherscan V2 API (один ключ для всех EVM сетей)
        logger.debug("Polygon: Пробуем получить данные через Etherscan V2")
        transactions = await self._get_from_etherscan_v2(limit)
        if transactions:
            logger.info(
                "Данные получены через Etherscan V2",
                chain="polygon",
                count=len(transactions),
            )
            return transactions

        # Fallback to direct Polygonscan API
        logger.debug("Polygon: Пробуем получить данные через Polygonscan API")
        transactions = await self._get_from_polygonscan(limit)
        if transactions:
            logger.info(
                "Polygon: Данные получены через Polygonscan",
                count=len(transactions),
            )
            return transactions

        # Пробуем публичные RPC
        logger.debug("Polygon: Пробуем получить данные через RPC")
        transactions = await self._get_from_rpc(limit)
        if transactions:
            logger.info(
                "Polygon: Данные получены через RPC",
                count=len(transactions),
            )
            return transactions

        logger.debug("Polygon: Не удалось получить транзакции")
        return []

    async def _get_from_etherscan_v2(
        self,
        limit: int,
    ) -> list[PolygonTransaction]:
        """Получение транзакций через Etherscan V2 API."""
        if not self.api_key:
            return []

        try:
            transactions = []
            num_addresses = 10

            for address in TRACKED_POLYGON_ADDRESSES[:num_addresses]:
                # Get next API key for each request (rotation)
                api_key = get_next_api_key() or self.api_key
                
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": 50,
                    "sort": "desc",
                    "apikey": api_key,
                }

                data = await self._make_api_request(ETHERSCAN_V2_URL, params=params)
                if not data or data.get("status") != "1":
                    # Log detailed error for debugging
                    if data:
                        logger.warning(
                            "Polygon: Etherscan V2 error response",
                            status=data.get("status"),
                            message=data.get("message"),
                            result=str(data.get("result", ""))[:200],
                            address=address[:10] + "..." if len(address) > 10 else address,
                        )
                    continue

                for tx in data.get("result", []):
                    value_wei = int(tx.get("value", 0))
                    value_matic = value_wei / 10**18
                    value_usd = value_matic * self._matic_price

                    if value_matic < self.min_value_matic:
                        continue

                    try:
                        timestamp = datetime.fromtimestamp(
                            int(tx.get("timeStamp", 0)), tz=timezone.utc
                        )
                    except (ValueError, OSError):
                        timestamp = datetime.now(timezone.utc)

                    transactions.append(
                        PolygonTransaction(
                            tx_hash=tx.get("hash", ""),
                            from_address=tx.get("from", ""),
                            to_address=tx.get("to", ""),
                            value_matic=value_matic,
                            value_usd=value_usd,
                            timestamp=timestamp,
                            block_number=int(tx.get("blockNumber", 0)),
                        )
                    )

                await asyncio.sleep(0.35)  # Rate limit: 3 req/sec per key

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.debug("Polygon: Ошибка Etherscan V2 API", error=str(e))
            return []

    async def _get_from_polygonscan(
        self,
        limit: int,
    ) -> list[PolygonTransaction]:
        """Получение транзакций через Polygonscan API (работает без ключа с rate limit)."""
        try:
            transactions = []
            # Limit addresses when no API key to avoid rate limiting
            num_addresses = 10 if self.api_key else 3

            for address in TRACKED_POLYGON_ADDRESSES[:num_addresses]:
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

                data = await self._make_api_request(POLYGONSCAN_API_URL, params=params)
                if not data or data.get("status") != "1":
                    # Rate limit delay without API key
                    if not self.api_key:
                        await asyncio.sleep(0.5)
                    continue

                for tx in data.get("result", []):
                    value_wei = int(tx.get("value", 0))
                    value_matic = value_wei / 10**18
                    value_usd = value_matic * self._matic_price

                    if value_matic < self.min_value_matic:
                        continue

                    try:
                        timestamp = datetime.fromtimestamp(
                            int(tx.get("timeStamp", 0)), tz=timezone.utc
                        )
                    except (ValueError, OSError):
                        timestamp = datetime.now(timezone.utc)

                    transactions.append(
                        PolygonTransaction(
                            tx_hash=tx.get("hash", ""),
                            from_address=tx.get("from", ""),
                            to_address=tx.get("to", ""),
                            value_matic=value_matic,
                            value_usd=value_usd,
                            timestamp=timestamp,
                            block_number=int(tx.get("blockNumber", 0)),
                        )
                    )

                # Rate limit delay - longer without API key
                await asyncio.sleep(0.5 if not self.api_key else 0.2)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.error(f"Polygon: Ошибка Polygonscan API: {e}")
            return []

    async def _get_from_rpc(
        self,
        limit: int,
    ) -> list[PolygonTransaction]:
        """Резервное получение через публичные RPC ноды."""
        for rpc_url in PUBLIC_POLYGON_RPC_URLS:
            try:
                transactions = await self._get_from_single_rpc(rpc_url, limit)
                if transactions:
                    return transactions
            except Exception as e:
                logger.debug(f"Polygon RPC недоступен: {rpc_url}, error: {e}")
                continue

        return []

    async def _get_from_single_rpc(
        self,
        rpc_url: str,
        limit: int,
    ) -> list[PolygonTransaction]:
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

        # Polygon блоки очень быстрые, смотрим больше блоков
        for block_num in range(latest_block, max(latest_block - 10, 0), -1):
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
                value_matic = value_wei / 10**18
                value_usd = value_matic * self._matic_price

                if value_matic < self.min_value_matic:
                    continue

                try:
                    timestamp = datetime.fromtimestamp(block_timestamp, tz=timezone.utc)
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                transactions.append(
                    PolygonTransaction(
                        tx_hash=tx.get("hash", ""),
                        from_address=tx.get("from", ""),
                        to_address=tx.get("to", "") or "",
                        value_matic=value_matic,
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
        transactions: list[PolygonTransaction],
        limit: int,
    ) -> list[PolygonTransaction]:
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
