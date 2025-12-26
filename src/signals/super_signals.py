"""
Super Signals - объединённая система прогнозирования.
Сканирует 3000+ монет, анализирует ТОП-30, выдаёт ТОП-5 с вероятностью.

Объединяет:
- Rocket Hunter: скринер волатильных монет (движение >±15%)
- AI Signals: умные сигналы с ATR, BB, Funding
"""

import logging
import time
import asyncio
import aiohttp
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime

from signals.exchanges.okx import OKXClient
from signals.exchanges.bybit import BybitClient
from signals.exchanges.gate import GateClient
from config import settings

logger = logging.getLogger(__name__)


class SuperSignals:
    """
    Объединённая система прогнозирования.
    Сканирует 3000+ монет, анализирует ТОП-30, выдаёт ТОП-5 с вероятностью.
    """

    # Настройки
    MIN_PROBABILITY = 45  # Минимальная вероятность для вывода (снижено с 50 для учета сильного движения)
    TOP_CANDIDATES = 30   # Сколько анализировать глубоко
    TOP_SIGNALS = 5       # Сколько выводить

    # Фильтры
    MIN_CHANGE_24H = 15   # Минимальное движение %
    MIN_VOLUME = 500000   # Минимальный объём $
    MAX_MCAP = 1000000000 # Максимальная капа $1B
    
    # Уровни и риск-менеджмент
    ATR_MULTIPLIER = 1.5  # Множитель ATR для расчёта стоп-лосса
    MAX_STOP_LOSS_PERCENT = 0.10  # Максимальный стоп-лосс (10%)
    DEFAULT_ATR_PERCENT = 0.03  # Fallback ATR (3% от цены)

    # Исключенные символы
    EXCLUDED_SYMBOLS = {
        # Стейблкоины
        "USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "PYUSD", "USDD",
        # Wrapped токены
        "WETH", "WBTC", "WBNB", "WSTETH", "WBETH",
        # Биржевые токены
        "BGB", "WBT", "GT", "MX", "KCS", "HT", "OKB", "BNB", "LEO", "CRO",
    }

    # Конфигурация бирж
    EXCHANGE_CONFIG = {
        "binance": "Binance",
        "bybit": "Bybit",
        "mexc": "MEXC",
        "gateio": "Gate.io",
        "kucoin": "KuCoin",
    }

    def __init__(self):
        # Биржи для фьючерсных данных
        self.exchanges = {
            "okx": OKXClient(),
            "bybit": BybitClient(),
            "gate": GateClient(),
        }
        self.session: Optional[aiohttp.ClientSession] = None

        # Кэш пар с бирж
        self.exchange_pairs: Dict[str, Set[str]] = {
            exchange_key: set() for exchange_key in self.EXCHANGE_CONFIG.keys()
        }
        self.pairs_loaded = False

    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close all connections."""
        for exchange in self.exchanges.values():
            await exchange.close()
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_futures_symbols(self) -> Set[str]:
        """Получает список всех фьючерсных пар с Binance Futures."""
        await self._ensure_session()
        
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        futures_symbols = set()
        
        try:
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for symbol_info in data.get("symbols", []):
                        if symbol_info.get("status") == "TRADING":
                            # Убираем USDT из конца чтобы получить базовый символ
                            symbol = symbol_info.get("symbol", "")
                            if symbol.endswith("USDT"):
                                base = symbol[:-4]  # BTC, ETH, BIFI и т.д.
                                futures_symbols.add(base)
                    
                    logger.info(f"Binance Futures: loaded {len(futures_symbols)} symbols")
        except Exception as e:
            logger.warning(f"Failed to fetch Binance Futures symbols: {e}")
        
        return futures_symbols

    async def fetch_binance_funding(self, symbol: str) -> Optional[float]:
        """Получает funding rate с Binance Futures."""
        await self._ensure_session()
        
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        params = {"symbol": f"{symbol}USDT"}
        
        try:
            async with self.session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    funding = float(data.get("lastFundingRate", 0)) * 100
                    return funding
        except Exception as e:
            logger.debug(f"Failed to fetch funding rate for {symbol}: {e}")
        
        return None

    def _is_valid_symbol(self, symbol: str) -> bool:
        """Проверяет валидность символа."""
        if not symbol or not symbol.isascii():
            return False
        if "." in symbol or "_" in symbol or "-" in symbol:
            return False
        if len(symbol) > 10:
            return False
        if symbol.upper() in self.EXCLUDED_SYMBOLS:
            return False
        return True

    async def load_exchange_pairs(self):
        """Загружает списки торгуемых пар со всех бирж."""
        if self.pairs_loaded:
            return

        await asyncio.gather(
            self._load_binance_pairs(),
            self._load_bybit_pairs(),
            self._load_mexc_pairs(),
            self._load_gateio_pairs(),
            self._load_kucoin_pairs(),
            return_exceptions=True,
        )

        self.pairs_loaded = True
        logger.info(
            f"Exchange pairs loaded: Binance={len(self.exchange_pairs['binance'])}, "
            f"Bybit={len(self.exchange_pairs['bybit'])}, "
            f"MEXC={len(self.exchange_pairs['mexc'])}, "
            f"Gate.io={len(self.exchange_pairs['gateio'])}, "
            f"KuCoin={len(self.exchange_pairs['kucoin'])}"
        )

    async def _load_binance_pairs(self):
        """Binance - список всех USDT пар."""
        await self._ensure_session()
        url = "https://api.binance.com/api/v3/exchangeInfo"
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for symbol in data.get("symbols", []):
                        if (
                            symbol.get("quoteAsset") == "USDT"
                            and symbol.get("status") == "TRADING"
                        ):
                            base = symbol.get("baseAsset", "").upper()
                            self.exchange_pairs["binance"].add(base)
        except Exception as e:
            logger.warning(f"Failed to load Binance pairs: {e}")

    async def _load_bybit_pairs(self):
        """Bybit - список всех spot пар."""
        await self._ensure_session()
        url = "https://api.bybit.com/v5/market/tickers?category=spot"
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data.get("result", {}).get("list", []):
                        symbol = item.get("symbol", "")
                        if symbol.endswith("USDT"):
                            base = symbol.replace("USDT", "").upper()
                            self.exchange_pairs["bybit"].add(base)
        except Exception as e:
            logger.warning(f"Failed to load Bybit pairs: {e}")

    async def _load_mexc_pairs(self):
        """MEXC - список всех пар."""
        await self._ensure_session()
        url = "https://api.mexc.com/api/v3/ticker/24hr"
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for ticker in data:
                        symbol = ticker.get("symbol", "")
                        if symbol.endswith("USDT"):
                            base = symbol.replace("USDT", "").upper()
                            self.exchange_pairs["mexc"].add(base)
        except Exception as e:
            logger.warning(f"Failed to load MEXC pairs: {e}")

    async def _load_gateio_pairs(self):
        """Gate.io - список всех пар."""
        await self._ensure_session()
        url = "https://api.gateio.ws/api/v4/spot/tickers"
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for ticker in data:
                        pair = ticker.get("currency_pair", "")
                        if pair.endswith("_USDT"):
                            base = pair.replace("_USDT", "").upper()
                            self.exchange_pairs["gateio"].add(base)
        except Exception as e:
            logger.warning(f"Failed to load Gate.io pairs: {e}")

    async def _load_kucoin_pairs(self):
        """KuCoin - список всех пар."""
        await self._ensure_session()
        url = "https://api.kucoin.com/api/v1/market/allTickers"
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for ticker in data.get("data", {}).get("ticker", []):
                        symbol = ticker.get("symbol", "")
                        if symbol.endswith("-USDT"):
                            base = symbol.replace("-USDT", "").upper()
                            self.exchange_pairs["kucoin"].add(base)
        except Exception as e:
            logger.warning(f"Failed to load KuCoin pairs: {e}")

    def get_available_exchanges(self, symbol: str) -> List[str]:
        """Возвращает список бирж где торгуется монета."""
        symbol = symbol.upper()
        available = []

        for exchange_key, display_name in self.EXCHANGE_CONFIG.items():
            if symbol in self.exchange_pairs[exchange_key]:
                available.append(display_name)

        return available

    async def fetch_binance_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
        """
        Получает свечи с Binance Spot API.
        Это основной источник свечей — там есть почти все монеты.
        """
        await self._ensure_session()
        
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": f"{symbol}USDT",
            "interval": interval,
            "limit": limit
        }
        
        try:
            async with self.session.get(
                url, 
                params=params, 
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candles = []
                    for k in data:
                        candles.append({
                            "timestamp": k[0],
                            "open": float(k[1]),
                            "high": float(k[2]),
                            "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5])
                        })
                    return candles
        except Exception as e:
            logger.debug(f"Binance klines failed for {symbol}: {e}")
        
        return []

    async def fetch_bybit_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
        """
        Получает свечи с Bybit Spot API (fallback).
        """
        await self._ensure_session()
        
        # Конвертация интервала
        interval_map = {"1h": "60", "4h": "240", "1d": "D"}
        bybit_interval = interval_map.get(interval, "60")
        
        url = "https://api.bybit.com/v5/market/kline"
        params = {
            "category": "spot",
            "symbol": f"{symbol}USDT",
            "interval": bybit_interval,
            "limit": limit
        }
        
        try:
            async with self.session.get(
                url, 
                params=params, 
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    klines = data.get("result", {}).get("list", [])
                    candles = []
                    for k in reversed(klines):  # Bybit возвращает в обратном порядке
                        candles.append({
                            "timestamp": int(k[0]),
                            "open": float(k[1]),
                            "high": float(k[2]),
                            "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5])
                        })
                    return candles
        except Exception as e:
            logger.debug(f"Bybit klines failed for {symbol}: {e}")
        
        return []

    async def fetch_mexc_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
        """
        Получает свечи с MEXC API (fallback).
        """
        await self._ensure_session()
        
        # Конвертация интервала
        interval_map = {"1h": "1h", "4h": "4h", "1d": "1d"}
        mexc_interval = interval_map.get(interval, "1h")
        
        url = "https://api.mexc.com/api/v3/klines"
        params = {
            "symbol": f"{symbol}USDT",
            "interval": mexc_interval,
            "limit": limit
        }
        
        try:
            async with self.session.get(
                url, 
                params=params, 
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candles = []
                    for k in data:
                        candles.append({
                            "timestamp": k[0],
                            "open": float(k[1]),
                            "high": float(k[2]),
                            "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5])
                        })
                    return candles
        except Exception as e:
            logger.debug(f"MEXC klines failed for {symbol}: {e}")
        
        return []

    async def fetch_gateio_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
        """
        Получает свечи с Gate.io API (fallback).
        """
        await self._ensure_session()
        
        # Конвертация интервала
        interval_map = {"1h": "1h", "4h": "4h", "1d": "1d"}
        gate_interval = interval_map.get(interval, "1h")
        
        url = "https://api.gateio.ws/api/v4/spot/candlesticks"
        params = {
            "currency_pair": f"{symbol}_USDT",
            "interval": gate_interval,
            "limit": limit
        }
        
        try:
            async with self.session.get(
                url, 
                params=params, 
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candles = []
                    for k in data:
                        candles.append({
                            "timestamp": int(k[0]) * 1000,  # Gate.io возвращает секунды
                            "open": float(k[5]),
                            "high": float(k[3]),
                            "low": float(k[4]),
                            "close": float(k[2]),
                            "volume": float(k[1])
                        })
                    return candles
        except Exception as e:
            logger.debug(f"Gate.io klines failed for {symbol}: {e}")
        
        return []

    async def fetch_klines_with_fallback(self, symbol: str, interval: str = "1h", limit: int = 100) -> Tuple[List[Dict], str]:
        """
        Получает свечи с fallback chain: Binance → Bybit → MEXC → Gate.io
        
        Returns:
            Tuple[List[Dict], str]: (свечи, название биржи)
        """
        # 1. Пробуем Binance (основной)
        candles = await self.fetch_binance_klines(symbol, interval, limit)
        if candles and len(candles) >= 20:
            logger.debug(f"{symbol}: got {len(candles)} candles from Binance")
            return candles, "binance"
        
        # 2. Пробуем Bybit
        candles = await self.fetch_bybit_klines(symbol, interval, limit)
        if candles and len(candles) >= 20:
            logger.debug(f"{symbol}: got {len(candles)} candles from Bybit")
            return candles, "bybit"
        
        # 3. Пробуем MEXC
        candles = await self.fetch_mexc_klines(symbol, interval, limit)
        if candles and len(candles) >= 20:
            logger.debug(f"{symbol}: got {len(candles)} candles from MEXC")
            return candles, "mexc"
        
        # 4. Пробуем Gate.io
        candles = await self.fetch_gateio_klines(symbol, interval, limit)
        if candles and len(candles) >= 20:
            logger.debug(f"{symbol}: got {len(candles)} candles from Gate.io")
            return candles, "gateio"
        
        logger.warning(f"{symbol}: ALL kline sources failed!")
        return [], ""

    async def fetch_binance_coins(self) -> List[Dict]:
        """Получает все торговые пары с Binance (~600 монет)."""
        await self._ensure_session()
        url = "https://api.binance.com/api/v3/ticker/24hr"

        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    coins = []
                    for ticker in data:
                        symbol = ticker.get("symbol", "")
                        if not symbol.endswith("USDT"):
                            continue

                        base_symbol = symbol.replace("USDT", "")
                        price_change_24h = float(ticker.get("priceChangePercent", 0))
                        current_price = float(ticker.get("lastPrice", 0))
                        volume_24h = float(ticker.get("quoteVolume", 0))

                        coins.append({
                            "symbol": base_symbol,
                            "name": base_symbol,
                            "current_price": current_price,
                            "price_change_percentage_24h": price_change_24h,
                            "price_change_percentage_1h_in_currency": 0,
                            "total_volume": volume_24h,
                            "market_cap": 0,
                            "source": "binance",
                        })

                    logger.info(f"Binance: fetched {len(coins)} coins")
                    return coins
        except Exception as e:
            logger.error(f"Error fetching Binance data: {e}")

        return []

    async def fetch_coinlore_coins(self) -> List[Dict]:
        """Получает монеты с CoinLore (2000 монет)."""
        await self._ensure_session()
        all_coins = []

        for start in range(0, 2000, 100):
            url = f"https://api.coinlore.net/api/tickers/?start={start}&limit=100"

            try:
                async with self.session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tickers = data.get("data", [])

                        if not tickers:
                            break

                        for ticker in tickers:
                            percent_change_24h = float(
                                ticker.get("percent_change_24h", 0) or 0
                            )
                            percent_change_1h = float(
                                ticker.get("percent_change_1h", 0) or 0
                            )

                            all_coins.append({
                                "symbol": ticker.get("symbol", "").upper(),
                                "name": ticker.get("name", ""),
                                "current_price": float(ticker.get("price_usd", 0) or 0),
                                "price_change_percentage_24h": percent_change_24h,
                                "price_change_percentage_1h_in_currency": percent_change_1h,
                                "total_volume": float(ticker.get("volume24", 0) or 0),
                                "market_cap": float(ticker.get("market_cap_usd", 0) or 0),
                                "source": "coinlore",
                            })
                    else:
                        break
            except Exception as e:
                logger.warning(f"CoinLore error at start={start}: {e}")
                break

            await asyncio.sleep(0.5)

        logger.info(f"CoinLore: fetched {len(all_coins)} coins")
        return all_coins

    async def fetch_coinpaprika_coins(self) -> List[Dict]:
        """Получает все монеты с CoinPaprika (2500+ монет)."""
        await self._ensure_session()
        url = "https://api.coinpaprika.com/v1/tickers"

        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    coins = []
                    for ticker in data:
                        quotes = ticker.get("quotes", {}).get("USD", {})

                        percent_change_24h = float(
                            quotes.get("percent_change_24h", 0) or 0
                        )
                        percent_change_1h = float(
                            quotes.get("percent_change_1h", 0) or 0
                        )

                        coins.append({
                            "symbol": ticker.get("symbol", "").upper(),
                            "name": ticker.get("name", ""),
                            "current_price": float(quotes.get("price", 0) or 0),
                            "price_change_percentage_24h": percent_change_24h,
                            "price_change_percentage_1h_in_currency": percent_change_1h,
                            "total_volume": float(quotes.get("volume_24h", 0) or 0),
                            "market_cap": float(quotes.get("market_cap", 0) or 0),
                            "source": "coinpaprika",
                        })

                    logger.info(f"CoinPaprika: fetched {len(coins)} coins")
                    return coins
        except Exception as e:
            logger.warning(f"CoinPaprika error: {e}")

        return []

    async def fetch_coingecko_coins(self) -> List[Dict]:
        """Получает 1 страницу с CoinGecko (250 монет)."""
        await self._ensure_session()
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h",
        }

        headers = {}
        api_key = getattr(settings, "coingecko_api_key", None)
        if api_key and len(api_key) > 5:
            headers["x-cg-demo-api-key"] = api_key

        try:
            async with self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    coins = []
                    for coin in data:
                        coins.append({
                            "symbol": coin.get("symbol", "").upper(),
                            "name": coin.get("name", ""),
                            "current_price": float(coin.get("current_price", 0) or 0),
                            "price_change_percentage_24h": float(
                                coin.get("price_change_percentage_24h", 0) or 0
                            ),
                            "price_change_percentage_1h_in_currency": float(
                                coin.get("price_change_percentage_1h_in_currency", 0) or 0
                            ),
                            "total_volume": float(coin.get("total_volume", 0) or 0),
                            "market_cap": float(coin.get("market_cap", 0) or 0),
                            "source": "coingecko",
                        })

                    logger.info(f"CoinGecko: fetched {len(coins)} coins")
                    return coins
        except Exception as e:
            logger.error(f"Error fetching CoinGecko data: {e}")

        return []

    async def fetch_all_coins(self) -> List[Dict]:
        """
        Сканирует монеты из всех источников и объединяет.
        Binance + CoinLore + CoinPaprika + CoinGecko

        Returns:
            Список монет с базовой информацией
        """
        # Загружаем списки пар с бирж
        await self.load_exchange_pairs()

        logger.info(
            "SuperSignals: Stage 1 - Screening from 4 sources "
            "(Binance + CoinLore + CoinPaprika + CoinGecko)"
        )

        # Параллельно загружаем из всех источников
        results = await asyncio.gather(
            self.fetch_binance_coins(),
            self.fetch_coinlore_coins(),
            self.fetch_coinpaprika_coins(),
            self.fetch_coingecko_coins(),
            return_exceptions=True,
        )

        binance_coins = results[0] if not isinstance(results[0], Exception) else []
        coinlore_coins = results[1] if not isinstance(results[1], Exception) else []
        coinpaprika_coins = results[2] if not isinstance(results[2], Exception) else []
        coingecko_coins = results[3] if not isinstance(results[3], Exception) else []

        # Объединяем и убираем дубликаты
        # Приоритет: Binance > CoinGecko > CoinPaprika > CoinLore
        seen_symbols = set()
        all_coins = []

        for coin in binance_coins:
            symbol = coin["symbol"]
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                all_coins.append(coin)

        for coin in coingecko_coins:
            symbol = coin["symbol"]
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                all_coins.append(coin)

        for coin in coinpaprika_coins:
            symbol = coin["symbol"]
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                all_coins.append(coin)

        for coin in coinlore_coins:
            symbol = coin["symbol"]
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                all_coins.append(coin)

        logger.info(
            f"SuperSignals: total {len(all_coins)} unique coins "
            f"(Binance: {len(binance_coins)}, CoinLore: {len(coinlore_coins)}, "
            f"CoinPaprika: {len(coinpaprika_coins)}, CoinGecko: {len(coingecko_coins)})"
        )

        return all_coins

    def apply_filters(self, coins: List[Dict]) -> List[Dict]:
        """
        Фильтрует монеты по базовым критериям.

        Args:
            coins: Список монет

        Returns:
            Список монет прошедших фильтры
        """
        filtered = []

        for coin in coins:
            symbol = coin.get("symbol", "").upper()

            # Проверка валидности символа
            if not self._is_valid_symbol(symbol):
                continue

            # Минимальный объём
            volume_24h = coin.get("total_volume", 0)
            if volume_24h < self.MIN_VOLUME:
                continue

            # Пропускаем монеты без изменения цены
            price_change_24h = coin.get("price_change_percentage_24h")
            if price_change_24h is None:
                continue

            # Минимальное движение (>±15%)
            if abs(price_change_24h) < self.MIN_CHANGE_24H:
                continue

            # Максимальная капа (<$1B)
            market_cap = coin.get("market_cap", 0)
            if market_cap > self.MAX_MCAP:
                continue

            filtered.append(coin)

        logger.info(f"SuperSignals: {len(filtered)} coins passed filters")
        return filtered

    async def deep_analyze(self, coin: Dict) -> Optional[Dict]:
        """
        Глубокий анализ монеты с расчётом вероятности.

        Args:
            coin: Данные монеты

        Returns:
            Dict с полной информацией или None
        """
        symbol = coin.get("symbol", "").upper()

        try:
            current_price = float(coin.get("current_price", 0))
            if current_price <= 0:
                return None

            price_change_1h = coin.get("price_change_percentage_1h_in_currency", 0) or 0
            price_change_24h = coin.get("price_change_percentage_24h", 0) or 0
            volume_24h = coin.get("total_volume", 0) or 0
            market_cap = coin.get("market_cap", 0) or 0

            # === Загрузка свечей с fallback ===
            candles_1h, exchange_1h = await self.fetch_klines_with_fallback(symbol, "1h", 100)
            candles_4h, exchange_4h = await self.fetch_klines_with_fallback(symbol, "4h", 50)
            
            # Проверяем что получили достаточно данных
            if not candles_1h or len(candles_1h) < 20:
                logger.debug(f"Not enough 1h candles for {symbol}")
                return None
                
            if not candles_4h or len(candles_4h) < 20:
                logger.debug(f"Not enough 4h candles for {symbol}")
                return None
            
            exchange_name = exchange_1h or exchange_4h
            
            # Funding rate - пробуем получить с Binance Futures
            funding_rate = await self.fetch_binance_funding(symbol)

            # === Расчёт индикаторов СНАЧАЛА (нужен RSI для определения направления) ===
            analysis = self._calculate_indicators(candles_1h, candles_4h, current_price)
            
            # === Определение направления на основе RSI и движения ===
            # Логика: ищем РАЗВОРОТ, а не продолжение тренда
            rsi = analysis["rsi"]
            
            # Приоритет 1: Сильное движение + подтверждение RSI (более мягкие пороги 40/60)
            # После падения + перепродан = ЛОНГ (ожидаем отскок)
            if price_change_24h < -15 and rsi < 40:
                direction = "long"
            # После роста + перекуплен = ШОРТ (ожидаем откат)
            elif price_change_24h > 15 and rsi > 60:
                direction = "short"
            
            # Приоритет 2: Экстремальный RSI (стандартные пороги 30/70)
            elif rsi < 30:
                direction = "long"  # Сильно перепродан
            elif rsi > 70:
                direction = "short"  # Сильно перекуплен
            
            # Приоритет 3: Нейтральный RSI - смотрим на экстремальное движение
            else:
                if price_change_24h > 30:
                    direction = "short"  # Сильный рост - ждём откат
                elif price_change_24h < -30:
                    direction = "long"  # Сильное падение - ждём отскок
                else:
                    direction = "long" if price_change_24h < 0 else "short"
            
            logger.debug(f"{symbol}: direction={direction.upper()} (RSI={rsi:.1f}, change_24h={price_change_24h:+.1f}%)")
            
            analysis["symbol"] = symbol
            analysis["name"] = coin.get("name", symbol)
            analysis["direction"] = direction
            analysis["current_price"] = current_price
            analysis["change_1h"] = price_change_1h
            analysis["change_24h"] = price_change_24h
            analysis["volume_24h"] = volume_24h
            analysis["market_cap"] = market_cap
            analysis["exchange"] = exchange_name
            analysis["funding_rate"] = funding_rate
            analysis["source"] = coin.get("source", "unknown")

            # Логируем результат анализа индикаторов
            logger.debug(
                f"{symbol}: RSI={analysis['rsi']:.1f}, "
                f"MACD={analysis['macd']['histogram']:.6f}, "
                f"Volume={analysis['volume_ratio']:.2f}x"
            )

            # Определяем накопление (accumulation)
            accumulation = self.detect_accumulation(candles_1h, analysis['volume_ratio'], price_change_1h)
            analysis["accumulation"] = accumulation
            
            if accumulation["detected"]:
                logger.debug(f"{symbol}: Accumulation detected - {accumulation['strength']}")

            # Расчёт вероятности
            probability = self.calculate_probability(analysis)
            if probability < self.MIN_PROBABILITY:
                logger.info(f"{symbol}: probability {probability}% < {self.MIN_PROBABILITY}% - skipped (RSI={analysis['rsi']:.1f})")
                return None

            analysis["probability"] = probability

            # Расчёт уровней входа/стопа/TP
            levels = self.calculate_real_levels(analysis)
            analysis["levels"] = levels

            # Получаем список бирж
            analysis["exchanges"] = self.get_available_exchanges(symbol)

            logger.info(f"{symbol}: probability {probability}% - ACCEPTED")
            return analysis

        except Exception as e:
            logger.debug(f"Error analyzing {symbol}: {e}")
            return None

    def _calculate_indicators(self, candles_1h: List[Dict], candles_4h: List[Dict], current_price: float) -> Dict:
        """Рассчитывает все индикаторы для анализа."""
        # Закрытия для индикаторов
        closes_1h = [float(c.get("close", 0)) for c in candles_1h]
        closes_4h = [float(c.get("close", 0)) for c in candles_4h]

        # RSI 1h и 4h
        rsi = self._calculate_rsi(closes_1h, period=14)
        rsi_4h = self._calculate_rsi(closes_4h, period=14) if candles_4h else None

        # MACD
        macd = self._calculate_macd(closes_1h)

        # Bollinger Bands
        bb_position = self._calculate_bb_position(closes_1h, current_price)

        # ATR (для стопа)
        highs = [float(c.get("high", 0)) for c in candles_1h]
        lows = [float(c.get("low", 0)) for c in candles_1h]
        atr = self._calculate_atr(highs, lows, closes_1h, period=14)

        # Volume ratio
        volumes = [float(c.get("volume", 0)) for c in candles_1h]
        volume_ratio = self._calculate_volume_ratio(volumes)

        # Поддержка/сопротивление
        support, resistance = self._find_support_resistance(closes_4h, current_price)

        # Расстояние до поддержки/сопротивления
        price_to_support = abs(current_price - support) / current_price * 100 if support else 100
        price_to_resistance = abs(resistance - current_price) / current_price * 100 if resistance else 100

        # EMA 20/50
        ema_20 = self._calculate_ema(candles_1h, 20)
        ema_50 = self._calculate_ema(candles_1h, 50)
        ema_trend = "bullish" if ema_20 > ema_50 else "bearish"
        price_vs_ema = "above" if current_price > ema_20 else "below"

        # Stochastic RSI
        stoch_rsi = self._calculate_stoch_rsi(candles_1h)

        return {
            "rsi": rsi,
            "rsi_4h": rsi_4h,
            "macd": macd,
            "bb_position": bb_position,
            "atr": atr,
            "volume_ratio": volume_ratio,
            "support": support,
            "resistance": resistance,
            "price_to_support": price_to_support,
            "price_to_resistance": price_to_resistance,
            "ema_20": ema_20,
            "ema_50": ema_50,
            "ema_trend": ema_trend,
            "price_vs_ema": price_vs_ema,
            "stoch_rsi": stoch_rsi,
        }

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Рассчитывает RSI."""
        if len(prices) < period + 1:
            return 50.0

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period if gains else 0
        avg_loss = sum(losses[-period:]) / period if losses else 0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(self, prices: List[float]) -> Dict:
        """Рассчитывает MACD."""
        if len(prices) < 26:
            return {"crossover": None, "histogram": 0, "prev_histogram": 0}

        # EMA
        ema_12 = self._ema(prices, 12)
        ema_26 = self._ema(prices, 26)

        macd_line = ema_12 - ema_26

        # Signal line (EMA of MACD)
        # Упрощённо - берём последние значения
        signal_line = macd_line * 0.9  # Приблизительно

        histogram = macd_line - signal_line

        # Предыдущий histogram (упрощённо)
        prev_histogram = histogram * 0.95

        # Определяем crossover
        crossover = None
        if histogram > 0 and prev_histogram <= 0:
            crossover = "bullish"
        elif histogram < 0 and prev_histogram >= 0:
            crossover = "bearish"

        return {
            "crossover": crossover,
            "histogram": histogram,
            "prev_histogram": prev_histogram,
        }

    def _ema(self, prices: List[float], period: int) -> float:
        """Рассчитывает EMA."""
        if not prices:
            return 0

        multiplier = 2 / (period + 1)
        ema = prices[0]

        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def _calculate_bb_position(self, prices: List[float], current_price: float) -> float:
        """Рассчитывает позицию цены в Bollinger Bands (0-1)."""
        if len(prices) < 20:
            return 0.5

        sma = sum(prices[-20:]) / 20
        variance = sum((x - sma) ** 2 for x in prices[-20:]) / 20
        std = variance ** 0.5

        upper = sma + 2 * std
        lower = sma - 2 * std

        if upper == lower:
            return 0.5

        position = (current_price - lower) / (upper - lower)
        return max(0, min(1, position))

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Рассчитывает ATR."""
        if len(closes) < period + 1:
            return 0

        true_ranges = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)

        atr = sum(true_ranges[-period:]) / period if true_ranges else 0
        return atr

    def _calculate_volume_ratio(self, volumes: List[float]) -> float:
        """Рассчитывает отношение текущего объёма к среднему."""
        if len(volumes) < 2:
            return 1.0

        current_volume = volumes[-1]
        avg_volume = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 1

        if avg_volume == 0:
            return 1.0

        return current_volume / avg_volume

    def _find_support_resistance(self, prices: List[float], current_price: float) -> Tuple[float, float]:
        """Находит уровни поддержки и сопротивления."""
        if len(prices) < 10:
            return current_price * 0.97, current_price * 1.03

        # Поддержка - минимум за период
        support = min(prices[-20:])

        # Сопротивление - максимум за период
        resistance = max(prices[-20:])

        # Если текущая цена вне диапазона - корректируем
        if current_price < support:
            support = current_price * 0.97
        if current_price > resistance:
            resistance = current_price * 1.03

        return support, resistance

    def detect_accumulation(self, candles_1h: List[Dict], volume_ratio: float, price_change_1h: float) -> Dict:
        """
        Определяет паттерн накопления (accumulation).
        
        Накопление = высокий объём при минимальном изменении цены
        Это значит что крупный игрок скупает/продаёт, не двигая цену
        
        Args:
            candles_1h: Свечи 1h для дополнительного анализа
            volume_ratio: Отношение текущего объёма к среднему
            price_change_1h: Изменение цены за 1h в %
        
        Returns:
            {
                "detected": True/False,
                "strength": "strong" / "moderate" / "weak" / None,
                "signal": "🟢 Сильное накопление" / "🟡 Накопление" / None,
                "volume_increase": 300,  # %
                "price_change": 2,  # %
            }
        """
        result = {
            "detected": False,
            "strength": None,
            "signal": None,
            "volume_increase": volume_ratio * 100 if volume_ratio else 0,
            "price_change": abs(price_change_1h) if price_change_1h else 0
        }
        
        if volume_ratio is None or price_change_1h is None:
            return result
        
        volume_pct = volume_ratio * 100  # Конвертируем в проценты (x2.5 = 250%)
        price_pct = abs(price_change_1h)  # Абсолютное изменение цены
        
        # Сильное накопление: объём > 300%, цена < 5%
        if volume_pct > 300 and price_pct < 5:
            result["detected"] = True
            result["strength"] = "strong"
            result["signal"] = "🟢 Сильное накопление"
        
        # Умеренное накопление: объём > 200%, цена < 10%
        elif volume_pct > 200 and price_pct < 10:
            result["detected"] = True
            result["strength"] = "moderate"
            result["signal"] = "🟢 Накопление"
        
        # Слабое накопление: объём > 150%, цена < 15%
        elif volume_pct > 150 and price_pct < 15:
            result["detected"] = True
            result["strength"] = "weak"
            result["signal"] = "🟡 Слабое накопление"
        
        return result

    def _calculate_ema(self, candles: List[Dict], period: int) -> float:
        """Рассчитывает EMA."""
        if len(candles) < period:
            return 0
        
        closes = [float(c["close"]) for c in candles]
        multiplier = 2 / (period + 1)
        ema = closes[0]
        
        for close in closes[1:]:
            ema = (close - ema) * multiplier + ema
        
        return ema

    def _calculate_stoch_rsi(self, candles: List[Dict], period: int = 14) -> Dict:
        """Рассчитывает Stochastic RSI."""
        if len(candles) < period * 2:
            return {"k": 50, "d": 50}
        
        # Сначала считаем RSI
        closes = [float(c["close"]) for c in candles]
        rsi_values = []
        
        for i in range(period, len(closes)):
            window = closes[i-period:i]
            gains = []
            losses = []
            for j in range(1, len(window)):
                change = window[j] - window[j-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains) / period if gains else 0
            avg_loss = sum(losses) / period if losses else 0
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)
        
        if len(rsi_values) < period:
            return {"k": 50, "d": 50}
        
        # Stochastic на RSI
        recent_rsi = rsi_values[-period:]
        min_rsi = min(recent_rsi)
        max_rsi = max(recent_rsi)
        
        if max_rsi == min_rsi:
            k = 50
        else:
            k = ((rsi_values[-1] - min_rsi) / (max_rsi - min_rsi)) * 100
        
        # %D = SMA of %K (3 periods)
        if len(rsi_values) >= 3:
            d = sum([
                ((rsi_values[-1] - min_rsi) / (max_rsi - min_rsi) if max_rsi != min_rsi else 0.5) * 100,
                ((rsi_values[-2] - min_rsi) / (max_rsi - min_rsi) if max_rsi != min_rsi else 0.5) * 100,
                ((rsi_values[-3] - min_rsi) / (max_rsi - min_rsi) if max_rsi != min_rsi else 0.5) * 100,
            ]) / 3
        else:
            d = k
        
        return {"k": round(k, 1), "d": round(d, 1)}

    def calculate_probability(self, analysis: Dict) -> int:
        """
        Рассчитывает вероятность успешного сигнала.
        Возвращает баллы от 0 до 15, затем конвертирует в %.
        """
        score = 0
        direction = analysis["direction"]

        rsi = analysis["rsi"]
        macd = analysis["macd"]
        funding = analysis.get("funding_rate", 0) or 0
        volume_ratio = analysis["volume_ratio"]
        bb_position = analysis["bb_position"]
        price_to_support = analysis["price_to_support"]
        price_to_resistance = analysis["price_to_resistance"]
        # Use abs() to reward magnitude regardless of direction
        # Direction is already captured in analysis["direction"]
        change_24h = abs(analysis.get("change_24h", 0))

        # === НОВОЕ: Баллы за сильное движение 24h ===
        movement_points = 0
        if change_24h > 50:
            movement_points = 3  # Очень сильное движение (>50%)
        elif change_24h > 30:
            movement_points = 2  # Сильное движение (30-50%)
        elif change_24h > 15:
            movement_points = 1  # Среднее движение (15-30%)
        score += movement_points
        
        # Лог для отладки
        logger.debug(f"  {analysis['symbol']}: change_24h={change_24h:.1f}% → +{movement_points} points")

        if direction == "long":
            # RSI перепродан
            rsi_points = 0
            if rsi < 25:
                rsi_points = 3
            elif rsi < 30:
                rsi_points = 2
            elif rsi < 40:
                rsi_points = 1
            score += rsi_points

            # MACD бычий
            macd_points = 0
            if macd["crossover"] == "bullish":
                macd_points = 3
            elif macd["histogram"] > 0 and macd["histogram"] > macd.get("prev_histogram", 0):
                macd_points = 2
            score += macd_points

            # Funding отрицательный (шорты платят)
            if funding < -0.01:
                score += 2
            elif funding < 0:
                score += 1

            # Цена у поддержки
            if price_to_support < 2:
                score += 2
            elif price_to_support < 5:
                score += 1

            # BB у нижней границы
            if bb_position < 0.2:
                score += 1
            
            # RSI 4h (НОВОЕ)
            rsi_4h = analysis.get("rsi_4h")
            if rsi_4h is not None:
                if rsi_4h < 30:
                    score += 2  # 4h тоже перепродан = сильный сигнал
                elif rsi_4h < 40:
                    score += 1
                logger.debug(f"  {analysis['symbol']}: RSI_4h={rsi_4h:.1f}")
            
            # EMA тренд (НОВОЕ)
            ema_trend = analysis.get("ema_trend")
            price_vs_ema = analysis.get("price_vs_ema")
            if ema_trend == "bullish":
                score += 1  # EMA20 > EMA50 = бычий тренд
            if price_vs_ema == "above":
                score += 1  # Цена над EMA20
            
            # Stochastic RSI (НОВОЕ)
            stoch_rsi = analysis.get("stoch_rsi", {})
            stoch_k = stoch_rsi.get("k", 50)
            if stoch_k < 20:
                score += 2  # Сильно перепродан
            elif stoch_k < 30:
                score += 1
            logger.debug(f"  {analysis['symbol']}: StochRSI K={stoch_k:.1f}")
                
            logger.debug(f"  {analysis['symbol']}: LONG RSI={rsi:.1f}(+{rsi_points}), MACD(+{macd_points}), BB={bb_position:.2f}")

        else:  # short
            # RSI перекуплен
            rsi_points = 0
            if rsi > 75:
                rsi_points = 3
            elif rsi > 70:
                rsi_points = 2
            elif rsi > 60:
                rsi_points = 1
            score += rsi_points

            # MACD медвежий
            macd_points = 0
            if macd["crossover"] == "bearish":
                macd_points = 3
            elif macd["histogram"] < 0 and macd["histogram"] < macd.get("prev_histogram", 0):
                macd_points = 2
            score += macd_points

            # Funding положительный (лонги платят)
            if funding > 0.01:
                score += 2
            elif funding > 0:
                score += 1

            # Цена у сопротивления
            if price_to_resistance < 2:
                score += 2
            elif price_to_resistance < 5:
                score += 1

            # BB у верхней границы
            if bb_position > 0.8:
                score += 1
            
            # RSI 4h (НОВОЕ)
            rsi_4h = analysis.get("rsi_4h")
            if rsi_4h is not None:
                if rsi_4h > 70:
                    score += 2  # 4h тоже перекуплен = сильный сигнал
                elif rsi_4h > 60:
                    score += 1
                logger.debug(f"  {analysis['symbol']}: RSI_4h={rsi_4h:.1f}")
            
            # EMA тренд (НОВОЕ)
            ema_trend = analysis.get("ema_trend")
            price_vs_ema = analysis.get("price_vs_ema")
            if ema_trend == "bearish":
                score += 1  # EMA20 < EMA50 = медвежий тренд
            if price_vs_ema == "below":
                score += 1  # Цена под EMA20
            
            # Stochastic RSI (НОВОЕ)
            stoch_rsi = analysis.get("stoch_rsi", {})
            stoch_k = stoch_rsi.get("k", 50)
            if stoch_k > 80:
                score += 2  # Сильно перекуплен
            elif stoch_k > 70:
                score += 1
            logger.debug(f"  {analysis['symbol']}: StochRSI K={stoch_k:.1f}")
                
            logger.debug(f"  {analysis['symbol']}: SHORT RSI={rsi:.1f}(+{rsi_points}), MACD(+{macd_points}), BB={bb_position:.2f}")

        # Volume spike (для обоих направлений)
        volume_points = 0
        if volume_ratio > 2.5:
            volume_points = 2
        elif volume_ratio > 1.5:
            volume_points = 1
        score += volume_points
        
        # Accumulation (для обоих направлений)
        accumulation = analysis.get("accumulation", {})
        accumulation_points = 0
        if accumulation.get("detected"):
            strength = accumulation.get("strength")
            if strength == "strong":
                accumulation_points = 4  # Сильное накопление = очень хороший знак
            elif strength == "moderate":
                accumulation_points = 3
            elif strength == "weak":
                accumulation_points = 1
            score += accumulation_points
            logger.debug(f"  {analysis['symbol']}: Accumulation {strength} = +{accumulation_points} points")
        
        logger.debug(f"  {analysis['symbol']}: Volume={volume_ratio:.2f}x(+{volume_points}), Total score={score}")

        score = min(score, 15)

        # Конвертируем в %
        probability = self.score_to_probability(score)

        return probability

    def score_to_probability(self, score: int) -> int:
        """Конвертирует баллы в процент вероятности."""
        if score >= 12:
            return 90
        elif score >= 10:
            return 80
        elif score >= 8:
            return 70
        elif score >= 6:
            return 60
        elif score >= 4:
            return 50
        else:
            return 45

    def calculate_probability_with_breakdown(self, analysis: Dict, direction: str) -> Dict:
        """
        Рассчитывает вероятность с детальным breakdown по категориям.
        
        Args:
            analysis: Данные анализа монеты
            direction: Направление сигнала ("long" или "short")
        
        Returns:
            {
                "probability": 85,
                "breakdown": {
                    "technical": {"score": 30, "max": 40, "details": "RSI=17, MACD бычий"},
                    "volume": {"score": 25, "max": 30, "details": "x2.5 всплеск, накопление"},
                    "funding": {"score": 15, "max": 20, "details": "-0.02% сквиз шортов"},
                    "trend": {"score": 15, "max": 20, "details": "1h+4h совпадают"},
                },
                "total_score": 85,
                "max_score": 110
            }
        """
        breakdown = {
            "technical": {"score": 0, "max": 40, "details": []},
            "volume": {"score": 0, "max": 30, "details": []},
            "funding": {"score": 0, "max": 20, "details": []},
            "trend": {"score": 0, "max": 20, "details": []},
        }
        
        # === TECHNICAL (max 40) ===
        rsi = analysis.get("rsi")
        if rsi:
            if direction == "long" and rsi < 30:
                breakdown["technical"]["score"] += 15
                breakdown["technical"]["details"].append(f"RSI={rsi:.0f} перепродан")
            elif direction == "long" and rsi < 40:
                breakdown["technical"]["score"] += 8
                breakdown["technical"]["details"].append(f"RSI={rsi:.0f}")
            elif direction == "short" and rsi > 70:
                breakdown["technical"]["score"] += 15
                breakdown["technical"]["details"].append(f"RSI={rsi:.0f} перекуплен")
            elif direction == "short" and rsi > 60:
                breakdown["technical"]["score"] += 8
                breakdown["technical"]["details"].append(f"RSI={rsi:.0f}")
        
        # MACD
        macd_signal = analysis.get("macd", {})
        if macd_signal:
            crossover = macd_signal.get("crossover")
            if (direction == "long" and crossover == "bullish") or \
               (direction == "short" and crossover == "bearish"):
                breakdown["technical"]["score"] += 10
                breakdown["technical"]["details"].append(f"MACD {crossover}")
        
        # EMA
        ema_trend = analysis.get("ema_trend")
        if ema_trend:
            if (direction == "long" and ema_trend == "bullish") or \
               (direction == "short" and ema_trend == "bearish"):
                breakdown["technical"]["score"] += 8
                breakdown["technical"]["details"].append(f"EMA {ema_trend}")
        
        # StochRSI
        stoch_rsi = analysis.get("stoch_rsi", {})
        stoch_k = stoch_rsi.get("k", 50)
        if direction == "long" and stoch_k < 20:
            breakdown["technical"]["score"] += 7
            breakdown["technical"]["details"].append(f"StochRSI={stoch_k:.0f}")
        elif direction == "short" and stoch_k > 80:
            breakdown["technical"]["score"] += 7
            breakdown["technical"]["details"].append(f"StochRSI={stoch_k:.0f}")
        
        # === VOLUME (max 30) ===
        volume_ratio = analysis.get("volume_ratio", 1)
        if volume_ratio > 3:
            breakdown["volume"]["score"] += 15
            breakdown["volume"]["details"].append(f"x{volume_ratio:.1f} всплеск")
        elif volume_ratio > 2:
            breakdown["volume"]["score"] += 10
            breakdown["volume"]["details"].append(f"x{volume_ratio:.1f} рост")
        elif volume_ratio > 1.5:
            breakdown["volume"]["score"] += 5
            breakdown["volume"]["details"].append(f"x{volume_ratio:.1f}")
        
        # Accumulation
        accumulation = analysis.get("accumulation", {})
        if accumulation.get("detected"):
            strength = accumulation.get("strength")
            if strength == "strong":
                breakdown["volume"]["score"] += 15
                breakdown["volume"]["details"].append("сильное накопление")
            elif strength == "moderate":
                breakdown["volume"]["score"] += 10
                breakdown["volume"]["details"].append("накопление")
            elif strength == "weak":
                breakdown["volume"]["score"] += 5
                breakdown["volume"]["details"].append("слабое накопление")
        
        # === FUNDING (max 20) ===
        funding = analysis.get("funding_rate")
        if funding is not None:
            if direction == "long" and funding < -0.01:
                breakdown["funding"]["score"] += 15
                breakdown["funding"]["details"].append(f"{funding:.3f}% сквиз шортов")
            elif direction == "long" and funding < 0:
                breakdown["funding"]["score"] += 8
                breakdown["funding"]["details"].append(f"{funding:.3f}%")
            elif direction == "short" and funding > 0.01:
                breakdown["funding"]["score"] += 15
                breakdown["funding"]["details"].append(f"{funding:.3f}% давление лонгов")
            elif direction == "short" and funding > 0:
                breakdown["funding"]["score"] += 8
                breakdown["funding"]["details"].append(f"{funding:.3f}%")
        
        # === TREND (max 20) ===
        rsi_4h = analysis.get("rsi_4h")
        if rsi_4h:
            if direction == "long" and rsi_4h < 30:
                breakdown["trend"]["score"] += 12
                breakdown["trend"]["details"].append(f"RSI_4h={rsi_4h:.0f} перепродан")
            elif direction == "long" and rsi_4h < 40:
                breakdown["trend"]["score"] += 6
                breakdown["trend"]["details"].append(f"RSI_4h={rsi_4h:.0f}")
            elif direction == "short" and rsi_4h > 70:
                breakdown["trend"]["score"] += 12
                breakdown["trend"]["details"].append(f"RSI_4h={rsi_4h:.0f} перекуплен")
            elif direction == "short" and rsi_4h > 60:
                breakdown["trend"]["score"] += 6
                breakdown["trend"]["details"].append(f"RSI_4h={rsi_4h:.0f}")
        
        # Совпадение 1h и 4h
        if rsi and rsi_4h:
            if direction == "long" and rsi < 35 and rsi_4h < 40:
                breakdown["trend"]["score"] += 8
                breakdown["trend"]["details"].append("1h+4h совпадают")
            elif direction == "short" and rsi > 65 and rsi_4h > 60:
                breakdown["trend"]["score"] += 8
                breakdown["trend"]["details"].append("1h+4h совпадают")
        
        # Calculate total
        total_score = sum(cat["score"] for cat in breakdown.values())
        max_score = sum(cat["max"] for cat in breakdown.values())
        
        # Normalize to 0-100 probability
        probability = min(95, max(30, int((total_score / max_score) * 100)))
        
        # Format details as strings
        for cat in breakdown.values():
            cat["details"] = ", ".join(cat["details"]) if cat["details"] else "—"
        
        return {
            "probability": probability,
            "breakdown": breakdown,
            "total_score": total_score,
            "max_score": max_score
        }

    def calculate_real_levels(self, analysis: Dict) -> Dict:
        """
        Рассчитывает реальные уровни входа, стопа и TP
        на основе ATR и текущей волатильности.
        """
        current_price = analysis["current_price"]
        atr = analysis.get("atr", current_price * self.DEFAULT_ATR_PERCENT)
        direction = analysis["direction"]
        
        if direction == "long":
            # Вход: текущая цена с небольшим диапазоном
            entry_low = current_price * 0.99
            entry_high = current_price * 1.01
            
            # Стоп: под текущей ценой на ATR_MULTIPLIER * ATR (обычно 3-8%)
            stop_distance = min(atr * self.ATR_MULTIPLIER, current_price * self.MAX_STOP_LOSS_PERCENT)
            stop_loss = current_price - stop_distance
            
            # TP1: Risk:Reward 1:2
            tp1 = current_price + (stop_distance * 2)
            
            # TP2: Risk:Reward 1:3
            tp2 = current_price + (stop_distance * 3)
            
        else:  # short
            # Вход
            entry_low = current_price * 0.99
            entry_high = current_price * 1.01
            
            # Стоп: над текущей ценой на ATR_MULTIPLIER * ATR
            stop_distance = min(atr * self.ATR_MULTIPLIER, current_price * self.MAX_STOP_LOSS_PERCENT)
            stop_loss = current_price + stop_distance
            
            # TP1: Risk:Reward 1:2
            tp1 = current_price - (stop_distance * 2)
            
            # TP2: Risk:Reward 1:3
            tp2 = current_price - (stop_distance * 3)
        
        # Расчёт процентов
        stop_percent = ((stop_loss - current_price) / current_price) * 100
        tp1_percent = ((tp1 - current_price) / current_price) * 100
        tp2_percent = ((tp2 - current_price) / current_price) * 100
        
        # R:R ratio - должен быть всегда 2.0 при правильном расчёте
        risk = abs(current_price - stop_loss)
        reward = abs(tp1 - current_price)
        # Risk не может быть 0 при правильных данных, но защитимся на всякий случай
        if risk > 0:
            rr_ratio = round(reward / risk, 1)
        else:
            # Это не должно произойти, но если ATR = 0, устанавливаем базовое значение
            logger.warning(f"Risk is 0 for {analysis.get('symbol', 'unknown')}, using fallback R:R")
            rr_ratio = 2.0
        
        return {
            "entry_low": entry_low,
            "entry_high": entry_high,
            "stop_loss": stop_loss,
            "stop_percent": round(stop_percent, 1),
            "tp1": tp1,
            "tp1_percent": round(tp1_percent, 1),
            "tp2": tp2,
            "tp2_percent": round(tp2_percent, 1),
            "rr_ratio": rr_ratio,
        }

    async def scan(self, mode: str = "all") -> List[Dict]:
        """
        Главный метод сканирования.
        Возвращает ТОП-5 сигналов с вероятностью ≥50%
        
        Args:
            mode: "all" - все монеты (спот), "futures" - только фьючерсы
        """
        start_time = time.time()

        logger.info(f"SuperSignals: Starting scan (mode={mode})")

        # Загружаем список фьючерсных пар если нужно
        futures_symbols = set()
        if mode == "futures":
            futures_symbols = await self.fetch_futures_symbols()
            if not futures_symbols:
                logger.warning("No futures symbols loaded, falling back to all mode")
                mode = "all"
            else:
                logger.info(f"Futures mode: filtering by {len(futures_symbols)} symbols")

        # Этап 1: Скринер
        all_coins = await self.fetch_all_coins()
        
        # После получения всех монет, фильтруем по режиму
        if mode == "futures" and futures_symbols:
            coins_before = len(all_coins)
            all_coins = [c for c in all_coins if c.get("symbol", "").upper() in futures_symbols]
            logger.info(f"Futures filter: {coins_before} → {len(all_coins)} coins")
        
        filtered = self.apply_filters(all_coins)

        # Сортируем по движению и берём ТОП-30
        filtered.sort(key=lambda x: abs(x.get("price_change_percentage_24h", 0)), reverse=True)
        top_candidates = filtered[: self.TOP_CANDIDATES]

        logger.info(f"SuperSignals: Stage 2 - Deep analysis of {len(top_candidates)} candidates")
        
        # Логируем кандидатов
        for i, coin in enumerate(top_candidates[:5], 1):
            logger.info(f"  Candidate #{i}: {coin['symbol']} ({coin['price_change_percentage_24h']:+.1f}%)")

        # Этап 2: Глубокий анализ
        analyzed = []
        for coin in top_candidates:
            result = await self.deep_analyze(coin)
            if result:
                analyzed.append(result)
            await asyncio.sleep(0.1)

        # Логируем результат анализа
        logger.info(f"SuperSignals: Analyzed {len(top_candidates)} coins, accepted {len(analyzed)}")

        # Сортируем по вероятности
        analyzed.sort(key=lambda x: x["probability"], reverse=True)
        top_signals = analyzed[: self.TOP_SIGNALS]

        elapsed = time.time() - start_time
        logger.info(f"SuperSignals: Found {len(top_signals)} signals in {elapsed:.1f}s")
        
        # Логируем результаты
        for i, signal in enumerate(top_signals, 1):
            logger.info(f"  Signal #{i}: {signal['symbol']} - {signal['probability']}% ({signal['direction']})")

        return top_signals

    def format_message(self, signals: List[Dict], scanned_count: int, filtered_count: int, mode: str = "all") -> str:
        """Форматирует супер сигналы для вывода."""
        now = datetime.now().strftime("%H:%M:%S")

        if mode == "futures":
            title = "⚡ *ФЬЮЧЕРСЫ ТОП\\-5*"
            scan_text = f"📊 Просканировано: {scanned_count:,}\\+ фьючерсных пар"
        else:
            title = f"⚡ *СУПЕР СИГНАЛЫ \\(ТОП\\-{len(signals)}\\)*"
            scan_text = f"📊 Просканировано: {scanned_count:,} монет"

        header = f"""{title}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{scan_text}
