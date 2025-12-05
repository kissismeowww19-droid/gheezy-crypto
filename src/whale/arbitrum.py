"""
Gheezy Crypto - Arbitrum Whale Tracker

Отслеживание крупных транзакций на Arbitrum через Arbiscan API.
Работает в России без VPN.

Возможности:
- Arbiscan API (требуется API ключ)
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

logger = structlog.get_logger()

# ===== API URLs =====
ARBISCAN_API_URL = "https://api.arbiscan.io/api"

# ===== Публичные RPC URL для Arbitrum =====
PUBLIC_ARBITRUM_RPC_URLS = [
    "https://arb1.arbitrum.io/rpc",
    "https://rpc.ankr.com/arbitrum",
    "https://arbitrum.publicnode.com",
    "https://arbitrum-one.public.blastapi.io",
]

# ===== Минимальный порог для китов =====
MIN_WHALE_ETH = 50

# ===== Известные адреса Arbitrum =====
ARBITRUM_EXCHANGES: dict[str, str] = {
    # Binance
    "0xb38e8c17e38363af6ebdcb3dae12e0243582891d": "Binance Arbitrum",
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Binance Hot",

    # Coinbase
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",

    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",

    # Bybit
    "0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4": "Bybit",

    # GMX
    "0x489ee077994b6658eafa855c308275ead8097c4a": "GMX Vault",
    "0x908c4d94d34924765f1edc22a1dd098397c59dd4": "GMX Reward Router",

    # Uniswap
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router 2",

    # Arbitrum Bridge
    "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a": "Arbitrum Bridge",
    "0x4dbd4fc535ac27206064b68ffcf827b0a60bab3f": "Arbitrum Bridge 2",

    # Camelot DEX
    "0xc873fecbd354f5a56e00e710b90ef4201db2448d": "Camelot Router",

    # Radiant Capital
    "0x2032b9a8e9f7e76768ca9271003d3e43e1616b1f": "Radiant Lending Pool",
}

TRACKED_ARBITRUM_ADDRESSES = list(ARBITRUM_EXCHANGES.keys())


def get_arbitrum_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для Arbitrum адреса.

    Args:
        address: Адрес кошелька

    Returns:
        str: Метка адреса или None
    """
    return ARBITRUM_EXCHANGES.get(address.lower())


@dataclass
class ArbitrumTransaction:
    """
    Транзакция на Arbitrum.

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
        return get_arbitrum_wallet_label(self.from_address)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_arbitrum_wallet_label(self.to_address)


class ArbitrumTracker:
    """
    Трекер крупных транзакций на Arbitrum.

    Использует Arbiscan API для получения данных.
    """

    def __init__(self):
        """Инициализация трекера."""
        self.api_key = getattr(settings, "arbiscan_api_key", "")
        self.min_value_eth = MIN_WHALE_ETH
        self.min_value_usd = getattr(settings, "whale_min_transaction", 100_000)
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._eth_price: float = 2000.0
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
                            "Arbitrum: Цена ETH обновлена",
                            price=f"${self._eth_price}",
                        )
        except Exception as e:
            logger.warning(
                "Arbitrum: Ошибка при обновлении цены ETH",
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
    ) -> list[ArbitrumTransaction]:
        """
        Получение крупных ETH транзакций на Arbitrum.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[ArbitrumTransaction]: Список транзакций
        """
        await self._update_eth_price()

        # Пробуем Arbiscan API (работает и без ключа с rate limit)
        logger.debug("Arbitrum: Пробуем получить данные через Arbiscan API")
        transactions = await self._get_from_arbiscan(limit)
        if transactions:
            logger.info(
                "Arbitrum: Данные получены через Arbiscan",
                count=len(transactions),
            )
            return transactions

        # Пробуем публичные RPC
        logger.debug("Arbitrum: Пробуем получить данные через RPC")
        transactions = await self._get_from_rpc(limit)
        if transactions:
            logger.info(
                "Arbitrum: Данные получены через RPC",
                count=len(transactions),
            )
            return transactions

        logger.warning("Arbitrum: Не удалось получить транзакции")
        return []

    async def _get_from_arbiscan(
        self,
        limit: int,
    ) -> list[ArbitrumTransaction]:
        """Получение транзакций через Arbiscan API (работает без ключа с rate limit)."""
        try:
            transactions = []
            # Limit addresses when no API key to avoid rate limiting
            num_addresses = 10 if self.api_key else 3

            for address in TRACKED_ARBITRUM_ADDRESSES[:num_addresses]:
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

                data = await self._make_api_request(ARBISCAN_API_URL, params=params)
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
                        ArbitrumTransaction(
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
            logger.error(f"Arbitrum: Ошибка Arbiscan API: {e}")
            return []

    async def _get_from_rpc(
        self,
        limit: int,
    ) -> list[ArbitrumTransaction]:
        """Резервное получение через публичные RPC ноды."""
        for rpc_url in PUBLIC_ARBITRUM_RPC_URLS:
            try:
                transactions = await self._get_from_single_rpc(rpc_url, limit)
                if transactions:
                    return transactions
            except Exception as e:
                logger.debug(f"Arbitrum RPC недоступен: {rpc_url}, error: {e}")
                continue

        return []

    async def _get_from_single_rpc(
        self,
        rpc_url: str,
        limit: int,
    ) -> list[ArbitrumTransaction]:
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

        # Arbitrum has ~0.25s block time, 5 blocks = ~1.25 seconds of data
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
                    ArbitrumTransaction(
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
        transactions: list[ArbitrumTransaction],
        limit: int,
    ) -> list[ArbitrumTransaction]:
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
