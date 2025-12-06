"""
Gheezy Crypto - BSC Whale Tracker

Отслеживание крупных транзакций на Binance Smart Chain через публичные RPC ноды.
Работает полностью бесплатно без API ключей.

Возможности:
- Ротация публичных RPC нод с автоматическим failover
- Health check для выбора рабочего RPC
- Кэширование данных блоков (10 минут)
- Кэширование цен криптовалют
- Retry логика с exponential backoff
- Timeout handling (3-5 секунд)
- Не требует платных API ключей
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
from whale.known_wallets import get_bsc_wallet_label
from whale.bsc_provider import BSCProvider

logger = structlog.get_logger()

# Block data cache settings
BLOCK_CACHE_TTL = 600  # Cache block data for 10 minutes
BLOCK_CACHE_MAX_SIZE = 100  # Maximum number of blocks to cache
BLOCK_CACHE_CLEANUP_SIZE = 50  # Number of oldest blocks to remove when cleaning

# ===== Block scanning constants =====
# Maximum number of blocks to scan
# BSC creates a block every ~3 seconds, so 20 blocks = ~1 minute of transactions
MAX_BLOCKS_TO_SCAN = 20
# Multiplier for over-collecting transactions before filtering
TRANSACTION_BUFFER_MULTIPLIER = 2

# ===== Расширенный список адресов бирж для отслеживания на BSC =====
TRACKED_BSC_ADDRESSES = [
    # Binance Hot Wallets
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3",
    "0xe2fc31f816a9b94326492132018c3aecc4a93ae1",
    "0x28c6c06298d514db089934071355e5743bf21d60",
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8",
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be",
    "0xd551234ae421e3bcba99a0da6d736074f22192ff",
    "0x631fc1ea2270e98fbd9d92658ece0f5a269aa161",
    # Binance Cold Wallets
    "0xf977814e90da44bfa03b6295a0616a897441acec",
    "0x5a52e96bacdabb82fd05763e25335261b270efcb",
    "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503",
    # PancakeSwap
    "0x10ed43c718714eb63d5aa57b78b54704e256024e",  # V2 Router
    "0x45c54210128a065de780c4b0df3d16664f7f859e",  # V3 Router
    "0x73feaa1ee314f8c655e354234017be2193c9e24e",  # MasterChef
    "0x556b9306565093c855aea9ae92a594704c2cd59e",  # Deployer
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b",
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3",
    # KuCoin
    "0x2b5634c42055806a59e9107ed44d43c426e58258",
    "0xd6216fc19db775df9774a6e33526131da7d19a2c",
    # Gate.io
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe",
    "0x1c4b70a3968436b9a0a9cf5205c787eb81bb558c",
    # Huobi
    "0xab5c66752a9e8167967685f1450532fb96d5d24f",
    "0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b",
    # Bybit
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40",
    "0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4",
]


@dataclass
class BSCTransaction:
    """
    Транзакция на BSC.

    Attributes:
        tx_hash: Хэш транзакции
        from_address: Адрес отправителя
        to_address: Адрес получателя
        value_bnb: Сумма в BNB
        value_usd: Сумма в USD
        token_symbol: Символ токена (BNB или BEP-20)
        timestamp: Время транзакции
        block_number: Номер блока
    """

    tx_hash: str
    from_address: str
    to_address: str
    value_bnb: float
    value_usd: float
    token_symbol: str = "BNB"
    timestamp: Optional[datetime] = None
    block_number: Optional[int] = None

    @property
    def from_label(self) -> Optional[str]:
        """Метка отправителя."""
        return get_bsc_wallet_label(self.from_address)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_bsc_wallet_label(self.to_address)


class BSCTracker:
    """
    Трекер крупных транзакций на BSC.

    Использует публичные RPC ноды с автоматической ротацией:
    1. BSCProvider для управления RPC endpoints
    2. Автоматический failover между провайдерами
    3. Кэширование данных блоков и цен

    Особенности:
    - Не требует API ключей
    - Кэширование цен криптовалют
    - Кэширование данных блоков
    - Retry логика с exponential backoff
    - Timeout handling (3-5 секунд)
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Инициализация трекера.

        Args:
            api_key: Не используется (для обратной совместимости)
        """
        self.min_value_usd = settings.whale_min_transaction
        self.blocks_to_analyze = getattr(settings, "whale_blocks_to_analyze", 200)
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._bnb_price: float = 300.0  # Дефолтная цена BNB
        self._price_last_update: float = 0  # Время последнего обновления цены
        
        # BSC RPC provider with rotation
        self._provider = BSCProvider()
        
        # Block cache: block_number -> block_data
        self._block_cache: dict[int, tuple[dict, float]] = {}
        self._block_cache_ttl = BLOCK_CACHE_TTL

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение HTTP сессии."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Закрытие HTTP сессии и провайдера."""
        if self._session and not self._session.closed:
            await self._session.close()
        await self._provider.close()

    async def _update_bnb_price(self) -> None:
        """
        Обновление цены BNB через CoinGecko с кэшированием.

        Цена кэшируется на время, заданное в whale_price_cache_ttl.
        """
        current_time = time.time()

        # Проверяем кэш
        if current_time - self._price_last_update < self.price_cache_ttl:
            logger.debug(
                "Используем кэшированную цену BNB",
                price=self._bnb_price,
                cache_age=int(current_time - self._price_last_update),
            )
            return

        try:
            session = await self._get_session()
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "binancecoin", "vs_currencies": "usd"}
            timeout = aiohttp.ClientTimeout(total=10)

            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if "binancecoin" in data and "usd" in data["binancecoin"]:
                        self._bnb_price = data["binancecoin"]["usd"]
                        self._price_last_update = current_time
                        logger.info(
                            "Цена BNB обновлена",
                            price=f"${self._bnb_price}",
                        )
                else:
                    logger.warning(
                        "CoinGecko API вернул ошибку",
                        status=response.status,
                    )
        except asyncio.TimeoutError:
            logger.warning("Таймаут при получении цены BNB")
        except Exception as e:
            logger.warning(
                "Ошибка при обновлении цены BNB",
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
        """
        Выполнение HTTP запроса с retry логикой.

        Args:
            url: URL для запроса
            params: GET параметры
            json_data: JSON данные для POST запроса

        Returns:
            dict: Ответ API или None при ошибке
        """
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=15)

        if json_data:
            async with session.post(
                url, json=json_data, timeout=timeout
            ) as response:
                if response.status == 200:
                    return await response.json()
                logger.warning(
                    "API запрос вернул ошибку",
                    url=url,
                    status=response.status,
                )
                return None
        else:
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
    ) -> list[BSCTransaction]:
        """
        Получение крупных BNB транзакций.

        Использует публичные RPC ноды с автоматической ротацией.
        Не требует API ключей.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[BSCTransaction]: Список транзакций
        """
        await self._update_bnb_price()
        min_value_bnb = self.min_value_usd / self._bnb_price

        # Use RPC with automatic provider rotation
        logger.debug("BSC: Getting data via RPC with provider rotation")
        transactions = await self._get_from_rpc_with_rotation(min_value_bnb, limit)
        
        if transactions:
            logger.info(
                "BSC: Data obtained via RPC",
                count=len(transactions),
            )
            return transactions

        logger.warning("BSC: All RPC providers unavailable")
        return []

    async def _get_from_rpc_with_rotation(
        self,
        min_value_bnb: float,
        limit: int,
    ) -> list[BSCTransaction]:
        """
        Получение транзакций через RPC с автоматической ротацией провайдеров.

        Использует BSCProvider для выбора рабочего RPC endpoint.
        Получает последние блоки и фильтрует крупные транзакции.

        Args:
            min_value_bnb: Минимальная сумма в BNB
            limit: Максимальное количество транзакций

        Returns:
            list[BSCTransaction]: Список транзакций
        """
        try:
            # Get latest block number using provider rotation
            block_data = await self._provider.make_request(
                method="eth_blockNumber",
                params=[],
                timeout=5,
            )
            
            if not block_data or "result" not in block_data:
                logger.debug("BSC: Failed to get block number")
                return []

            latest_block = int(block_data["result"], 16)
            transactions = []

            # BSC creates blocks every ~3 seconds
            # Analyze recent blocks to capture more transactions
            blocks_to_scan = min(MAX_BLOCKS_TO_SCAN, 20)

            logger.debug(
                "BSC: Analyzing blocks",
                start=latest_block - blocks_to_scan + 1,
                end=latest_block,
                blocks_count=blocks_to_scan,
            )

            for block_num in range(latest_block, max(latest_block - blocks_to_scan, 0), -1):
                # Check cache first
                block = await self._get_block_cached(block_num)
                
                if not block:
                    continue

                block_timestamp = int(block.get("timestamp", "0x0"), 16)

                for tx in block.get("transactions", []):
                    if isinstance(tx, str):  # Only hash, not full transaction
                        continue

                    value_hex = tx.get("value", "0x0")
                    value_wei = int(value_hex, 16)
                    value_bnb = value_wei / 10**18
                    value_usd = value_bnb * self._bnb_price

                    # Filter by minimum value
                    if value_bnb < min_value_bnb:
                        continue

                    try:
                        timestamp = datetime.fromtimestamp(block_timestamp, tz=timezone.utc)
                    except (ValueError, OSError):
                        timestamp = datetime.now(timezone.utc)

                    transactions.append(
                        BSCTransaction(
                            tx_hash=tx.get("hash", ""),
                            from_address=tx.get("from", ""),
                            to_address=tx.get("to", "") or "",
                            value_bnb=value_bnb,
                            value_usd=value_usd,
                            token_symbol="BNB",
                            timestamp=timestamp,
                            block_number=block_num,
                        )
                    )

                # Stop if we have enough transactions
                if len(transactions) >= limit * TRANSACTION_BUFFER_MULTIPLIER:
                    break

            if transactions:
                logger.debug(
                    "BSC: Found transactions",
                    count=len(transactions),
                )

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.warning(
                "BSC RPC error",
                error=str(e),
            )
            return []

    async def _get_block_cached(self, block_num: int) -> Optional[dict]:
        """
        Get block data with caching.

        Args:
            block_num: Block number

        Returns:
            dict: Block data or None if unavailable
        """
        current_time = time.time()
        
        # Check cache
        if block_num in self._block_cache:
            block_data, cache_time = self._block_cache[block_num]
            if current_time - cache_time < self._block_cache_ttl:
                return block_data
            else:
                # Remove expired cache entry
                del self._block_cache[block_num]
        
        # Fetch block data via RPC
        block_response = await self._provider.make_request(
            method="eth_getBlockByNumber",
            params=[hex(block_num), True],  # True = include transactions
            timeout=5,
        )
        
        if not block_response or "result" not in block_response:
            return None
        
        block_data = block_response["result"]
        if not block_data or "transactions" not in block_data:
            return None
        
        # Cache the block data
        self._block_cache[block_num] = (block_data, current_time)
        
        # Clean old cache entries if cache is too large
        if len(self._block_cache) > BLOCK_CACHE_MAX_SIZE:
            # Remove oldest entries
            oldest_blocks = sorted(self._block_cache.keys())[:BLOCK_CACHE_CLEANUP_SIZE]
            for old_block in oldest_blocks:
                del self._block_cache[old_block]
        
        return block_data

    def _deduplicate_and_sort(
        self,
        transactions: list[BSCTransaction],
        limit: int,
    ) -> list[BSCTransaction]:
        """
        Удаление дубликатов и сортировка транзакций.

        Args:
            transactions: Список транзакций
            limit: Максимальное количество

        Returns:
            list[BSCTransaction]: Отсортированный список уникальных транзакций
        """
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

    async def get_bep20_transactions(
        self,
        token_contract: str,
        limit: int = 20,
    ) -> list[BSCTransaction]:
        """
        Получение крупных BEP-20 транзакций.
        
        NOTE: This method is deprecated as it requires Etherscan V2 API
        which needs a paid plan for BSC. BEP-20 tracking is not currently
        supported without an API key.

        Args:
            token_contract: Адрес контракта токена
            limit: Максимальное количество транзакций

        Returns:
            list[BSCTransaction]: Empty list (not supported)
        """
        logger.warning(
            "BEP-20 tracking not supported without Etherscan API",
            contract=token_contract,
        )
        return []
