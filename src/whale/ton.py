"""
Gheezy Crypto - TON Whale Tracker

Отслеживание крупных транзакций на TON через TON Center API.
Поддерживает отслеживание TON и Jettons (USDT, NOT, DOGS).
Работает в России без VPN.

Возможности:
- TON Center API (бесплатный)
- TON API (резервный)
- Отслеживание крупных TON транзакций
- Отслеживание Jettons
- Кэширование цен криптовалют
- Retry логика с exponential backoff
"""

import asyncio
import base64
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

# ===== API URLs =====
# TON Center API v2 (бесплатный, primary)
TONCENTER_API_URL = "https://toncenter.com/api/v2"

# TON Center API v3 (новая версия)
TONCENTER_API_V3_URL = "https://toncenter.com/api/v3"

# TON API (резервный)
TONAPI_URL = "https://tonapi.io/v2"

# Note: ORBS Network endpoint removed - returns 404 errors
# Note: GetBlock endpoint removed - requires API key

# TON address constants
# TON user-friendly address is 36 bytes: 1 byte flags + 1 byte workchain + 32 bytes address + 2 bytes CRC16
# However, some addresses may have slight variations, so we allow 35-36 bytes
TON_ADDRESS_MIN_BYTES = 35
TON_ADDRESS_MAX_BYTES = 36


def is_valid_ton_address(address: str) -> bool:
    """
    Check if TON address is valid.

    Args:
        address: TON address to validate

    Returns:
        bool: True if address is valid
    """
    if not address:
        return False

    # Raw format: workchain:64hex (e.g., 0:a3935861f79daf59a13d6d182e6811868c8879f13943b613aa5e423fec3dbe48)
    if ":" in address:
        parts = address.split(":")
        if len(parts) == 2:
            try:
                int(parts[0])  # workchain should be integer
                hex_part = parts[1]
                if len(hex_part) == 64:  # 32 bytes = 64 hex chars
                    # Validate that hex_part contains only valid hex characters
                    int(hex_part, 16)
                    return True
            except ValueError:
                pass
        return False

    # User-friendly format: 48 chars base64 (EQ/UQ/Ef/Uf/kQ/kf prefixes)
    if len(address) == 48:
        # Check valid prefixes for bounceable/non-bounceable addresses
        valid_prefixes = ("EQ", "UQ", "Ef", "Uf", "kQ", "kf")
        if address.startswith(valid_prefixes):
            return True
        # Also accept addresses that look like base64 even without standard prefix
        try:
            address_b64 = address.replace("-", "+").replace("_", "/")
            padding = 4 - len(address_b64) % 4
            if padding != 4:
                address_b64 += "=" * padding
            decoded = base64.b64decode(address_b64)
            if TON_ADDRESS_MIN_BYTES <= len(decoded) <= TON_ADDRESS_MAX_BYTES:
                return True
        except Exception:
            pass

    return False


def user_friendly_to_raw(address: str) -> str:
    """
    Конвертирует user-friendly TON адрес в raw формат.

    TON имеет 2 формата адресов:
    - User-friendly (с _ и -): EQCjk1hh952vWaE9bRguaBGGjIh58TlDaxOqXkI_7D2-SJ6I
    - Raw format (с : ): 0:a3935861f79daf59a13d6d182e6811868c8879f13943b613aa5e423fec3dbe48

    Args:
        address: Адрес в user-friendly формате

    Returns:
        str: Адрес в raw формате (workchain:hex).
             Возвращает оригинальный адрес без изменений если:
             - адрес пустой
             - адрес уже в raw формате (содержит ':')
             - возникла ошибка при конвертации
    """
    if not address:
        return address

    # Если уже raw формат, возвращаем как есть
    if ":" in address:
        return address

    try:
        # Заменяем URL-safe символы на стандартные base64
        address_b64 = address.replace("-", "+").replace("_", "/")

        # Добавляем padding если нужно
        padding = 4 - len(address_b64) % 4
        if padding != 4:
            address_b64 += "=" * padding

        # Декодируем base64
        decoded = base64.b64decode(address_b64)

        if len(decoded) < TON_ADDRESS_MIN_BYTES:
            logger.debug(f"Invalid TON address length: {len(decoded)}")
            return address

        # Первый байт - флаги (bounceable/testnet)
        # Второй байт - workchain
        workchain = decoded[1]
        if workchain > 127:
            workchain = workchain - 256

        # Следующие 32 байта - адрес
        address_bytes = decoded[2:34]
        address_hex = address_bytes.hex()

        return f"{workchain}:{address_hex}"

    except Exception as e:
        logger.debug(f"Error converting TON address: {e}")
        return address


