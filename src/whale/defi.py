"""
Gheezy Crypto - DeFi Transaction Tracker

Отслеживание крупных DeFi операций:
- Свопы на DEX (Uniswap, SushiSwap, Curve)
- Lending операции (Aave, Compound)
- Стейкинг операции (Lido)

Минимальные пороги:
- MIN_SWAP_USD: $100,000 для свопов
- MIN_LENDING_USD: $100,000 для lending
- MIN_STAKE_ETH: 100 ETH для стейкинга
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
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

# ===== Пороговые значения =====
MIN_SWAP_USD = 100_000
MIN_LENDING_USD = 100_000
MIN_STAKE_ETH = 100

# ===== DeFi Contract Addresses =====
# Uniswap
UNISWAP_V3_ROUTER = "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45"
UNISWAP_V2_ROUTER = "0x7a250d5630b4cf539739df2c5dacb4c659f2488d"
UNISWAP_UNIVERSAL_ROUTER = "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad"
UNISWAP_V3_QUOTER = "0xb27308f9f90d607463bb33ea1bebb41c27ce5ab6"

# Aave V3
AAVE_V3_POOL = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"
AAVE_V2_POOL = "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9"

# Lido
LIDO_STETH = "0xae7ab96520de3a18e5e111b5eaab095312d7fe84"
LIDO_WSTETH = "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"
LIDO_STAKING_POOL = "0xdc24316b9ae028f1497c275eb9192a3ea0f67022"

# Compound
COMPOUND_COMPTROLLER = "0x3d9819210a31b4961b30ef54be2aed79b9c9cd3b"
COMPOUND_CETH = "0x4ddc2d193948926d02f9b1fe9e1daa0718270ed5"
COMPOUND_CUSDC = "0x39aa39c021dfbae8fac545936693ac917d5e7563"

# Curve
CURVE_3POOL = "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7"
CURVE_STETH_POOL = "0xdc24316b9ae028f1497c275eb9192a3ea0f67022"

# SushiSwap
SUSHISWAP_ROUTER = "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f"

# 1inch
ONEINCH_ROUTER_V5 = "0x1111111254eeb25477b68fb85ed929f73a960582"

# MakerDAO
MAKER_VAT = "0x35d1b3f3d7966a1dfe207aa4514c12a259a0492b"

# All DeFi contracts to track
DEFI_CONTRACTS = {
    UNISWAP_V3_ROUTER: "Uniswap V3",
    UNISWAP_V2_ROUTER: "Uniswap V2",
    UNISWAP_UNIVERSAL_ROUTER: "Uniswap Universal",
    AAVE_V3_POOL: "Aave V3",
    AAVE_V2_POOL: "Aave V2",
    LIDO_STETH: "Lido stETH",
    LIDO_WSTETH: "Lido wstETH",
    LIDO_STAKING_POOL: "Lido Staking",
    COMPOUND_COMPTROLLER: "Compound",
    COMPOUND_CETH: "Compound cETH",
    COMPOUND_CUSDC: "Compound cUSDC",
    CURVE_3POOL: "Curve 3pool",
    SUSHISWAP_ROUTER: "SushiSwap",
    ONEINCH_ROUTER_V5: "1inch",
    MAKER_VAT: "MakerDAO",
}


class DeFiEventType(str, Enum):
    """Типы DeFi событий."""
    SWAP = "SWAP"
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    BORROW = "BORROW"
    REPAY = "REPAY"
    STAKE = "STAKE"
    UNSTAKE = "UNSTAKE"
    LIQUIDATION = "LIQUIDATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class DeFiEvent:
    """
    DeFi событие.

    Attributes:
        tx_hash: Хэш транзакции
        protocol: Название протокола
        event_type: Тип события
        amount_usd: Сумма в USD
        token_in: Входящий токен (для свопов)
        token_out: Выходящий токен (для свопов)
        amount_in: Количество входящего токена
        amount_out: Количество выходящего токена
        user_address: Адрес пользователя
        timestamp: Время события
    """

    tx_hash: str
    protocol: str
    event_type: DeFiEventType
    amount_usd: float
    token_in: Optional[str] = None
    token_out: Optional[str] = None
    amount_in: Optional[float] = None
    amount_out: Optional[float] = None
    user_address: Optional[str] = None
    timestamp: Optional[datetime] = None

    @property
    def formatted_amount(self) -> str:
        """Форматированная сумма в USD."""
        if self.amount_usd >= 1_000_000_000:
            return f"${self.amount_usd / 1_000_000_000:.2f}B"
        elif self.amount_usd >= 1_000_000:
            return f"${self.amount_usd / 1_000_000:.2f}M"
        elif self.amount_usd >= 1_000:
            return f"${self.amount_usd / 1_000:.2f}K"
        return f"${self.amount_usd:.2f}"

    @property
    def event_emoji(self) -> str:
        """Эмодзи для типа события."""
        emoji_map = {
            DeFiEventType.SWAP: "🔄",
            DeFiEventType.DEPOSIT: "📥",
            DeFiEventType.WITHDRAW: "📤",
            DeFiEventType.BORROW: "💳",
            DeFiEventType.REPAY: "💰",
            DeFiEventType.STAKE: "🥩",
            DeFiEventType.UNSTAKE: "🔓",
            DeFiEventType.LIQUIDATION: "⚠️",
            DeFiEventType.UNKNOWN: "❓",
        }
        return emoji_map.get(self.event_type, "❓")


class DeFiTracker:
    """
    Трекер крупных DeFi операций.

    Отслеживает:
    - Свопы на Uniswap, SushiSwap, Curve, 1inch
    - Lending на Aave, Compound
    - Стейкинг на Lido
    """

    def __init__(self):
        """Инициализация трекера."""
        self.min_swap_usd = MIN_SWAP_USD
        self.min_lending_usd = MIN_LENDING_USD
        self.min_stake_eth = MIN_STAKE_ETH
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._eth_price: float = 2000.0
        self._price_last_update: float = 0

        # Etherscan API
        self.api_key = getattr(settings, "etherscan_api_key", "")
        self.api_url = "https://api.etherscan.io/v2/api?chainid=1"

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
                            "DeFi: Цена ETH обновлена",
                            price=f"${self._eth_price}",
                        )
        except Exception as e:
            logger.warning(
                "DeFi: Ошибка при обновлении цены ETH",
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
    ) -> Optional[dict]:
        """Выполнение HTTP запроса с retry логикой."""
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=15)

        async with session.get(url, params=params, timeout=timeout) as response:
            if response.status == 200:
                return await response.json()
            logger.warning(
                "DeFi API запрос вернул ошибку",
                url=url,
                status=response.status,
            )
            return None

    async def get_large_swaps(self, limit: int = 20) -> list[DeFiEvent]:
        """
        Получение крупных свопов на DEX.

        Args:
            limit: Максимальное количество событий

        Returns:
            list[DeFiEvent]: Список крупных свопов
        """
        await self._update_eth_price()
        events = []

        if not self.api_key:
            logger.warning("DeFi: Etherscan API ключ не настроен")
            return events

        # Получаем транзакции для Uniswap роутеров
        routers = [UNISWAP_V3_ROUTER, UNISWAP_V2_ROUTER, UNISWAP_UNIVERSAL_ROUTER]

        for router in routers:
            try:
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": router,
                    "page": 1,
                    "offset": 50,
                    "sort": "desc",
                    "apikey": self.api_key,
                }

                data = await self._make_api_request(self.api_url, params=params)
                if not data or data.get("status") != "1":
                    continue

                for tx in data.get("result", []):
                    value_wei = int(tx.get("value", 0))
                    value_eth = value_wei / 10**18
                    value_usd = value_eth * self._eth_price

                    if value_usd < self.min_swap_usd:
                        continue

                    try:
                        timestamp = datetime.fromtimestamp(
                            int(tx.get("timeStamp", 0)), tz=timezone.utc
                        )
                    except (ValueError, OSError):
                        timestamp = datetime.now(timezone.utc)

                    protocol = DEFI_CONTRACTS.get(router, "Unknown DEX")
                    events.append(
                        DeFiEvent(
                            tx_hash=tx.get("hash", ""),
                            protocol=protocol,
                            event_type=DeFiEventType.SWAP,
                            amount_usd=value_usd,
                            user_address=tx.get("from", ""),
                            timestamp=timestamp,
                        )
                    )

                await asyncio.sleep(0.2)  # Rate limiting

            except Exception as e:
                logger.warning(f"DeFi: Ошибка получения свопов для {router}: {e}")

        # Сортируем по сумме и возвращаем топ
        events.sort(key=lambda x: x.amount_usd, reverse=True)
        return events[:limit]

    async def get_lending_events(self, limit: int = 20) -> list[DeFiEvent]:
        """
        Получение крупных lending операций (Aave, Compound).

        Args:
            limit: Максимальное количество событий

        Returns:
            list[DeFiEvent]: Список lending событий
        """
        await self._update_eth_price()
        events = []

        if not self.api_key:
            logger.warning("DeFi: Etherscan API ключ не настроен")
            return events

        # Aave V3 Pool
        lending_pools = [AAVE_V3_POOL, AAVE_V2_POOL, COMPOUND_CETH]

        for pool in lending_pools:
            try:
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": pool,
                    "page": 1,
                    "offset": 50,
                    "sort": "desc",
                    "apikey": self.api_key,
                }

                data = await self._make_api_request(self.api_url, params=params)
                if not data or data.get("status") != "1":
                    continue

                for tx in data.get("result", []):
                    value_wei = int(tx.get("value", 0))
                    value_eth = value_wei / 10**18
                    value_usd = value_eth * self._eth_price

                    if value_usd < self.min_lending_usd:
                        continue

                    try:
                        timestamp = datetime.fromtimestamp(
                            int(tx.get("timeStamp", 0)), tz=timezone.utc
                        )
                    except (ValueError, OSError):
                        timestamp = datetime.now(timezone.utc)

                    protocol = DEFI_CONTRACTS.get(pool, "Unknown Lending")

                    # Определяем тип события по направлению
                    from_addr = tx.get("from", "").lower()
                    to_addr = tx.get("to", "").lower()

                    if to_addr == pool.lower():
                        event_type = DeFiEventType.DEPOSIT
                    else:
                        event_type = DeFiEventType.WITHDRAW

                    events.append(
                        DeFiEvent(
                            tx_hash=tx.get("hash", ""),
                            protocol=protocol,
                            event_type=event_type,
                            amount_usd=value_usd,
                            user_address=from_addr,
                            timestamp=timestamp,
                        )
                    )

                await asyncio.sleep(0.2)

            except Exception as e:
                logger.warning(f"DeFi: Ошибка получения lending для {pool}: {e}")

        events.sort(key=lambda x: x.amount_usd, reverse=True)
        return events[:limit]

    async def get_staking_events(self, limit: int = 20) -> list[DeFiEvent]:
        """
        Получение крупных стейкинг операций (Lido).

        Args:
            limit: Максимальное количество событий

        Returns:
            list[DeFiEvent]: Список стейкинг событий
        """
        await self._update_eth_price()
        events = []

        if not self.api_key:
            logger.warning("DeFi: Etherscan API ключ не настроен")
            return events

        min_value_usd = self.min_stake_eth * self._eth_price

        try:
            params = {
                "module": "account",
                "action": "txlist",
                "address": LIDO_STETH,
                "page": 1,
                "offset": 100,
                "sort": "desc",
                "apikey": self.api_key,
            }

            data = await self._make_api_request(self.api_url, params=params)
            if not data or data.get("status") != "1":
                return events

            for tx in data.get("result", []):
                value_wei = int(tx.get("value", 0))
                value_eth = value_wei / 10**18
                value_usd = value_eth * self._eth_price

                if value_usd < min_value_usd:
                    continue

                try:
                    timestamp = datetime.fromtimestamp(
                        int(tx.get("timeStamp", 0)), tz=timezone.utc
                    )
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                events.append(
                    DeFiEvent(
                        tx_hash=tx.get("hash", ""),
                        protocol="Lido",
                        event_type=DeFiEventType.STAKE,
                        amount_usd=value_usd,
                        amount_in=value_eth,
                        token_in="ETH",
                        token_out="stETH",
                        user_address=tx.get("from", ""),
                        timestamp=timestamp,
                    )
                )

        except Exception as e:
            logger.warning(f"DeFi: Ошибка получения стейкинга: {e}")

        events.sort(key=lambda x: x.amount_usd, reverse=True)
        return events[:limit]

    async def get_all_defi_events(self, limit: int = 20) -> list[DeFiEvent]:
        """
        Получение всех DeFi событий.

        Args:
            limit: Максимальное количество событий

        Returns:
            list[DeFiEvent]: Список всех DeFi событий
        """
        # Запускаем все запросы параллельно
        swaps_task = self.get_large_swaps(limit=limit)
        lending_task = self.get_lending_events(limit=limit)
        staking_task = self.get_staking_events(limit=limit)

        results = await asyncio.gather(
            swaps_task, lending_task, staking_task,
            return_exceptions=True
        )

        all_events = []
        for result in results:
            if isinstance(result, list):
                all_events.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"DeFi: Ошибка получения событий: {result}")

        # Сортируем по времени
        all_events.sort(
            key=lambda x: x.timestamp if x.timestamp else datetime.now(timezone.utc),
            reverse=True,
        )

        return all_events[:limit]

    async def format_defi_message(self) -> str:
        """
        Форматирование сообщения о DeFi событиях для Telegram.

        Returns:
            str: Форматированное сообщение
        """
        events = await self.get_all_defi_events(limit=10)

        if not events:
            return (
                "🏦 *DeFi Tracker*\n\n"
                "📊 Нет крупных DeFi операций\n\n"
                f"_Минимальный порог:_\n"
                f"• Свопы: ${MIN_SWAP_USD:,}\n"
                f"• Lending: ${MIN_LENDING_USD:,}\n"
                f"• Стейкинг: {MIN_STAKE_ETH} ETH"
            )

        text = "🏦 *DeFi Tracker*\n\n"

        for i, event in enumerate(events[:10], 1):
            time_str = event.timestamp.strftime("%H:%M") if event.timestamp else "N/A"
            short_hash = f"{event.tx_hash[:8]}...{event.tx_hash[-4:]}"

            text += (
                f"{event.event_emoji} *{event.protocol}*\n"
                f"   {event.event_type.value}: {event.formatted_amount}\n"
                f"   🕐 {time_str} | `{short_hash}`\n\n"
            )

        text += (
            f"_Пороги: Swap ${MIN_SWAP_USD // 1000}K, "
            f"Lend ${MIN_LENDING_USD // 1000}K, "
            f"Stake {MIN_STAKE_ETH} ETH_"
        )

        return text