🔬 Глубокий анализ: 30 монет
⏰ Обновлено: {now}
"""

        messages = [header]

        for i, signal in enumerate(signals, 1):
            direction = "📈 ЛОНГ" if signal["direction"] == "long" else "📉 ШОРТ"
            prob = signal["probability"]

            # Эмодзи вероятности
            if prob >= 80:
                prob_emoji = "🟢🟢🟢"
            elif prob >= 70:
                prob_emoji = "🟢🟢"
            else:
                prob_emoji = "🟢"

            # RSI
            rsi = signal["rsi"]
            if rsi < 30:
                rsi_status = "🟢 перепродан"
            elif rsi > 70:
                rsi_status = "🔴 перекуплен"
            else:
                rsi_status = "🟡 нейтрально"

            # MACD
            macd = signal["macd"]
            if macd.get("crossover") == "bullish":
                macd_status = "🟢 пересечение вверх"
            elif macd.get("crossover") == "bearish":
                macd_status = "🔴 пересечение вниз"
            elif macd.get("histogram", 0) > 0:
                macd_status = "🟢 бычий"
            else:
                macd_status = "🔴 медвежий"

            # Funding
            funding = signal.get("funding_rate", 0)
            if funding and funding < -0.01:
                funding_status = f"🟢 {funding:.3f}% \\(сквиз шортов\\)"
            elif funding and funding > 0.01:
                funding_status = f"🔴 {funding:.3f}% \\(лонги платят\\)"
            else:
                funding_status = f"🟡 {funding:.3f}%" if funding else "🟡 N/A"

            # Volume
            vol_ratio = signal.get("volume_ratio", 1)
            if vol_ratio > 2:
                vol_status = f"🟢 x{vol_ratio:.1f} всплеск"
            elif vol_ratio > 1.5:
                vol_status = f"🟢 x{vol_ratio:.1f} повышен"
            else:
                vol_status = f"🟡 x{vol_ratio:.1f}"

            # RSI 4h (НОВОЕ)
            rsi_4h = signal.get("rsi_4h")
            rsi_4h_line = ""
            if rsi_4h:
                if rsi_4h < 30:
                    rsi_4h_emoji = "🟢"
                    rsi_4h_text = "перепродан"
                elif rsi_4h > 70:
                    rsi_4h_emoji = "🔴"
                    rsi_4h_text = "перекуплен"
                else:
                    rsi_4h_emoji = "🟡"
                    rsi_4h_text = "нейтрально"
                rsi_4h_line = f"• RSI\\(4h\\): {rsi_4h:.0f} {rsi_4h_emoji} {rsi_4h_text}\n"

            # EMA (НОВОЕ)
            ema_trend = signal.get("ema_trend")
            ema_line = ""
            if ema_trend:
                ema_emoji = "🟢" if ema_trend == "bullish" else "🔴"
                ema_text = "бычий" if ema_trend == "bullish" else "медвежий"
                ema_line = f"• EMA 20/50: {ema_emoji} {ema_text}\n"

            # Stochastic RSI (НОВОЕ)
            stoch_rsi = signal.get("stoch_rsi", {})
            stoch_k = stoch_rsi.get("k")
            stoch_line = ""
            if stoch_k:
                if stoch_k < 20:
                    stoch_emoji = "🟢"
                    stoch_text = "перепродан"
                elif stoch_k > 80:
                    stoch_emoji = "🔴"
                    stoch_text = "перекуплен"
                else:
                    stoch_emoji = "🟡"
                    stoch_text = "нейтрально"
                stoch_line = f"• StochRSI: {stoch_k:.0f} {stoch_emoji} {stoch_text}\n"

            # Exchanges
            exchanges = signal.get("exchanges", [])
            exchanges_str = " • ".join([f"{ex} ✅" for ex in exchanges[:4]]) if exchanges else "Нет данных"

            # Levels
            levels = signal["levels"]

            # Format price
            current_price = signal["current_price"]
            if current_price >= 1:
                price_str = f"${current_price:.2f}"
            elif current_price >= 0.01:
                price_str = f"${current_price:.4f}"
            else:
                price_str = f"${current_price:.8f}"

            def format_price(p):
                if p >= 1:
                    return f"${p:.2f}"
                elif p >= 0.01:
                    return f"${p:.4f}"
                else:
                    return f"${p:.8f}"

            # Accumulation
            accumulation = signal.get("accumulation", {})
            accumulation_line = ""
            if accumulation.get("detected"):
                accum_signal = accumulation.get("signal", "")
                vol_inc = accumulation.get("volume_increase", 0)
                price_ch = accumulation.get("price_change", 0)
                accumulation_line = f"• Накопление: {accum_signal} \\(объём \\+{vol_inc:.0f}%, цена {price_ch:.1f}%\\)\n"

            # Breakdown (если есть)
            breakdown = signal.get("breakdown")
            breakdown_text = ""
            if breakdown:
                breakdown_text = "\n📊 Breakdown:\n"
                
                tech = breakdown.get("technical", {})
                if tech.get("score", 0) > 0:
                    breakdown_text += f"• Технический: \\+{tech['score']}/{tech['max']} \\({tech['details']}\\)\n"
                
                vol = breakdown.get("volume", {})
                if vol.get("score", 0) > 0:
                    breakdown_text += f"• Объём: \\+{vol['score']}/{vol['max']} \\({vol['details']}\\)\n"
                
                fund = breakdown.get("funding", {})
                if fund.get("score", 0) > 0:
                    breakdown_text += f"• Funding: \\+{fund['score']}/{fund['max']} \\({fund['details']}\\)\n"
                
                trend = breakdown.get("trend", {})
                if trend.get("score", 0) > 0:
                    breakdown_text += f"• Тренд: \\+{trend['score']}/{trend['max']} \\({trend['details']}\\)\n"

            msg = f"""
