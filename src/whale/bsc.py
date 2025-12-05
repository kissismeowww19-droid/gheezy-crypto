"""
Gheezy Crypto - BSC Whale Tracker

Отслеживание крупных транзакций на Binance Smart Chain через BscScan API.
Поддерживает резервные источники данных через публичные RPC ноды.
Работает в России без VPN.

Возможности:
- BscScan API (требуется API ключ для высокой скорости)
- Публичные RPC ноды для работы без ключа
- Кэширование цен криптовалют
- Retry логика с exponential backoff
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import aiohttp
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config import settings
from src.whale.known_wallets import get_bsc_wallet_label

logger = structlog.get_logger()

# BscScan API URL (free tier works without upgrade)
BSCSCAN_API_URL = "https://api.bscscan.com/api"

# ===== Публичные RPC URL для BSC (резервные) =====
PUBLIC_BSC_RPC_URLS = [
    "https://bsc-dataseed.binance.org",
    "https://bsc-dataseed1.binance.org",
    "https://bsc-dataseed2.binance.org",
    "https://bsc-dataseed3.binance.org",
    "https://bsc-dataseed4.binance.org",
    "https://rpc.ankr.com/bsc",
    "https://bsc.publicnode.com",
    "https://bsc-mainnet.public.blastapi.io",
]

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

    Использует несколько источников данных:
    1. BscScan API (если есть ключ)
    2. Публичные RPC ноды для работы без ключа

    Особенности:
    - Кэширование цен криптовалют
    - Retry логика с exponential backoff
    - Параллельные запросы к адресам бирж
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Инициализация трекера.

        Args:
            api_key: API ключ BscScan (опционально)
        """
        self.api_key = api_key or getattr(settings, "bscscan_api_key", "")
        self.min_value_usd = settings.whale_min_transaction
        self.blocks_to_analyze = getattr(settings, "whale_blocks_to_analyze", 200)
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._bnb_price: float = 300.0  # Дефолтная цена BNB
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

        Использует несколько источников данных:
        1. BscScan API (если есть ключ)
        2. Публичные RPC ноды

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[BSCTransaction]: Список транзакций
        """
        await self._update_bnb_price()
        min_value_bnb = self.min_value_usd / self._bnb_price

        # Пробуем BscScan если есть ключ
        if self.api_key:
            logger.debug("Пробуем получить данные через BscScan API")
            transactions = await self._get_from_bscscan(min_value_bnb, limit)
            if transactions:
                logger.info(
                    "Данные получены через BscScan",
                    count=len(transactions),
                )
                return transactions

        # Резервный вариант через RPC
        logger.debug("Пробуем получить данные через публичные RPC")
        transactions = await self._get_from_rpc(min_value_bnb, limit)
        if transactions:
            logger.info(
                "Данные получены через RPC",
                count=len(transactions),
            )
            return transactions

        logger.warning("BscScan API ключ не настроен и RPC недоступен")
        return []

    async def _get_from_bscscan(
        self,
        min_value_bnb: float,
        limit: int,
    ) -> list[BSCTransaction]:
        """
        Получение транзакций через BscScan API.

        Args:
            min_value_bnb: Минимальная сумма в BNB
            limit: Максимальное количество транзакций

        Returns:
            list[BSCTransaction]: Список транзакций
        """
        if not self.api_key:
            return []

        try:
            # Получаем последний блок
            params_block = {
                "module": "proxy",
                "action": "eth_blockNumber",
                "apikey": self.api_key,
            }

            data = await self._make_api_request(BSCSCAN_API_URL, params=params_block)
            if not data or "result" not in data:
                logger.warning("Не удалось получить номер последнего блока BscScan")
                return []

            latest_block = int(data["result"], 16)
            # BSC блоки быстрее, смотрим больше блоков
            start_block = latest_block - (self.blocks_to_analyze * 2)

            logger.debug(
                "Анализируем блоки BSC",
                start=start_block,
                end=latest_block,
                blocks_count=self.blocks_to_analyze * 2,
            )

            # Параллельные запросы к адресам бирж
            tasks = []
            for address in TRACKED_BSC_ADDRESSES[:15]:  # Ограничиваем для скорости
                tasks.append(
                    self._fetch_address_transactions(
                        address, start_block, latest_block, min_value_bnb
                    )
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Собираем все транзакции
            transactions = []
            for result in results:
                if isinstance(result, list):
                    transactions.extend(result)
                elif isinstance(result, Exception):
                    logger.debug(f"Ошибка при получении транзакций: {result}")

            # Удаляем дубликаты и сортируем
            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.error(
                "Ошибка BscScan API",
                error=str(e),
            )
            return []

    async def _fetch_address_transactions(
        self,
        address: str,
        start_block: int,
        end_block: int,
        min_value_bnb: float,
    ) -> list[BSCTransaction]:
        """
        Получение транзакций для конкретного адреса.

        Args:
            address: Адрес кошелька
            start_block: Начальный блок
            end_block: Конечный блок
            min_value_bnb: Минимальная сумма в BNB

        Returns:
            list[BSCTransaction]: Список транзакций
        """
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": 1,
            "offset": 100,
            "sort": "desc",
            "apikey": self.api_key,
        }

        data = await self._make_api_request(BSCSCAN_API_URL, params=params)
        if not data or data.get("status") != "1" or not data.get("result"):
            return []

        transactions = []
        for tx in data["result"]:
            value_wei = int(tx.get("value", 0))
            value_bnb = value_wei / 10**18
            value_usd = value_bnb * self._bnb_price

            if value_bnb < min_value_bnb:
                continue

            try:
                timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", 0)))
            except (ValueError, OSError):
                timestamp = datetime.now()

            transactions.append(
                BSCTransaction(
                    tx_hash=tx.get("hash", ""),
                    from_address=tx.get("from", ""),
                    to_address=tx.get("to", ""),
                    value_bnb=value_bnb,
                    value_usd=value_usd,
                    token_symbol="BNB",
                    timestamp=timestamp,
                    block_number=int(tx.get("blockNumber", 0)),
                )
            )

        return transactions

    async def _get_from_rpc(
        self,
        min_value_bnb: float,
        limit: int,
    ) -> list[BSCTransaction]:
        """
        Резервное получение транзакций через публичные RPC ноды.

        Args:
            min_value_bnb: Минимальная сумма в BNB
            limit: Максимальное количество транзакций

        Returns:
            list[BSCTransaction]: Список транзакций
        """
        for rpc_url in PUBLIC_BSC_RPC_URLS:
            try:
                transactions = await self._get_from_single_rpc(
                    rpc_url, min_value_bnb, limit
                )
                if transactions:
                    return transactions
            except Exception as e:
                logger.debug(
                    "BSC RPC недоступен",
                    url=rpc_url,
                    error=str(e),
                )
                continue

        logger.info("Все публичные BSC RPC недоступны")
        return []

    async def _get_from_single_rpc(
        self,
        rpc_url: str,
        min_value_bnb: float,
        limit: int,
    ) -> list[BSCTransaction]:
        """
        Получение транзакций через конкретную RPC ноду.

        Args:
            rpc_url: URL RPC ноды
            min_value_bnb: Минимальная сумма в BNB
            limit: Максимальное количество транзакций

        Returns:
            list[BSCTransaction]: Список транзакций
        """
        # Получаем номер последнего блока
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

        # Анализируем последние несколько блоков (BSC быстрее, смотрим больше)
        for block_num in range(latest_block, max(latest_block - 10, 0), -1):
            block_request = {
                "jsonrpc": "2.0",
                "method": "eth_getBlockByNumber",
                "params": [hex(block_num), True],  # True = включить транзакции
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
                if isinstance(tx, str):  # Только хэш, а не полная транзакция
                    continue

                value_hex = tx.get("value", "0x0")
                value_wei = int(value_hex, 16)
                value_bnb = value_wei / 10**18
                value_usd = value_bnb * self._bnb_price

                if value_bnb < min_value_bnb:
                    continue

                try:
                    timestamp = datetime.fromtimestamp(block_timestamp)
                except (ValueError, OSError):
                    timestamp = datetime.now()

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

                if len(transactions) >= limit:
                    break

            if len(transactions) >= limit:
                break

        return self._deduplicate_and_sort(transactions, limit)

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
            key=lambda x: x.timestamp or datetime.now(),
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

        Args:
            token_contract: Адрес контракта токена
            limit: Максимальное количество транзакций

        Returns:
            list[BSCTransaction]: Список транзакций
        """
        if not self.api_key:
            logger.warning("BscScan API ключ не настроен для BEP-20")
            return []

        try:
            params = {
                "module": "account",
                "action": "tokentx",
                "contractaddress": token_contract,
                "page": 1,
                "offset": 100,
                "sort": "desc",
                "apikey": self.api_key,
            }

            data = await self._make_api_request(BSCSCAN_API_URL, params=params)
            if not data or data.get("status") != "1" or not data.get("result"):
                return []

            transactions = []
            for tx in data["result"]:
                decimals = int(tx.get("tokenDecimal", 18))
                value = int(tx.get("value", 0)) / (10**decimals)

                # Получаем цену токена (упрощённо используем 1 USD для stablecoins)
                token_symbol = tx.get("tokenSymbol", "TOKEN")
                if token_symbol.upper() in ("USDT", "USDC", "BUSD", "DAI"):
                    value_usd = value
                else:
                    value_usd = value * 1.0

                if value_usd < self.min_value_usd:
                    continue

                try:
                    timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", 0)))
                except (ValueError, OSError):
                    timestamp = datetime.now()

                transactions.append(
                    BSCTransaction(
                        tx_hash=tx.get("hash", ""),
                        from_address=tx.get("from", ""),
                        to_address=tx.get("to", ""),
                        value_bnb=value,
                        value_usd=value_usd,
                        token_symbol=token_symbol,
                        timestamp=timestamp,
                        block_number=int(tx.get("blockNumber", 0)),
                    )
                )

                if len(transactions) >= limit:
                    break

            return transactions

        except Exception as e:
            logger.error(
                "Ошибка при получении BEP-20 транзакций",
                error=str(e),
            )
            return []
