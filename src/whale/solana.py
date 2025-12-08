"""
Gheezy Crypto - Solana Whale Tracker

Отслеживание крупных транзакций на Solana через Solscan API.
Поддерживает отслеживание SOL и SPL токенов.
Работает в России без VPN.

Возможности:
- Solscan Public API (бесплатный)
- Отслеживание крупных SOL транзакций
- Отслеживание SPL токенов (USDC, USDT, мемкоины)
- Кэширование цен криптовалют
- Retry логика с exponential backoff
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

# ===== API URLs =====
# Solscan Pro API (requires API key, but has public endpoints)
SOLSCAN_API_URL = "https://pro-api.solscan.io/v2.0"

# Solscan Public API v1 (legacy, limited functionality)
SOLSCAN_PUBLIC_API_URL = "https://public-api.solscan.io"

# Solana RPC URL (резервный)
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

# Helius API (Priority 1) - 100k requests/day free
HELIUS_API_URL = "https://api.helius.xyz/v0"

# Jupiter API (Priority 2) - fully free
JUPITER_API_URL = "https://api.jup.ag"
JUPITER_STATS_URL = "https://stats.jup.ag"

# SolanaTracker API (Priority 3) - Raydium, Pumpfun, Orca data
SOLANA_TRACKER_API_URL = "https://data.solanatracker.io"

# Public Solana RPC endpoints (fallback)
PUBLIC_SOLANA_RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
    "https://rpc.ankr.com/solana",
    "https://solana.publicnode.com",
]


class TransactionType(str, Enum):
    """Типы транзакций."""
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    EXCHANGE_TRANSFER = "EXCHANGE_TRANSFER"
    WHALE_TRANSFER = "WHALE_TRANSFER"
    DEX_SWAP = "DEX_SWAP"
    UNKNOWN = "UNKNOWN"


# ===== Известные адреса Solana =====
SOLANA_EXCHANGES: dict[str, str] = {
    # Binance
    "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9": "Binance",
    "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM": "Binance Hot",
    "2ojv9BAiHUrvsm9gxDe7fJSzbNZSJcxZvf8dqmWGHG8S": "Binance Cold",

    # Coinbase
    "H8sMJSCQxfKiFTCfDR3DUMLPwcRbM61LGFJ8N4dK3WjS": "Coinbase",
    "GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE": "Coinbase Prime",

    # Kraken
    "CuieVDEDtLo7FypA9SbLM9saXFdb1dsshEkyErMqkRQq": "Kraken",
    "6WM1MnqH5t3iNvn9JQpUKPMnGunH5t3rNvn9JQpUKPMn": "Kraken Hot",

    # OKX
    "5VCwKtCXgCJ6kit5FybXjvriW3xELsFDhYrPSqtJNmcD": "OKX",
    "AobVSwdW9BbpMdJvTqeCN4hPAmh4rHm7vwLnQ5ATSyrS": "OKX Hot",

    # Bybit
    "AC5RDfQFmDS1deWZos921JfqscXdByf8BKHs5ACWjtW2": "Bybit",

    # KuCoin
    "BmFdpraQhkiDQE6SnfG5omcA1VwzqfXrwtNYBwWTymy6": "KuCoin",

    # Gate.io
    "u6PJ8DtQuPFnfmwHbGFULQ4u4EgjDiyYKjVEsynXq2w": "Gate.io",

    # DEX - Raydium
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM",
    "5quBtoiQqxF9Jv6KYKctB59NT3gtJD2Y65kdnB1Uev3h": "Raydium Authority",

    # DEX - Jupiter
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter V6",
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB": "Jupiter V4",

    # DEX - Orca
    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": "Orca",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",

    # NFT - Magic Eden
    "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K": "Magic Eden V2",
    "1BWutmTvYPwDtmw9abTkS4Ssr8no61spGAvW1X6NDix": "Magic Eden Wallet",

    # NFT - Tensor
    "TSWAPaqyCSx2KABk68Shruf4rp7CxcNi8hAsbdwmHbN": "Tensor",

    # Memecoins - Pump.fun
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "Pump.fun",

    # Memecoins - Moonshot
    "MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG": "Moonshot",

    # Staking
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "Marinade Staked SOL",
    "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn": "Jito Staked SOL",
}

# Известные киты Solana
SOLANA_WHALES: dict[str, str] = {
    "4wBqpZM9k9xMd3CkFEj4Y7FHG5Qq3A8JiSqrMhknV1q8": "SOL Whale 1",
    "9BVr2V9w2FcLMUPQQh8xJk8mJ8qehmNjHdELQ5hUAqYS": "SOL Whale 2",
    "DRpbCBMxVnDK7maPM5tGv6MvB3v1sRMC86PZ8okm21hy": "SOL Whale 3",
}


def get_solana_wallet_label(address: str) -> Optional[str]:
    """
    Получить метку для Solana адреса.

    Args:
        address: Адрес кошелька Solana

    Returns:
        str: Метка адреса или None если адрес неизвестен
    """
    if address in SOLANA_EXCHANGES:
        return SOLANA_EXCHANGES[address]
    if address in SOLANA_WHALES:
        return SOLANA_WHALES[address]
    return None


def is_solana_exchange_address(address: str) -> bool:
    """
    Проверить, является ли адрес адресом биржи.

    Args:
        address: Адрес кошелька

    Returns:
        bool: True если адрес принадлежит бирже
    """
    label = get_solana_wallet_label(address)
    if label is None:
        return False
    exchange_keywords = [
        "binance", "coinbase", "kraken", "okx", "bybit",
        "kucoin", "gate"
    ]
    label_lower = label.lower()
    return any(keyword in label_lower for keyword in exchange_keywords)


def is_solana_dex_address(address: str) -> bool:
    """
    Проверить, является ли адрес адресом DEX.

    Args:
        address: Адрес кошелька

    Returns:
        bool: True если адрес принадлежит DEX
    """
    label = get_solana_wallet_label(address)
    if label is None:
        return False
    dex_keywords = ["raydium", "jupiter", "orca", "whirlpool"]
    label_lower = label.lower()
    return any(keyword in label_lower for keyword in dex_keywords)


@dataclass
class SolanaTransaction:
    """
    Транзакция на Solana.

    Attributes:
        tx_hash: Хэш транзакции (signature)
        from_address: Адрес отправителя
        to_address: Адрес получателя
        value_sol: Сумма в SOL
        value_usd: Сумма в USD
        token_symbol: Символ токена (SOL или SPL)
        timestamp: Время транзакции
        slot: Номер слота
        tx_type: Тип транзакции
    """

    tx_hash: str
    from_address: str
    to_address: str
    value_sol: float
    value_usd: float
    token_symbol: str = "SOL"
    timestamp: Optional[datetime] = None
    slot: Optional[int] = None
    tx_type: TransactionType = TransactionType.UNKNOWN

    @property
    def from_label(self) -> Optional[str]:
        """Метка отправителя."""
        return get_solana_wallet_label(self.from_address)

    @property
    def to_label(self) -> Optional[str]:
        """Метка получателя."""
        return get_solana_wallet_label(self.to_address)

    def get_transaction_type(self) -> TransactionType:
        """Определить тип транзакции."""
        from_is_exchange = is_solana_exchange_address(self.from_address)
        to_is_exchange = is_solana_exchange_address(self.to_address)
        from_is_dex = is_solana_dex_address(self.from_address)
        to_is_dex = is_solana_dex_address(self.to_address)

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


class SolanaTracker:
    """
    Трекер крупных транзакций на Solana.

    Использует Solscan Public API для получения данных.
    Работает без API ключа.

    Особенности:
    - Кэширование цен криптовалют
    - Retry логика с exponential backoff
    """

    def __init__(self):
        """Инициализация трекера."""
        self.min_value_usd = settings.whale_min_transaction
        self.price_cache_ttl = getattr(settings, "whale_price_cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        self._sol_price: float = 150.0  # Дефолтная цена SOL
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

    async def _update_sol_price(self) -> None:
        """
        Обновление цены SOL через CoinGecko с кэшированием.
        """
        current_time = time.time()

        if current_time - self._price_last_update < self.price_cache_ttl:
            logger.debug(
                "Используем кэшированную цену SOL",
                price=self._sol_price,
                cache_age=int(current_time - self._price_last_update),
            )
            return

        try:
            session = await self._get_session()
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "solana", "vs_currencies": "usd"}
            timeout = aiohttp.ClientTimeout(total=10)

            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if "solana" in data and "usd" in data["solana"]:
                        self._sol_price = data["solana"]["usd"]
                        self._price_last_update = current_time
                        logger.info(
                            "Цена SOL обновлена",
                            price=f"${self._sol_price}",
                        )
                else:
                    logger.warning(
                        "CoinGecko API вернул ошибку",
                        status=response.status,
                    )
        except asyncio.TimeoutError:
            logger.warning("Таймаут при получении цены SOL")
        except Exception as e:
            logger.warning(
                "Ошибка при обновлении цены SOL",
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
        timeout = aiohttp.ClientTimeout(total=20)
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
    ) -> list[SolanaTransaction]:
        """
        Получение крупных SOL транзакций с приоритетным fallback.

        Порядок попыток:
        1. Helius API (Priority 1)
        2. Jupiter API (Priority 2)
        3. SolanaTracker API (Priority 3)
        4. Solscan API (fallback)
        5. Solana RPC (резервный)

        Args:
            limit: Максимальное количество транзакций

        Returns:
            list[SolanaTransaction]: Список транзакций
        """
        await self._update_sol_price()
        min_value_sol = self.min_value_usd / self._sol_price

        # Priority 1: Helius API
        logger.debug("Пробуем получить данные через Helius API")
        transactions = await self._get_from_helius(min_value_sol, limit)
        if transactions:
            logger.info(
                "Данные получены через Helius API",
                count=len(transactions),
            )
            return transactions

        # Priority 2: Jupiter API
        logger.debug("Пробуем получить данные через Jupiter API")
        transactions = await self._get_from_jupiter(min_value_sol, limit)
        if transactions:
            logger.info(
                "Данные получены через Jupiter API",
                count=len(transactions),
            )
            return transactions

        # Priority 3: SolanaTracker API
        logger.debug("Пробуем получить данные через SolanaTracker API")
        transactions = await self._get_from_solana_tracker(min_value_sol, limit)
        if transactions:
            logger.info(
                "Данные получены через SolanaTracker API",
                count=len(transactions),
            )
            return transactions

        # Fallback: Solscan API
        logger.debug("Пробуем получить данные через Solscan")
        transactions = await self._get_from_solscan(min_value_sol, limit)
        if transactions:
            logger.info(
                "Данные получены через Solscan",
                count=len(transactions),
            )
            return transactions

        # Last resort: Solana RPC
        logger.debug("Пробуем получить данные через Solana RPC")
        transactions = await self._get_from_rpc(min_value_sol, limit)
        if transactions:
            logger.info(
                "Данные получены через Solana RPC",
                count=len(transactions),
            )
            return transactions

        logger.warning("SOL транзакции временно недоступны")
        return []

    async def _get_from_helius(
        self,
        min_value_sol: float,
        limit: int,
    ) -> list[SolanaTransaction]:
        """
        Получение транзакций через Helius API (Priority 1).

        Helius API предоставляет данные о транзакциях адресов и держателях токенов.
        Бесплатный лимит: 100k запросов/день.

        Args:
            min_value_sol: Минимальная сумма в SOL
            limit: Максимальное количество транзакций

        Returns:
            list[SolanaTransaction]: Список транзакций
        """
        try:
            transactions = []

            # Получаем транзакции для известных кошельков бирж
            for address in list(SOLANA_EXCHANGES.keys())[:5]:
                try:
                    url = f"{HELIUS_API_URL}/addresses/{address}/transactions"
                    params = {"limit": 10}

                    data = await self._make_api_request(url, params=params)
                    if not data or not isinstance(data, list):
                        continue

                    for tx in data:
                        if not isinstance(tx, dict):
                            continue

                        # Парсим данные транзакции
                        native_transfers = tx.get("nativeTransfers", [])
                        if not native_transfers:
                            continue

                        for transfer in native_transfers:
                            amount_sol = transfer.get("amount", 0) / 1_000_000_000
                            if amount_sol < min_value_sol:
                                continue

                            value_usd = amount_sol * self._sol_price
                            from_addr = transfer.get("fromUserAccount", "")
                            to_addr = transfer.get("toUserAccount", "")

                            try:
                                timestamp_val = tx.get("timestamp", 0)
                                timestamp = datetime.fromtimestamp(timestamp_val, tz=timezone.utc) if timestamp_val else None
                            except (ValueError, OSError):
                                timestamp = datetime.now(timezone.utc)

                            tx_obj = SolanaTransaction(
                                tx_hash=tx.get("signature", ""),
                                from_address=from_addr,
                                to_address=to_addr,
                                value_sol=amount_sol,
                                value_usd=value_usd,
                                token_symbol="SOL",
                                timestamp=timestamp,
                                slot=tx.get("slot"),
                            )
                            tx_obj.tx_type = tx_obj.get_transaction_type()
                            transactions.append(tx_obj)

                            if len(transactions) >= limit * 2:
                                break

                    if len(transactions) >= limit * 2:
                        break

                    await asyncio.sleep(0.2)  # Rate limiting

                except Exception as e:
                    logger.debug(f"Ошибка Helius API для адреса {address}: {e}")
                    continue

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.warning(
                "Ошибка Helius API",
                error=str(e),
            )
            return []

    async def _get_from_jupiter(
        self,
        min_value_sol: float,
        limit: int,
    ) -> list[SolanaTransaction]:
        """
        Получение транзакций через Jupiter API (Priority 2).

        Jupiter API предоставляет данные о ценах токенов и свапах.
        Полностью бесплатный.

        Args:
            min_value_sol: Минимальная сумма в SOL
            limit: Максимальное количество транзакций

        Returns:
            list[SolanaTransaction]: Список транзакций
        """
        try:
            transactions = []

            # Jupiter API больше подходит для цен и свапов, а не для whale tracking
            # Используем stats API для получения крупных свапов
            url = f"{JUPITER_STATS_URL}/tokens/top"
            
            data = await self._make_api_request(url)
            if not data or not isinstance(data, dict):
                return []

            # Jupiter API не предоставляет детальные транзакции напрямую
            # Поэтому возвращаем пустой список и полагаемся на другие источники
            logger.debug("Jupiter API не подходит для whale tracking транзакций")
            return []

        except Exception as e:
            logger.warning(
                "Ошибка Jupiter API",
                error=str(e),
            )
            return []

    async def _get_from_solana_tracker(
        self,
        min_value_sol: float,
        limit: int,
    ) -> list[SolanaTransaction]:
        """
        Получение транзакций через SolanaTracker API (Priority 3).

        SolanaTracker предоставляет данные о токенах Raydium, Pumpfun, Orca
        и whale transactions tracking.

        Args:
            min_value_sol: Минимальная сумма в SOL
            limit: Максимальное количество транзакций

        Returns:
            list[SolanaTransaction]: Список транзакций
        """
        try:
            transactions = []

            # SolanaTracker API для whale transactions
            url = f"{SOLANA_TRACKER_API_URL}/whale-transactions"
            params = {
                "limit": limit * 2,
                "min_amount": int(min_value_sol * 1_000_000_000),  # в lamports
            }

            data = await self._make_api_request(url, params=params)
            if not data:
                return []

            # Парсим ответ в зависимости от структуры API
            tx_list = data if isinstance(data, list) else data.get("transactions", [])

            for tx in tx_list:
                if not isinstance(tx, dict):
                    continue

                amount_sol = tx.get("amount", 0) / 1_000_000_000
                if amount_sol < min_value_sol:
                    continue

                value_usd = amount_sol * self._sol_price

                try:
                    timestamp_val = tx.get("timestamp", 0)
                    timestamp = datetime.fromtimestamp(timestamp_val, tz=timezone.utc) if timestamp_val else None
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                tx_obj = SolanaTransaction(
                    tx_hash=tx.get("signature", tx.get("txHash", "")),
                    from_address=tx.get("from", tx.get("fromAddress", "")),
                    to_address=tx.get("to", tx.get("toAddress", "")),
                    value_sol=amount_sol,
                    value_usd=value_usd,
                    token_symbol=tx.get("token", "SOL"),
                    timestamp=timestamp,
                    slot=tx.get("slot"),
                )
                tx_obj.tx_type = tx_obj.get_transaction_type()
                transactions.append(tx_obj)

                if len(transactions) >= limit:
                    break

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.warning(
                "Ошибка SolanaTracker API",
                error=str(e),
            )
            return []

    async def _get_from_solscan(
        self,
        min_value_sol: float,
        limit: int,
    ) -> list[SolanaTransaction]:
        """
        Получение транзакций через Solscan API.

        Args:
            min_value_sol: Минимальная сумма в SOL
            limit: Максимальное количество транзакций

        Returns:
            list[SolanaTransaction]: Список транзакций
        """
        try:
            transactions = []

            # Проверяем крупные транзакции известных кошельков
            # Используем старый API endpoint для получения транзакций адресов
            for address in list(SOLANA_EXCHANGES.keys())[:10]:
                txs = await self._fetch_address_transactions(address, min_value_sol)
                transactions.extend(txs)
                if len(transactions) >= limit * 2:
                    break
                await asyncio.sleep(0.3)  # Rate limiting

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.warning(
                "Ошибка Solscan API",
                error=str(e),
            )
            return []

    async def _fetch_address_transactions(
        self,
        address: str,
        min_value_sol: float,
    ) -> list[SolanaTransaction]:
        """
        Получение транзакций для конкретного адреса.

        Args:
            address: Адрес кошелька
            min_value_sol: Минимальная сумма в SOL

        Returns:
            list[SolanaTransaction]: Список транзакций
        """
        try:
            # Use the public API endpoint for account transactions
            url = f"{SOLSCAN_PUBLIC_API_URL}/account/transactions"
            params = {
                "account": address,
                "limit": 20,
            }

            data = await self._make_api_request(url, params=params)
            if not data:
                return []

            transactions = []

            for tx in data:
                if not isinstance(tx, dict):
                    continue

                # Парсим данные транзакции
                sol_transfer = tx.get("lamport", 0) / 1_000_000_000
                if sol_transfer < min_value_sol:
                    continue

                value_usd = sol_transfer * self._sol_price

                # Определяем адреса
                signer = tx.get("signer", [""])[0] if tx.get("signer") else ""
                # В Solana сложнее определить to_address из-за структуры транзакций
                to_addr = address if signer != address else ""

                try:
                    block_time = tx.get("blockTime", 0)
                    timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc) if block_time else None
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                tx_obj = SolanaTransaction(
                    tx_hash=tx.get("txHash", ""),
                    from_address=signer,
                    to_address=to_addr,
                    value_sol=sol_transfer,
                    value_usd=value_usd,
                    token_symbol="SOL",
                    timestamp=timestamp,
                    slot=tx.get("slot"),
                )
                tx_obj.tx_type = tx_obj.get_transaction_type()
                transactions.append(tx_obj)

            return transactions

        except Exception as e:
            logger.debug(f"Ошибка при получении транзакций адреса {address}: {e}")
            return []

    def _deduplicate_and_sort(
        self,
        transactions: list[SolanaTransaction],
        limit: int,
    ) -> list[SolanaTransaction]:
        """
        Удаление дубликатов и сортировка транзакций.

        Args:
            transactions: Список транзакций
            limit: Максимальное количество

        Returns:
            list[SolanaTransaction]: Отсортированный список уникальных транзакций
        """
        seen_hashes = set()
        unique_transactions = []

        for tx in sorted(
            transactions,
            key=lambda x: x.value_usd,
            reverse=True,
        ):
            if tx.tx_hash not in seen_hashes:
                seen_hashes.add(tx.tx_hash)
                unique_transactions.append(tx)
                if len(unique_transactions) >= limit:
                    break

        return unique_transactions

    async def _get_from_rpc(
        self,
        min_value_sol: float,
        limit: int,
    ) -> list[SolanaTransaction]:
        """
        Резервное получение транзакций через публичные Solana RPC ноды.

        Args:
            min_value_sol: Минимальная сумма в SOL
            limit: Максимальное количество транзакций

        Returns:
            list[SolanaTransaction]: Список транзакций
        """
        for rpc_url in PUBLIC_SOLANA_RPC_URLS:
            try:
                transactions = await self._get_from_single_rpc(
                    rpc_url, min_value_sol, limit
                )
                if transactions:
                    return transactions
            except Exception as e:
                logger.debug(
                    "Solana RPC недоступен",
                    url=rpc_url,
                    error=str(e),
                )
                continue

        logger.debug("Все публичные Solana RPC недоступны")
        return []

    async def _get_from_single_rpc(
        self,
        rpc_url: str,
        min_value_sol: float,
        limit: int,
    ) -> list[SolanaTransaction]:
        """
        Получение транзакций через конкретную RPC ноду.

        Args:
            rpc_url: URL RPC ноды
            min_value_sol: Минимальная сумма в SOL
            limit: Максимальное количество транзакций

        Returns:
            list[SolanaTransaction]: Список транзакций
        """
        session = await self._get_session()
        transactions = []

        # Получаем сигнатуры транзакций для известных адресов бирж
        for address in list(SOLANA_EXCHANGES.keys())[:5]:
            try:
                request_data = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSignaturesForAddress",
                    "params": [
                        address,
                        {"limit": 10}
                    ]
                }

                timeout = aiohttp.ClientTimeout(total=15)
                async with session.post(
                    rpc_url, json=request_data, timeout=timeout
                ) as response:
                    if response.status != 200:
                        continue

                    data = await response.json()
                    if "result" not in data:
                        continue

                    for sig_info in data["result"]:
                        # Получаем детали транзакции
                        tx_request = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getTransaction",
                            "params": [
                                sig_info.get("signature", ""),
                                {"encoding": "json", "maxSupportedTransactionVersion": 0}
                            ]
                        }

                        async with session.post(
                            rpc_url, json=tx_request, timeout=timeout
                        ) as tx_response:
                            if tx_response.status != 200:
                                continue

                            tx_data = await tx_response.json()
                            if "result" not in tx_data or not tx_data["result"]:
                                continue

                            tx = tx_data["result"]
                            meta = tx.get("meta", {})
                            if not meta:
                                continue

                            # Вычисляем изменение баланса
                            pre_balances = meta.get("preBalances", [])
                            post_balances = meta.get("postBalances", [])

                            if pre_balances and post_balances:
                                # Находим максимальное изменение
                                max_change = 0
                                for i in range(min(len(pre_balances), len(post_balances))):
                                    change = abs(post_balances[i] - pre_balances[i])
                                    if change > max_change:
                                        max_change = change

                                value_sol = max_change / 1_000_000_000
                                if value_sol < min_value_sol:
                                    continue

                                value_usd = value_sol * self._sol_price
                                block_time = tx.get("blockTime", 0)

                                try:
                                    timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc) if block_time else None
                                except (ValueError, OSError):
                                    timestamp = datetime.now(timezone.utc)

                                tx_obj = SolanaTransaction(
                                    tx_hash=sig_info.get("signature", ""),
                                    from_address=address,
                                    to_address="",
                                    value_sol=value_sol,
                                    value_usd=value_usd,
                                    token_symbol="SOL",
                                    timestamp=timestamp,
                                    slot=sig_info.get("slot"),
                                )
                                tx_obj.tx_type = tx_obj.get_transaction_type()
                                transactions.append(tx_obj)

                                if len(transactions) >= limit:
                                    return self._deduplicate_and_sort(transactions, limit)

                # Rate limiting
                await asyncio.sleep(0.2)

            except Exception as e:
                logger.debug(f"Ошибка RPC для адреса {address}: {e}")
                continue

        return self._deduplicate_and_sort(transactions, limit)

    async def get_spl_token_transactions(
        self,
        token_address: str,
        limit: int = 20,
    ) -> list[SolanaTransaction]:
        """
        Получение крупных SPL токен транзакций.

        Args:
            token_address: Адрес токена
            limit: Максимальное количество транзакций

        Returns:
            list[SolanaTransaction]: Список транзакций
        """
        try:
            url = f"{SOLSCAN_PUBLIC_API_URL}/token/transfer"
            params = {
                "token": token_address,
                "limit": limit * 2,
            }

            data = await self._make_api_request(url, params=params)
            if not data:
                return []

            transactions = []
            min_value_usd = self.min_value_usd

            for tx in data.get("data", []):
                if not isinstance(tx, dict):
                    continue

                # Получаем стоимость в USD
                amount = float(tx.get("amount", 0))
                decimals = int(tx.get("decimals", 9))
                value = amount / (10 ** decimals)

                # Для стейблкоинов цена = 1 USD
                token_symbol = tx.get("symbol", "TOKEN")
                if token_symbol.upper() in ("USDC", "USDT"):
                    value_usd = value
                else:
                    value_usd = value * 1.0  # Нужен API для точной цены

                if value_usd < min_value_usd:
                    continue

                try:
                    block_time = tx.get("blockTime", 0)
                    timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc) if block_time else None
                except (ValueError, OSError):
                    timestamp = datetime.now(timezone.utc)

                tx_obj = SolanaTransaction(
                    tx_hash=tx.get("signature", ""),
                    from_address=tx.get("source", ""),
                    to_address=tx.get("destination", ""),
                    value_sol=value,
                    value_usd=value_usd,
                    token_symbol=token_symbol,
                    timestamp=timestamp,
                )
                tx_obj.tx_type = tx_obj.get_transaction_type()
                transactions.append(tx_obj)

            return self._deduplicate_and_sort(transactions, limit)

        except Exception as e:
            logger.error(
                "Ошибка при получении SPL транзакций",
                error=str(e),
            )
            return []