⚡ \\#{i} {signal['symbol']}/USDT \\| {direction}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Цена: {price_str}
🎯 Вероятность: {prob}% {prob_emoji}

🔮 Почему сейчас:
• RSI\\(1h\\): {rsi:.0f} {rsi_status}
{rsi_4h_line}• MACD: {macd_status}
• Funding: {funding_status}
{ema_line}{stoch_line}• Объём: {vol_status}
{accumulation_line}{breakdown_text}
⏰ Ожидание: 1\\-4 часа

📍 Уровни:
• Вход: {format_price(levels['entry_low'])}\\-{format_price(levels['entry_high'])}
• Стоп: {format_price(levels['stop_loss'])} \\({levels['stop_percent']:+.1f}%\\)
• TP1: {format_price(levels['tp1'])} \\({levels['tp1_percent']:+.1f}%\\)
• TP2: {format_price(levels['tp2'])} \\({levels['tp2_percent']:+.1f}%\\)
📊 R:R = 1:{levels['rr_ratio']}

🏦 Где торговать:
{exchanges_str}
"""
            messages.append(msg)

        footer = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Данные: Binance \\+ CoinLore \\+ CoinPaprika \\+ CoinGecko
⚠️ Не является финансовым советом\\!
"""
        messages.append(footer)

        return "\n".join(messages)
