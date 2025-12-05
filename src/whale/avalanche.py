"""
Gheezy Crypto - Avalanche Whale Tracker

Отслеживание крупных транзакций на Avalanche через Snowtrace API.
Работает в России без VPN.

Возможности:
- Snowtrace API (требуется API ключ)
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
SNOWTRACE_API_URL = "https://api.snowtrace.io/api"

# ===== Публичные RPC URL для Avalanche =====
PUBLIC_AVALANCHE_RPC_URLS = [
    "https://api.avax.network/ext/bc/C/rpc",
    "https://rpc.ankr.com/avalanche",
    "https://avalanche.publicnode.com",
    "https://avalanche-c-chain.publicnode.com",
    "https://avax.meowrpc.com",
]

# ===== Минимальный порог для китов =====
MIN_WHALE_AVAX = 1000

# ===== Известные адреса Avalanche =====
AVALANCHE_EXCHANGES: dict[str, str] = {
    # Binance
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Binance",
    "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9": "Binance Hot",

    # Coinbase
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",

    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",

    # Avalanche Bridge
    "0x8eb8a3b98659cce290402893d0123abb75e3ab28": "Avalanche Bridge",

    # Trader Joe
    "0x60ae616a2155ee3d9a68541ba4544862310933d4": "Trader Joe Router",
    "0x9ad6c38be94206ca50bb0d90783181662f0cfa10": "Trader Joe Factory",

    # Pangolin
    "0xe54ca86531e17ef3616d22ca28b0d458b6c89106": "Pangolin Router",
    "0xefa94de7a4656d787667c749f7e1223d71e9fd88": "Pangolin Factory",

    # Aave
    "0x794a61358d6845594f94dc1db02a252b5b4814ad": "Aave V3 Avalanche",

    # Benqi
    "0x486af39519b4dc9a7fccd318217352830e8ad9b4": "Benqi QI Token",
    "0x4e9f683a27a6bdad3fc2764003759277e93696e6": "Benqi Comptroller",

    # GMX
    "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": "GMX Avalanche",
}

TRACKED_AVALANCHE_ADDRESSES = list(AVALANCHE_EXCHANGES.keys())


def get_avalanche_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для Avalanche адреса.

    Args:
        address: Адрес кошелька

    Returns:
        str: Метка адреса или None
    """
    return AVALANCHE_EXCHANGES.get(address.lower())


@dataclass
class AvalancheTransaction:
    """
    Транзакция на Avalanche.

    Attributes:
        tx_hash: Хэш транзакции
        from_address: Адрес отправителя
        to_address: Адрес получателя
        value_avax: Сумма в AVAX
        value_usd: Сумма в USD
        token_symbol: Символ токена
        timestamp: Время транзакции
        block_number: Номер блока
    """

    tx_hash: str
    from_address: str
    to_address: str
    value_avax: float
    value_usd: float
    token_symbol: str = "AVAX"
    timestamp: Optional[datetime] = None
    block_number: Optional[int] = None

    @property
    def from_label(self) -> Optional[str]:
        """Метка отправителя."""
        return get_avalanche_wallet_label(self.from_address)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_avalanche_wallet_label(self.to_address)


