"""
Gheezy Crypto - Ethereum Whale Tracker

Отслеживание крупных транзакций на Ethereum через Etherscan API.
Поддерживает резервные источники данных через публичные RPC ноды и Blockscout.
Работает в России без VPN.

Возможности:
- Etherscan API (требуется API ключ)
- Blockscout API (бесплатный, без ключа)
- Публичные RPC ноды для получения блоков
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
from whale.known_wallets import get_ethereum_wallet_label
from whale.etherscan_v2 import get_etherscan_key, get_etherscan_v2_url

logger = structlog.get_logger()

# ===== API URLs =====
# Etherscan API V2 URL with chainid=1 for Ethereum
ETHERSCAN_API_URL = get_etherscan_v2_url("eth") or "https://api.etherscan.io/v2/api?chainid=1"

# Blockscout API URL (бесплатный, без ключа)
BLOCKSCOUT_API_URL = "https://eth.blockscout.com/api/v2"

# ===== Публичные RPC URL для Ethereum (резервные) =====
PUBLIC_RPC_URLS = [
    "https://eth.llamarpc.com",
    "https://rpc.ankr.com/eth",
    "https://ethereum.publicnode.com",
    "https://1rpc.io/eth",
    "https://eth.drpc.org",
]

# ===== Расширенный список адресов бирж для отслеживания =====
TRACKED_EXCHANGE_ADDRESSES = [
    # Binance Hot Wallets
    "0x28c6c06298d514db089934071355e5743bf21d60",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f",
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8",
    "0xe2fc31f816a9b94326492132018c3aecc4a93ae1",
    # Binance Cold Wallets
    "0xf977814e90da44bfa03b6295a0616a897441acec",
    "0x5a52e96bacdabb82fd05763e25335261b270efcb",
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3",
    # Coinbase
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3",
    "0x503828976d22510aad0201ac7ec88293211d23da",
    "0xa090e606e30bd747d4e6245a1517ebe430f0057e",
    # Kraken
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2",
    "0x53d284357ec70ce289d6d64134dfac8e511c8a3d",
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b",
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3",
    "0x98ec059dc3adfbdd63429454aeb0c990fba4a128",
    # Bybit
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40",
    "0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4",
    # Bitfinex
    "0x742d35cc6634c0532925a3b844bc454e4438f44e",
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa",
    # Gemini
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853",
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8",
    # Huobi
    "0xab5c66752a9e8167967685f1450532fb96d5d24f",
    "0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b",
    "0xfdb16996831753d5331ff813c29a93c76834a0ad",
]


@dataclass
class EthereumTransaction:
    """
    Транзакция на Ethereum.

    Attributes:
        tx_hash: Хэш транзакции
        from_address: Адрес отправителя
        to_address: Адрес получателя
        value_eth: Сумма в ETH
        value_usd: Сумма в USD
        token_symbol: Символ токена (ETH или ERC-20)
        timestamp: Время транзакции
        block_number: Номер блока
        gas_price_gwei: Цена газа в Gwei
        gas_used: Использованный газ
        tx_type: Тип транзакции (0=legacy, 2=EIP-1559)
        is_internal: Является ли внутренней транзакцией
    """

    tx_hash: str
    from_address: str
    to_address: str
    value_eth: float
    value_usd: float
    token_symbol: str = "ETH"
    timestamp: Optional[datetime] = None
    block_number: Optional[int] = None
    gas_price_gwei: float = 0.0
    gas_used: int = 0
    tx_type: int = 0
    is_internal: bool = False

    @property
    def from_label(self) -> Optional[str]:
        """Метка отправителя."""
        return get_ethereum_wallet_label(self.from_address)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_ethereum_wallet_label(self.to_address)


class EthereumTracker:
    """
    Трекер крупных транзакций на Ethereum.

    Использует несколько источников данных с приоритетом:
    1. Etherscan API (если есть ключ)
    2. Blockscout API (бесплатный)
    3. Публичные RPC ноды для получения блоков

    Особенности:
    - Кэширование цен криптовалют
    - Retry логика с exponential backoff
    - Параллельные запросы к адресам бирж
    """

    def __init__(self):
        """Инициализация трекера."""
        # Use API key rotation for rate limits
        self.api_key = get_etherscan_key() or settings.etherscan_api_key
        self.min_value_usd = settings.whale_min_transaction
        self.blocks_to_analyze = getattr(settings, "whale_blocks_to_analyze", 200)
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._eth_price: float = 2000.0  # Дефолтная цена ETH
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

    async def _update_eth_price(self) -> None:
        """
        Обновление цены ETH через CoinGecko с кэшированием.

        Цена кэшируется на время, заданное в whale_price_cache_ttl.
        """
        current_time = time.time()

        # Проверяем кэш
        if current_time - self._price_last_update < self.price_cache_ttl:
            logger.debug(
                "Используем кэшированную цену ETH",
                price=self._eth_price,
                cache_age=int(current_time - self._price_last_update),
            )
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
                            "Цена ETH обновлена",
                            price=f"${self._eth_price}",
                        )
                else:
                    logger.warning(
                        "CoinGecko API вернул ошибку",
                        status=response.status,
                    )
        except asyncio.TimeoutError:
            logger.warning("Таймаут при получении цены ETH")
        except Exception as e:
            logger.warning(
                "Ошибка при обновлении цены ETH",
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
    ) -> list[EthereumTransaction]:
        """
        Получение крупных ETH транзакций.

        Использует несколько источников данных с приоритетом:
        1. Etherscan API (если есть ключ)
        2. Blockscout API (бесплатный)
        3. Публичные RPC ноды

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[EthereumTransaction]: Список транзакций
        """
        await self._update_eth_price()
        min_value_eth = self.min_value_usd / self._eth_price

        # Пробуем Etherscan если есть ключ
        if self.api_key:
            logger.debug("Пробуем получить данные через Etherscan API")
            transactions = await self._get_from_etherscan(min_value_eth, limit)
            if transactions:
                logger.info(
                    "Данные получены через Etherscan V2",
                    chain="eth",
                    count=len(transactions),
                )
                return transactions

        # Пробуем Blockscout (бесплатный)
        logger.debug("Пробуем получить данные через Blockscout API")
        transactions = await self._get_from_blockscout(min_value_eth, limit)
        if transactions:
            logger.info(
                "Данные получены через Blockscout",
                count=len(transactions),
            )
            return transactions

        # Резервный вариант через RPC
        logger.warning(
            "Etherscan и Blockscout недоступны, пробуем RPC",
        )
        transactions = await self._get_from_rpc(min_value_eth, limit)
        if transactions:
            logger.info(
                "Данные получены через RPC",
                count=len(transactions),
            )
            return transactions

        logger.warning("Не удалось получить транзакции ни из одного источника")
        return []

    async def _get_from_etherscan(
        self,
        min_value_eth: float,
        limit: int,
    ) -> list[EthereumTransaction]:
        """
        Получение транзакций через Etherscan API.

        Args:
            min_value_eth: Минимальная сумма в ETH
            limit: Максимальное количество транзакций

        Returns:
            list[EthereumTransaction]: Список транзакций
        """
        if not self.api_key:
            logger.debug("Etherscan API ключ не настроен")
            return []

        try:
            # Получаем последний блок
            params_block = {
                "module": "proxy",
                "action": "eth_blockNumber",
                "apikey": self.api_key,
            }

            data = await self._make_api_request(ETHERSCAN_API_URL, params=params_block)
            if not data or "result" not in data:
                logger.warning("Не удалось получить номер последнего блока Etherscan")
                return []

            latest_block = int(data["result"], 16)
            start_block = latest_block - self.blocks_to_analyze

            logger.debug(
                "Анализируем блоки Ethereum",
                start=start_block,
                end=latest_block,
                blocks_count=self.blocks_to_analyze,
            )

            # Sequential requests with delay to avoid rate limits (3 req/sec)
            # Reduced from 15 to 10 addresses to minimize API calls while still covering major exchanges
            # Адреса отсортированы по важности (крупнейшие биржи первые)
            transactions = []
            for address in TRACKED_EXCHANGE_ADDRESSES[:10]:
                try:
                    result = await self._fetch_address_transactions(
                        address, start_block, latest_block, min_value_eth
                    )
                    if result:
                        transactions.extend(result)
                except Exception as e:
                    logger.debug(f"Ошибка при получении транзакций: {e}")
                # Rate limit: 3 req/sec, add 0.4s delay between requests
                await asyncio.sleep(0.4)

            # Удаляем дубликаты и сортируем
            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.error(
                "Ошибка Etherscan API",
                error=str(e),
            )
            return []

    async def _fetch_address_transactions(
        self,
        address: str,
        start_block: int,
        end_block: int,
        min_value_eth: float,
    ) -> list[EthereumTransaction]:
        """
        Получение транзакций для конкретного адреса.

        Args:
            address: Адрес кошелька
            start_block: Начальный блок
            end_block: Конечный блок
            min_value_eth: Минимальная сумма в ETH

        Returns:
            list[EthereumTransaction]: Список транзакций
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

        data = await self._make_api_request(ETHERSCAN_API_URL, params=params)
        if not data or data.get("status") != "1" or not data.get("result"):
            # Log detailed error for debugging
            if data and data.get("status") != "1":
                logger.warning(
                    "ETH: Etherscan V2 error response",
                    status=data.get("status"),
                    message=data.get("message"),
                    result=str(data.get("result", ""))[:200],
                    address=address[:10] + "..." if len(address) > 10 else address,
                )
            return []

        transactions = []
        for tx in data["result"]:
            value_wei = int(tx.get("value", 0))
            value_eth = value_wei / 10**18
            value_usd = value_eth * self._eth_price

            if value_eth < min_value_eth:
                continue

            try:
                timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=timezone.utc)
            except (ValueError, OSError):
                timestamp = datetime.now(timezone.utc)

            transactions.append(
                EthereumTransaction(
                    tx_hash=tx.get("hash", ""),
                    from_address=tx.get("from", ""),
                    to_address=tx.get("to", ""),
                    value_eth=value_eth,
                    value_usd=value_usd,
                    token_symbol="ETH",
                    timestamp=timestamp,
                    block_number=int(tx.get("blockNumber", 0)),
                )
            )

        return transactions

    async def _get_from_blockscout(
        self,
        min_value_eth: float,
        limit: int,
    ) -> list[EthereumTransaction]:
        """
        Получение транзакций через Blockscout API (бесплатный).

        Blockscout не требует API ключа и работает без ограничений.

        Args:
            min_value_eth: Минимальная сумма в ETH
            limit: Максимальное количество транзакций

        Returns:
            list[EthereumTransaction]: Список транзакций
        """
        try:
            # Получаем последние блоки
            blocks_url = f"{BLOCKSCOUT_API_URL}/blocks"
            data = await self._make_api_request(blocks_url)

            if not data or "items" not in data:
                logger.debug("Blockscout: не удалось получить блоки")
                return []

            transactions = []

            # Анализируем последние блоки
            for block in data["items"][:5]:  # Последние 5 блоков
                block_number = block.get("height")
                if not block_number:
                    continue

                # Получаем транзакции блока
                txs_url = f"{BLOCKSCOUT_API_URL}/blocks/{block_number}/transactions"
                txs_data = await self._make_api_request(txs_url)

                if not txs_data or "items" not in txs_data:
                    continue

                for tx in txs_data["items"]:
                    value_wei = int(tx.get("value", "0") or "0")
                    value_eth = value_wei / 10**18
                    value_usd = value_eth * self._eth_price

                    if value_eth < min_value_eth:
                        continue

                    try:
                        timestamp_str = tx.get("timestamp")
                        if timestamp_str:
                            timestamp = datetime.fromisoformat(
                                timestamp_str.replace("Z", "+00:00")
                            )
                        else:
                            timestamp = datetime.now(timezone.utc)
                    except (ValueError, TypeError):
                        timestamp = datetime.now(timezone.utc)

                    transactions.append(
                        EthereumTransaction(
                            tx_hash=tx.get("hash", ""),
                            from_address=tx.get("from", {}).get("hash", ""),
                            to_address=tx.get("to", {}).get("hash", "") if tx.get("to") else "",
                            value_eth=value_eth,
                            value_usd=value_usd,
                            token_symbol="ETH",
                            timestamp=timestamp,
                            block_number=block_number,
                        )
                    )

                    if len(transactions) >= limit * 2:
                        break

                # Небольшая задержка
                await asyncio.sleep(0.1)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.warning(
                "Ошибка Blockscout API",
                error=str(e),
            )
            return []

    async def _get_from_rpc(
        self,
        min_value_eth: float,
        limit: int,
    ) -> list[EthereumTransaction]:
        """
        Резервное получение транзакций через публичные RPC ноды.

        Получает последние блоки и анализирует их транзакции.

        Args:
            min_value_eth: Минимальная сумма в ETH
            limit: Максимальное количество транзакций

        Returns:
            list[EthereumTransaction]: Список транзакций
        """
        for rpc_url in PUBLIC_RPC_URLS:
            try:
                transactions = await self._get_from_single_rpc(
                    rpc_url, min_value_eth, limit
                )
                if transactions:
                    return transactions
            except Exception as e:
                logger.debug(
                    "RPC недоступен",
                    url=rpc_url,
                    error=str(e),
                )
                continue

        logger.info("Все публичные RPC недоступны")
        return []

    async def _get_from_single_rpc(
        self,
        rpc_url: str,
        min_value_eth: float,
        limit: int,
    ) -> list[EthereumTransaction]:
        """
        Получение транзакций через конкретную RPC ноду.

        Args:
            rpc_url: URL RPC ноды
            min_value_eth: Минимальная сумма в ETH
            limit: Максимальное количество транзакций

        Returns:
            list[EthereumTransaction]: Список транзакций
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

        # Анализируем последние несколько блоков
        for block_num in range(latest_block, max(latest_block - 5, 0), -1):
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
                value_eth = value_wei / 10**18
                value_usd = value_eth * self._eth_price

                if value_eth < min_value_eth:
                    continue

                try:
                    timestamp = datetime.fromtimestamp(block_timestamp, tz=timezone.utc)
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                transactions.append(
                    EthereumTransaction(
                        tx_hash=tx.get("hash", ""),
                        from_address=tx.get("from", ""),
                        to_address=tx.get("to", "") or "",
                        value_eth=value_eth,
                        value_usd=value_usd,
                        token_symbol="ETH",
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
        transactions: list[EthereumTransaction],
        limit: int,
    ) -> list[EthereumTransaction]:
        """
        Удаление дубликатов и сортировка транзакций.

        Args:
            transactions: Список транзакций
            limit: Максимальное количество

        Returns:
            list[EthereumTransaction]: Отсортированный список уникальных транзакций
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

    async def get_erc20_transactions(
        self,
        token_contract: str,
        limit: int = 20,
    ) -> list[EthereumTransaction]:
        """
        Получение крупных ERC-20 транзакций.

        Args:
            token_contract: Адрес контракта токена
            limit: Максимальное количество транзакций

        Returns:
            list[EthereumTransaction]: Список транзакций
        """
        if not self.api_key:
            logger.warning("Etherscan API ключ не настроен для ERC-20")
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

            data = await self._make_api_request(ETHERSCAN_API_URL, params=params)
            if not data or data.get("status") != "1" or not data.get("result"):
                return []

            transactions = []
            for tx in data["result"]:
                decimals = int(tx.get("tokenDecimal", 18))
                value = int(tx.get("value", 0)) / (10**decimals)

                # Получаем цену токена (упрощённо используем 1 USD для stablecoins)
                token_symbol = tx.get("tokenSymbol", "TOKEN")
                if token_symbol.upper() in ("USDT", "USDC", "DAI", "BUSD"):
                    value_usd = value
                else:
                    # Для других токенов используем примерную оценку
                    value_usd = value * 1.0  # Требуется API для точной цены

                if value_usd < self.min_value_usd:
                    continue

                try:
                    timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=timezone.utc)
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                transactions.append(
                    EthereumTransaction(
                        tx_hash=tx.get("hash", ""),
                        from_address=tx.get("from", ""),
                        to_address=tx.get("to", ""),
                        value_eth=value,
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
                "Ошибка при получении ERC-20 транзакций",
                error=str(e),
            )
            return []