class TransactionType(str, Enum):
    """Типы транзакций."""

    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    EXCHANGE_TRANSFER = "EXCHANGE_TRANSFER"
    WHALE_TRANSFER = "WHALE_TRANSFER"
    DEX_SWAP = "DEX_SWAP"
    UNKNOWN = "UNKNOWN"


# ===== Известные адреса TON =====
TON_EXCHANGES: dict[str, str] = {
    # Binance
    "EQCjk1hh952vWaE9bRguaBGGjIh58TlDaxOqXkI_7D2-SJ6I": "Binance",
    "EQDvJkkZlTjBsn9kXQlkZcJb4_3jgD75HbjVv8w8tshO4KhI": "Binance Hot",
    # OKX - valid address format
    "EQBfAN7LfaUYgXZNw5Wc7GBgkEX2yhuJ5ka95J1JJwXiD4sO": "OKX",
    "EQCuPm-skZKcMv7cUeDCf6wZZ3dZMxHJ_8KnZkh_lsS_kARI": "OKX Hot",
    # Bybit
    "EQDzd8aeBou6Vj3csxe8Lh6CtACwpf-3VgbHsLdFH5swaGFQ": "Bybit",
    "EQDD8dqOzaj4zUK6ziJOo_G2lx6qf1TEktTRkFJ7T1c_fPQb": "Bybit Hot",
    # KuCoin
    "EQBDanbCeUqI4_v-xrnAN0_I2wRvEIaLg1a4ecR7_8NZI6SG": "KuCoin",
    # Gate.io
    "EQA2kCVNwVsil2EM2mB0SkXytxCqWj4gBYqPNbZXPT39_xIO": "Gate.io",
    # MEXC
    "EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N": "MEXC",
    # Crypto.com
    "EQC9_fZ4z9G5hfE7eQiWp5rMvQwvLv-BmxCm1p9Fq4rPF8XJ": "Crypto.com",
    # DEX - STON.fi
    "EQB3ncyBUTjZUA5EnFKR5_EnOMI9V1tTEAAPaiU71gc4TiUt": "STON.fi",
    "EQBsGx9ArADUrREB34W-ghgsCgBShvfUr4Jk5a4MQxpD7JFX": "STON.fi Router",
    "EQARULUYsmJq1RiZ-YiH-IJLcAZUVkVff-KBPwEmmaQGH6aC": "STON.fi Pool",
    # DEX - DeDust
    "EQBfBWT7X2BHg9tXAxzhz2aKvn6xHy_CUv4qkBJ9pwxvQ3Ff": "DeDust",
    "EQDa4VOnTYlLvDJ0gZjNYm5PXfSmmtL6Vs6A_CZEtXCNICq_": "DeDust Vault",
    # Fragment
    "EQBAjaOyi2wGWlk-EDkSabqqnF-MrrwMadnwqrurKpkla9nE": "Fragment",
    "EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqFRA": "Fragment Auction",
    # Getgems (NFT)
    "EQDrLq-X6jKZNHAScgghh0h1iog3StK71zn8dcmrOj8jPWRA": "Getgems",
    "EQCjk1hh952vWaE9bRguaBGGjIh58TlDaxOqXkI_7D2JMaTH": "Getgems Marketplace",
    # Wallet Apps
    "EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG": "Wallet App",
    "EQBTGfs1SVsdtwmQRqDeZZLkzA2DdPFW-G7x53bK0FdY2PLQ": "Tonkeeper",
}