class AvalancheTracker:
    """
    Трекер крупных транзакций на Avalanche.

    Использует Snowtrace API для получения данных.
    """

    def __init__(self):
        """Инициализация трекера."""
        self.api_key = getattr(settings, "snowtrace_api_key", "")
        self.min_value_avax = MIN_WHALE_AVAX
        self.min_value_usd = getattr(settings, "whale_min_transaction", 100_000)
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._avax_price: float = 25.0  # Дефолтная цена AVAX
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

    async def _update_avax_price(self) -> None:
        """Обновление цены AVAX через CoinGecko с кэшированием."""
        current_time = time.time()

        if current_time - self._price_last_update < self.price_cache_ttl:
            return

        try:
            session = await self._get_session()
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "avalanche-2", "vs_currencies": "usd"}
            timeout = aiohttp.ClientTimeout(total=10)

            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if "avalanche-2" in data and "usd" in data["avalanche-2"]:
                        self._avax_price = data["avalanche-2"]["usd"]
                        self._price_last_update = current_time
                        logger.info(
                            "Avalanche: Цена AVAX обновлена",
                            price=f"${self._avax_price}",
                        )
        except Exception as e:
            logger.warning(
                "Avalanche: Ошибка при обновлении цены AVAX",
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
    ) -> list[AvalancheTransaction]:
        """
        Получение крупных AVAX транзакций на Avalanche.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[AvalancheTransaction]: Список транзакций
        """
        await self._update_avax_price()

        # Пробуем Snowtrace API если есть ключ
        if self.api_key:
            logger.debug("Avalanche: Пробуем получить данные через Snowtrace API")
            transactions = await self._get_from_snowtrace(limit)
            if transactions:
                logger.info(
                    "Avalanche: Данные получены через Snowtrace",
                    count=len(transactions),
                )
                return transactions

        # Пробуем публичные RPC
        logger.debug("Avalanche: Пробуем получить данные через RPC")
        transactions = await self._get_from_rpc(limit)
        if transactions:
            logger.info(
                "Avalanche: Данные получены через RPC",
                count=len(transactions),
            )
            return transactions

        logger.warning("Avalanche: Не удалось получить транзакции")
        return []

    async def _get_from_snowtrace(
        self,
        limit: int,
    ) -> list[AvalancheTransaction]:
        """Получение транзакций через Snowtrace API."""
        if not self.api_key:
            return []

        try:
            transactions = []

            for address in TRACKED_AVALANCHE_ADDRESSES[:10]:
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "page": 1,
                    "offset": 50,
                    "sort": "desc",
                    "apikey": self.api_key,
                }

                data = await self._make_api_request(SNOWTRACE_API_URL, params=params)
                if not data or data.get("status") != "1":
                    continue

                for tx in data.get("result", []):
                    value_wei = int(tx.get("value", 0))
                    value_avax = value_wei / 10**18
                    value_usd = value_avax * self._avax_price

                    if value_avax < self.min_value_avax:
                        continue

                    try:
                        timestamp = datetime.fromtimestamp(
                            int(tx.get("timeStamp", 0)), tz=timezone.utc
                        )
                    except (ValueError, OSError):
                        timestamp = datetime.now(timezone.utc)

                    transactions.append(
                        AvalancheTransaction(
                            tx_hash=tx.get("hash", ""),
                            from_address=tx.get("from", ""),
                            to_address=tx.get("to", ""),
                            value_avax=value_avax,
                            value_usd=value_usd,
                            timestamp=timestamp,
                            block_number=int(tx.get("blockNumber", 0)),
                        )
                    )

                await asyncio.sleep(0.2)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.error(f"Avalanche: Ошибка Snowtrace API: {e}")
            return []

    async def _get_from_rpc(
        self,
        limit: int,
    ) -> list[AvalancheTransaction]:
        """Резервное получение через публичные RPC ноды."""
        for rpc_url in PUBLIC_AVALANCHE_RPC_URLS:
            try:
                transactions = await self._get_from_single_rpc(rpc_url, limit)
                if transactions:
                    return transactions
            except Exception as e:
                logger.debug(f"Avalanche RPC недоступен: {rpc_url}, error: {e}")
                continue

        return []

    async def _get_from_single_rpc(
        self,
        rpc_url: str,
        limit: int,
    ) -> list[AvalancheTransaction]:
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
                value_avax = value_wei / 10**18
                value_usd = value_avax * self._avax_price

                if value_avax < self.min_value_avax:
                    continue

                try:
                    timestamp = datetime.fromtimestamp(block_timestamp, tz=timezone.utc)
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                transactions.append(
                    AvalancheTransaction(
                        tx_hash=tx.get("hash", ""),
                        from_address=tx.get("from", ""),
                        to_address=tx.get("to", "") or "",
                        value_avax=value_avax,
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
        transactions: list[AvalancheTransaction],
        limit: int,
    ) -> list[AvalancheTransaction]:
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
