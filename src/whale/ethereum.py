"""
Gheezy Crypto - Ethereum Whale Tracker

Отслеживание крупных транзакций на Ethereum через Etherscan API.
Работает в России без VPN.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import aiohttp
import structlog

from src.config import settings
from src.whale.known_wallets import get_ethereum_wallet_label

logger = structlog.get_logger()

# Etherscan API V2 URL with chainid=1 for Ethereum
ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api?chainid=1"

# Публичные RPC URL для Ethereum (резервные)
PUBLIC_RPC_URLS = [
    "https://eth.llamarpc.com",
    "https://rpc.ankr.com/eth",
    "https://ethereum.publicnode.com",
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
        return get_ethereum_wallet_label(self.from_address)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_ethereum_wallet_label(self.to_address)


class EthereumTracker:
    """
    Трекер крупных транзакций на Ethereum.

    Использует Etherscan API для мониторинга.
    Резервный вариант через публичные RPC ноды.
    """

    def __init__(self):
        """Инициализация трекера."""
        self.api_key = settings.etherscan_api_key
        self.min_value_usd = settings.whale_min_transaction
        self._session: Optional[aiohttp.ClientSession] = None
        self._eth_price: float = 2000.0  # Дефолтная цена ETH

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
        """Обновление цены ETH через CoinGecko."""
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
                        logger.info(f"ETH price updated: ${self._eth_price}")
        except Exception as e:
            logger.warning(f"Failed to update ETH price: {e}")

    async def get_large_transactions(
        self,
        limit: int = 20,
    ) -> list[EthereumTransaction]:
        """
        Получение крупных ETH транзакций через Etherscan.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[EthereumTransaction]: Список транзакций
        """
        await self._update_eth_price()

        min_value_eth = self.min_value_usd / self._eth_price

        if self.api_key:
            transactions = await self._get_from_etherscan(min_value_eth, limit)
            if transactions:
                return transactions

        # Резервный вариант через RPC (если Etherscan недоступен)
        logger.warning("Etherscan unavailable, trying RPC fallback")
        return await self._get_from_rpc(min_value_eth, limit)

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
            logger.warning("Etherscan API key not configured")
            return []

        try:
            session = await self._get_session()

            # Получаем последний блок
            params_block = {
                "module": "proxy",
                "action": "eth_blockNumber",
                "apikey": self.api_key,
            }

            async with session.get(
                ETHERSCAN_API_URL, params=params_block, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    logger.error(f"Etherscan block number error: {response.status}")
                    return []

                data = await response.json()
                if "result" not in data:
                    return []

                latest_block = int(data["result"], 16)

            # Получаем транзакции из последних блоков
            # Смотрим последние ~100 блоков (примерно 20 минут)
            start_block = latest_block - 100

            # Используем API для получения внутренних транзакций крупных адресов
            # или обычных транзакций
            transactions = []

            # Получаем транзакции из нескольких известных кошельков бирж
            exchange_addresses = [
                "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance
                "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43",  # Coinbase
                "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0",  # Kraken
            ]

            for address in exchange_addresses:
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": start_block,
                    "endblock": latest_block,
                    "page": 1,
                    "offset": 50,
                    "sort": "desc",
                    "apikey": self.api_key,
                }

                async with session.get(
                    ETHERSCAN_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status != 200:
                        continue

                    data = await response.json()
                    if data.get("status") != "1" or not data.get("result"):
                        continue

                    for tx in data["result"]:
                        value_wei = int(tx.get("value", 0))
                        value_eth = value_wei / 10**18
                        value_usd = value_eth * self._eth_price

                        if value_eth < min_value_eth:
                            continue

                        transactions.append(
                            EthereumTransaction(
                                tx_hash=tx.get("hash", ""),
                                from_address=tx.get("from", ""),
                                to_address=tx.get("to", ""),
                                value_eth=value_eth,
                                value_usd=value_usd,
                                token_symbol="ETH",
                                timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", 0))),
                                block_number=int(tx.get("blockNumber", 0)),
                            )
                        )

                # Небольшая задержка между запросами
                await asyncio.sleep(0.2)

            # Сортируем по времени и возвращаем уникальные
            seen_hashes = set()
            unique_transactions = []
            for tx in sorted(transactions, key=lambda x: x.timestamp or datetime.now(), reverse=True):
                if tx.tx_hash not in seen_hashes:
                    seen_hashes.add(tx.tx_hash)
                    unique_transactions.append(tx)
                    if len(unique_transactions) >= limit:
                        break

            return unique_transactions

        except asyncio.TimeoutError:
            logger.warning("Etherscan request timeout")
            return []
        except Exception as e:
            logger.error(f"Etherscan error: {e}")
            return []

    async def _get_from_rpc(
        self,
        min_value_eth: float,
        limit: int,
    ) -> list[EthereumTransaction]:
        """
        Резервное получение транзакций через публичные RPC ноды.

        Args:
            min_value_eth: Минимальная сумма в ETH
            limit: Максимальное количество транзакций

        Returns:
            list[EthereumTransaction]: Список транзакций (пустой если RPC недоступен)
        """
        # RPC не предоставляет историю транзакций напрямую
        # Возвращаем пустой список, так как это резервный вариант
        logger.info("RPC fallback: no historical data available")
        return []

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
            logger.warning("Etherscan API key not configured for ERC-20")
            return []

        try:
            session = await self._get_session()

            params = {
                "module": "account",
                "action": "tokentx",
                "contractaddress": token_contract,
                "page": 1,
                "offset": 100,
                "sort": "desc",
                "apikey": self.api_key,
            }

            async with session.get(
                ETHERSCAN_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    return []

                data = await response.json()
                if data.get("status") != "1" or not data.get("result"):
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

                    transactions.append(
                        EthereumTransaction(
                            tx_hash=tx.get("hash", ""),
                            from_address=tx.get("from", ""),
                            to_address=tx.get("to", ""),
                            value_eth=value,
                            value_usd=value_usd,
                            token_symbol=token_symbol,
                            timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", 0))),
                            block_number=int(tx.get("blockNumber", 0)),
                        )
                    )

                    if len(transactions) >= limit:
                        break

                return transactions

        except Exception as e:
            logger.error(f"ERC-20 tracking error: {e}")
            return []