# Известные киты TON
TON_WHALES: dict[str, str] = {
    "EQAUZyAC52VvhiM_GHiXxYfASpFXG1nGPBrRfh1F1jSsqHPI": "TON Whale 1",
    "Ef8zMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM0vF": "TON Whale 2",
}


def get_ton_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для TON адреса.

    Args:
        address: Адрес кошелька TON

    Returns:
        str: Метка адреса или None если адрес неизвестен
    """
    if address in TON_EXCHANGES:
        return TON_EXCHANGES[address]
    if address in TON_WHALES:
        return TON_WHALES[address]
    return None


def is_ton_exchange_address(address: str) -> bool:
    """
    Проверить, является ли адрес адресом биржи.

    Args:
        address: Адрес кошелька

    Returns:
        bool: True если адрес принадлежит бирже
    """
    label = get_ton_wallet_label(address)
    if label is None:
        return False
    exchange_keywords = [
        "binance",
        "okx",
        "bybit",
        "kucoin",
        "gate",
        "mexc",
        "crypto.com",
    ]
    label_lower = label.lower()
    return any(keyword in label_lower for keyword in exchange_keywords)


def is_ton_dex_address(address: str) -> bool:
    """
    Проверить, является ли адрес адресом DEX.

    Args:
        address: Адрес кошелька

    Returns:
        bool: True если адрес принадлежит DEX
    """
    label = get_ton_wallet_label(address)
    if label is None:
        return False
    dex_keywords = ["ston.fi", "dedust"]
    label_lower = label.lower()
    return any(keyword in label_lower for keyword in dex_keywords)


@dataclass
class TONTransaction:
    """
    Транзакция на TON.

    Attributes:
        tx_hash: Хэш транзакции
        from_address: Адрес отправителя
        to_address: Адрес получателя
        value_ton: Сумма в TON
        value_usd: Сумма в USD
        token_symbol: Символ токена (TON или Jetton)
        timestamp: Время транзакции
        lt: Logical time
        tx_type: Тип транзакции
    """

    tx_hash: str
    from_address: str
    to_address: str
    value_ton: float
    value_usd: float
    token_symbol: str = "TON"
    timestamp: Optional[datetime] = None
    lt: Optional[int] = None
    tx_type: TransactionType = TransactionType.UNKNOWN

    @property
    def from_label(self) -> Optional[str]:
        """Метка отправителя."""
        return get_ton_wallet_label(self.from_address)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_ton_wallet_label(self.to_address)

    def get_transaction_type(self) -> TransactionType:
        """Определить тип транзакции."""
        from_is_exchange = is_ton_exchange_address(self.from_address)
        to_is_exchange = is_ton_exchange_address(self.to_address)
        from_is_dex = is_ton_dex_address(self.from_address)
        to_is_dex = is_ton_dex_address(self.to_address)

        if from_is_dex or to_is_dex:
            return TransactionType.DEX_SWAP
        if from_is_exchange and to_is_exchange:
            return TransactionType.EXCHANGE_TRANSFER
        if to_is_exchange:
            return TransactionType.DEPOSIT
        if from_is_exchange:
            return TransactionType.WITHDRAWAL
        if self.from_label or self.to_label:
            return TransactionType.WHALE_TRANSFER
        return TransactionType.UNKNOWN


class TONTracker:
    """
    Трекер крупных транзакций на TON.

    Использует TON Center API для получения данных.
    Работает без API ключа (с ограничениями rate limit).

    Особенности:
    - Кэширование цен криптовалют
    - Retry логика с exponential backoff
    """

    def __init__(self):
        """Инициализация трекера."""
        self.min_value_usd = settings.whale_min_transaction
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._ton_price: float = 5.0  # Дефолтная цена TON
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

    async def _update_ton_price(self) -> None:
        """
        Обновление цены TON через CoinGecko с кэшированием.
        """
        current_time = time.time()

        if current_time - self._price_last_update < self.price_cache_ttl:
            logger.debug(
                "Используем кэшированную цену TON",
                price=self._ton_price,
                cache_age=int(current_time - self._price_last_update),
            )
            return

        try:
            session = await self._get_session()
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "the-open-network", "vs_currencies": "usd"}
            timeout = aiohttp.ClientTimeout(total=10)

            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if "the-open-network" in data and "usd" in data["the-open-network"]:
                        self._ton_price = data["the-open-network"]["usd"]
                        self._price_last_update = current_time
                        logger.info(
                            "Цена TON обновлена",
                            price=f"${self._ton_price}",
                        )
                else:
                    logger.warning(
                        "CoinGecko API вернул ошибку",
                        status=response.status,
                    )
        except asyncio.TimeoutError:
            logger.warning("Таймаут при получении цены TON")
        except Exception as e:
            logger.warning(
                "Ошибка при обновлении цены TON",
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
    ) -> Optional[dict | list]:
        """
        Выполнение HTTP запроса с retry логикой.

        Args:
            url: URL для запроса
            params: GET параметры

        Returns:
            dict | list: Ответ API или None при ошибке
        """
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=8)  # Reduced from 20
        headers = {
            "Accept": "application/json",
            "User-Agent": "GheezyCrypto/1.0",
        }

        async with session.get(
            url, params=params, timeout=timeout, headers=headers
        ) as response:
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
    ) -> list[TONTransaction]:
        """
        Получение крупных TON транзакций.

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[TONTransaction]: Список транзакций
        """
        await self._update_ton_price()
        min_value_ton = self.min_value_usd / self._ton_price

        # Пробуем TON Center V3 (новая версия)
        logger.debug("Пробуем получить данные через TON Center V3")
        transactions = await self._get_from_toncenter_v3(min_value_ton, limit)
        if transactions:
            logger.info(
                "Данные получены через TON Center V3",
                count=len(transactions),
            )
            return transactions

        # Пробуем TON Center V2
        logger.debug("Пробуем получить данные через TON Center V2")
        transactions = await self._get_from_toncenter(min_value_ton, limit)
        if transactions:
            logger.info(
                "Данные получены через TON Center V2",
                count=len(transactions),
            )
            return transactions

        # Пробуем TON API (резервный)
        logger.debug("Пробуем получить данные через TON API")
        transactions = await self._get_from_tonapi(min_value_ton, limit)
        if transactions:
            logger.info(
                "Данные получены через TON API",
                count=len(transactions),
            )
            return transactions

        # Note: ORBS Network fallback removed - endpoint returns 404 errors
        logger.warning("Не удалось получить TON транзакции")
        return []

    async def _get_from_toncenter_v3(
        self,
        min_value_ton: float,
        limit: int,
    ) -> list[TONTransaction]:
        """
        Получение транзакций через TON Center API V3 (новая версия).

        Args:
            min_value_ton: Минимальная сумма в TON
            limit: Максимальное количество транзакций

        Returns:
            list[TONTransaction]: Список транзакций
        """
        try:
            transactions = []

            # Reduced to 4 addresses for performance optimization
            for address in list(TON_EXCHANGES.keys())[:4]:
                txs = await self._fetch_address_transactions_toncenter_v3(
                    address, min_value_ton
                )
                transactions.extend(txs)
                if len(transactions) >= limit * 2:
                    break
                # Увеличиваем задержку для избежания rate limit
                await asyncio.sleep(1.5)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.debug(
                "Ошибка TON Center V3 API",
                error=str(e),
            )
            return []

    async def _fetch_address_transactions_toncenter_v3(
        self,
        address: str,
        min_value_ton: float,
    ) -> list[TONTransaction]:
        """
        Получение транзакций для адреса через TON Center V3.

        Args:
            address: Адрес кошелька
            min_value_ton: Минимальная сумма в TON

        Returns:
            list[TONTransaction]: Список транзакций
        """
        try:
            # Validate address before making API call
            if not is_valid_ton_address(address):
                logger.debug(f"Skipping invalid TON address: {address}")
                return []

            # Конвертируем адрес в raw формат для API
            raw_address = user_friendly_to_raw(address)

            url = f"{TONCENTER_API_V3_URL}/transactions"
            params = {
                "account": raw_address,
                "limit": 10,
            }

            data = await self._make_api_request(url, params=params)
            if not data or "transactions" not in data:
                return []

            transactions = []
            for tx in data.get("transactions", []):
                if not isinstance(tx, dict):
                    continue

                # Парсим входящие сообщения
                in_msg = tx.get("in_msg", {})
                if not in_msg:
                    continue

                # Парсим сумму
                value_nano = int(in_msg.get("value", 0) or 0)
                value_ton = value_nano / 1_000_000_000

                if value_ton < min_value_ton:
                    continue

                value_usd = value_ton * self._ton_price

                # Адреса
                from_addr = in_msg.get("source", "")
                to_addr = in_msg.get("destination", "") or address

                # Время
                try:
                    utime = tx.get("now", 0) or tx.get("utime", 0)
                    timestamp = (
                        datetime.fromtimestamp(utime, tz=timezone.utc)
                        if utime
                        else None
                    )
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                # Хэш транзакции
                tx_hash = tx.get("hash", "")

                tx_obj = TONTransaction(
                    tx_hash=tx_hash,
                    from_address=from_addr,
                    to_address=to_addr,
                    value_ton=value_ton,
                    value_usd=value_usd,
                    token_symbol="TON",
                    timestamp=timestamp,
                    lt=tx.get("lt"),
                )
                tx_obj.tx_type = tx_obj.get_transaction_type()
                transactions.append(tx_obj)

            return transactions

        except Exception as e:
            logger.debug(f"Ошибка при получении транзакций адреса V3 {address}: {e}")
            return []

    async def _get_from_toncenter(
        self,
        min_value_ton: float,
        limit: int,
    ) -> list[TONTransaction]:
        """
        Получение транзакций через TON Center API.

        Args:
            min_value_ton: Минимальная сумма в TON
            limit: Максимальное количество транзакций

        Returns:
            list[TONTransaction]: Список транзакций
        """
        try:
            transactions = []

            # Reduced to 4 addresses for performance optimization
            for address in list(TON_EXCHANGES.keys())[:4]:
                txs = await self._fetch_address_transactions_toncenter(
                    address, min_value_ton
                )
                transactions.extend(txs)
                if len(transactions) >= limit * 2:
                    break
                # Увеличиваем задержку для избежания 429 ошибок
                await asyncio.sleep(1.0)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.warning(
                "Ошибка TON Center API",
                error=str(e),
            )
            return []

    async def _fetch_address_transactions_toncenter(
        self,
        address: str,
        min_value_ton: float,
    ) -> list[TONTransaction]:
        """
        Получение транзакций для адреса через TON Center.

        Args:
            address: Адрес кошелька
            min_value_ton: Минимальная сумма в TON

        Returns:
            list[TONTransaction]: Список транзакций
        """
        try:
            # Validate address before making API call
            if not is_valid_ton_address(address):
                logger.debug(f"Skipping invalid TON address: {address}")
                return []

            # Конвертируем адрес в raw формат для API
            raw_address = user_friendly_to_raw(address)

            url = f"{TONCENTER_API_URL}/getTransactions"
            # Исправленные параметры для TON Center API
            # Используем raw формат адреса
            params = {
                "address": raw_address,
                "limit": 10,  # Уменьшаем лимит для снижения нагрузки
                "archival": "false",
            }

            data = await self._make_api_request(url, params=params)
            if not data or not data.get("ok"):
                return []

            transactions = []
            result = data.get("result", [])

            for tx in result:
                if not isinstance(tx, dict):
                    continue

                # Получаем входящие сообщения
                in_msg = tx.get("in_msg", {})
                if not in_msg:
                    continue

                # Парсим сумму
                value_nano = int(in_msg.get("value", 0) or 0)
                value_ton = value_nano / 1_000_000_000

                if value_ton < min_value_ton:
                    continue

                value_usd = value_ton * self._ton_price

                # Адреса
                from_addr = in_msg.get("source", "")
                to_addr = in_msg.get("destination", "") or address

                # Время
                try:
                    utime = tx.get("utime", 0)
                    timestamp = (
                        datetime.fromtimestamp(utime, tz=timezone.utc)
                        if utime
                        else None
                    )
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                # Хэш транзакции
                tx_hash = tx.get("transaction_id", {}).get("hash", "")

                tx_obj = TONTransaction(
                    tx_hash=tx_hash,
                    from_address=from_addr,
                    to_address=to_addr,
                    value_ton=value_ton,
                    value_usd=value_usd,
                    token_symbol="TON",
                    timestamp=timestamp,
                    lt=tx.get("transaction_id", {}).get("lt"),
                )
                tx_obj.tx_type = tx_obj.get_transaction_type()
                transactions.append(tx_obj)

            return transactions

        except Exception as e:
            logger.debug(f"Ошибка при получении транзакций адреса {address}: {e}")
            return []

    async def _get_from_tonapi(
        self,
        min_value_ton: float,
        limit: int,
    ) -> list[TONTransaction]:
        """
        Получение транзакций через TON API (резервный).

        Args:
            min_value_ton: Минимальная сумма в TON
            limit: Максимальное количество транзакций

        Returns:
            list[TONTransaction]: Список транзакций
        """
        try:
            transactions = []

            # Reduced to 4 addresses for performance optimization
            for address in list(TON_EXCHANGES.keys())[:4]:
                txs = await self._fetch_address_transactions_tonapi(
                    address, min_value_ton
                )
                transactions.extend(txs)
                if len(transactions) >= limit * 2:
                    break
                await asyncio.sleep(0.5)  # Увеличенная задержка

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.warning(
                "Ошибка TON API",
                error=str(e),
            )
            return []

    async def _fetch_address_transactions_tonapi(
        self,
        address: str,
        min_value_ton: float,
    ) -> list[TONTransaction]:
        """
        Получение транзакций для адреса через TON API.

        Args:
            address: Адрес кошелька
            min_value_ton: Минимальная сумма в TON

        Returns:
            list[TONTransaction]: Список транзакций
        """
        try:
            # Validate address before making API call
            if not is_valid_ton_address(address):
                logger.debug(f"Skipping invalid TON address: {address}")
                return []

            # Конвертируем адрес в raw формат для API
            raw_address = user_friendly_to_raw(address)

            url = f"{TONAPI_URL}/blockchain/accounts/{raw_address}/transactions"
            params = {"limit": 10}  # Уменьшаем лимит

            data = await self._make_api_request(url, params=params)
            if not data:
                return []

            transactions = []
            txs_list = data.get("transactions", [])

            for tx in txs_list:
                if not isinstance(tx, dict):
                    continue

                # Парсим входящие сообщения
                in_msg = tx.get("in_msg", {})
                if not in_msg:
                    continue

                value_nano = int(in_msg.get("value", 0) or 0)
                value_ton = value_nano / 1_000_000_000

                if value_ton < min_value_ton:
                    continue

                value_usd = value_ton * self._ton_price

                from_addr = in_msg.get("source", {}).get("address", "")
                to_addr = in_msg.get("destination", {}).get("address", "") or address

                try:
                    utime = tx.get("utime", 0)
                    timestamp = (
                        datetime.fromtimestamp(utime, tz=timezone.utc)
                        if utime
                        else None
                    )
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                tx_obj = TONTransaction(
                    tx_hash=tx.get("hash", ""),
                    from_address=from_addr,
                    to_address=to_addr,
                    value_ton=value_ton,
                    value_usd=value_usd,
                    token_symbol="TON",
                    timestamp=timestamp,
                    lt=tx.get("lt"),
                )
                tx_obj.tx_type = tx_obj.get_transaction_type()
                transactions.append(tx_obj)

            return transactions

        except Exception as e:
            logger.debug(f"Ошибка при получении транзакций через TON API: {e}")
            return []

    async def _get_from_orbs(
        self,
        min_value_ton: float,
        limit: int,
    ) -> list[TONTransaction]:
        """
        DEPRECATED: ORBS Network endpoint removed (returns 404).

        This method is kept for backward compatibility but always returns empty list.

        Args:
            min_value_ton: Минимальная сумма в TON
            limit: Максимальное количество транзакций

        Returns:
            list[TONTransaction]: Empty list (ORBS endpoint disabled)
        """
        logger.debug("ORBS Network endpoint disabled - returns 404 errors")
        return []

    async def _fetch_address_transactions_orbs(
        self,
        address: str,
        min_value_ton: float,
    ) -> list[TONTransaction]:
        """
        DEPRECATED: ORBS Network endpoint removed (returns 404).

        This method is kept for backward compatibility but always returns empty list.

        Args:
            address: Адрес кошелька
            min_value_ton: Минимальная сумма в TON

        Returns:
            list[TONTransaction]: Empty list (ORBS endpoint disabled)
        """
        logger.debug("ORBS Network endpoint disabled - returns 404 errors")
        return []

    def _deduplicate_and_sort(
        self,
        transactions: list[TONTransaction],
        limit: int,
    ) -> list[TONTransaction]:
        """
        Удаление дубликатов и сортировка транзакций.

        Args:
            transactions: Список транзакций
            limit: Максимальное количество

        Returns:
            list[TONTransaction]: Отсортированный список уникальных транзакций
        """
        seen_hashes = set()
        unique_transactions = []

        for tx in sorted(
            transactions,
            key=lambda x: x.value_usd,
            reverse=True,
        ):
            if tx.tx_hash and tx.tx_hash not in seen_hashes:
                seen_hashes.add(tx.tx_hash)
                unique_transactions.append(tx)
                if len(unique_transactions) >= limit:
                    break

        return unique_transactions

    async def get_jetton_transactions(
        self,
        jetton_master: str,
        limit: int = 20,
    ) -> list[TONTransaction]:
        """
        Получение крупных Jetton транзакций.

        Args:
            jetton_master: Адрес мастер-контракта Jetton
            limit: Максимальное количество транзакций

        Returns:
            list[TONTransaction]: Список транзакций
        """
        try:
            url = f"{TONAPI_URL}/jettons/{jetton_master}/transfers"
            params = {"limit": limit * 2}

            data = await self._make_api_request(url, params=params)
            if not data:
                return []

            transactions = []
            min_value_usd = self.min_value_usd

            for transfer in data.get("transfers", []):
                if not isinstance(transfer, dict):
                    continue

                # Получаем данные токена
                jetton = transfer.get("jetton", {})
                decimals = int(jetton.get("decimals", 9))
                symbol = jetton.get("symbol", "JETTON")

                amount = int(transfer.get("amount", 0))
                value = amount / (10**decimals)

                # Для стейблкоинов цена = 1 USD
                if symbol.upper() in ("USDT", "USDC"):
                    value_usd = value
                else:
                    value_usd = value * 1.0

                if value_usd < min_value_usd:
                    continue

                from_addr = transfer.get("sender", {}).get("address", "")
                to_addr = transfer.get("receiver", {}).get("address", "")

                try:
                    timestamp = datetime.fromisoformat(
                        transfer.get("timestamp", "").replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    timestamp = datetime.now(timezone.utc)

                tx_obj = TONTransaction(
                    tx_hash=transfer.get("transaction_hash", ""),
                    from_address=from_addr,
                    to_address=to_addr,
                    value_ton=value,
                    value_usd=value_usd,
                    token_symbol=symbol,
                    timestamp=timestamp,
                )
                tx_obj.tx_type = tx_obj.get_transaction_type()
                transactions.append(tx_obj)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.error(
                "Ошибка при получении Jetton транзакций",
                error=str(e),
            )
            return []
