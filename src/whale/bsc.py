"""
Gheezy Crypto - BSC Whale Tracker

Отслеживание крупных транзакций на Binance Smart Chain через BscScan API.
Работает в России без VPN.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import aiohttp
import structlog

from src.config import settings
from src.whale.known_wallets import get_bsc_wallet_label

logger = structlog.get_logger()

# BscScan API URL
BSCSCAN_API_URL = "https://api.bscscan.com/api"


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

    Использует BscScan API для мониторинга.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Инициализация трекера.

        Args:
            api_key: API ключ BscScan (опционально)
        """
        self.api_key = api_key or getattr(settings, "bscscan_api_key", "")
        self.min_value_usd = settings.whale_min_transaction
        self._session: Optional[aiohttp.ClientSession] = None
        self._bnb_price: float = 300.0  # Дефолтная цена BNB

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
        """Обновление цены BNB через CoinGecko."""
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
                        logger.info(f"BNB price updated: ${self._bnb_price}")
        except Exception as e:
            logger.warning(f"Failed to update BNB price: {e}")

    async def get_large_transactions(
        self,
        limit: int = 20,
    ) -> list[BSCTransaction]:
        """
        Получение крупных BNB транзакций через BscScan.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[BSCTransaction]: Список транзакций
        """
        await self._update_bnb_price()

        min_value_bnb = self.min_value_usd / self._bnb_price

        if self.api_key:
            return await self._get_from_bscscan(min_value_bnb, limit)

        logger.warning("BscScan API key not configured")
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
            session = await self._get_session()

            # Получаем последний блок
            params_block = {
                "module": "proxy",
                "action": "eth_blockNumber",
                "apikey": self.api_key,
            }

            async with session.get(
                BSCSCAN_API_URL, params=params_block, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    logger.error(f"BscScan block number error: {response.status}")
                    return []

                data = await response.json()
                if "result" not in data:
                    return []

                latest_block = int(data["result"], 16)

            # BSC блоки быстрее, смотрим последние ~200 блоков (примерно 10 минут)
            start_block = latest_block - 200

            transactions = []

            # Известные адреса бирж на BSC
            exchange_addresses = [
                "0x8894e0a0c962cb723c1976a4421c95949be2d4e3",  # Binance
                "0xe2fc31f816a9b94326492132018c3aecc4a93ae1",  # Binance Hot
                "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance
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
                    BSCSCAN_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status != 200:
                        continue

                    data = await response.json()
                    if data.get("status") != "1" or not data.get("result"):
                        continue

                    for tx in data["result"]:
                        value_wei = int(tx.get("value", 0))
                        value_bnb = value_wei / 10**18
                        value_usd = value_bnb * self._bnb_price

                        if value_bnb < min_value_bnb:
                            continue

                        transactions.append(
                            BSCTransaction(
                                tx_hash=tx.get("hash", ""),
                                from_address=tx.get("from", ""),
                                to_address=tx.get("to", ""),
                                value_bnb=value_bnb,
                                value_usd=value_usd,
                                token_symbol="BNB",
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
            logger.warning("BscScan request timeout")
            return []
        except Exception as e:
            logger.error(f"BscScan error: {e}")
            return []

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
            logger.warning("BscScan API key not configured for BEP-20")
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
                BSCSCAN_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)
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
                    if token_symbol.upper() in ("USDT", "USDC", "BUSD", "DAI"):
                        value_usd = value
                    else:
                        value_usd = value * 1.0

                    if value_usd < self.min_value_usd:
                        continue

                    transactions.append(
                        BSCTransaction(
                            tx_hash=tx.get("hash", ""),
                            from_address=tx.get("from", ""),
                            to_address=tx.get("to", ""),
                            value_bnb=value,
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
            logger.error(f"BEP-20 tracking error: {e}")
            return []
