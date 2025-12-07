"""
AI Signals - анализ и прогнозирование движения цен на основе данных китов и рынка.

Анализирует активность китов и рыночные данные для прогнозирования движения цены на ближайший час.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import aiohttp
import asyncio
import numpy as np

from api_manager import get_coin_price
from signals.indicators import (
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_ma_crossover, calculate_stochastic_rsi, calculate_mfi,
    calculate_roc, calculate_williams_r, calculate_atr, calculate_keltner_channels,
    calculate_obv, calculate_vwap, calculate_volume_sma,
    calculate_pivot_points, calculate_fibonacci_levels
)
from signals.data_sources import DataSourceManager

logger = logging.getLogger(__name__)


class AISignalAnalyzer:
    """
    Анализатор AI сигналов для криптовалют.
    
    Использует данные китов и рыночные данные для прогнозирования движения цены.
    """
    
    # Константы для расчёта сигнала
    WHALE_SCORE_WEIGHT = 40  # Максимальный вес whale score
    PRICE_SCORE_WEIGHT = 30  # Максимальный вес price score
    VOLUME_SCORE_VALUE = 10  # Значение volume score
    HIGH_VOLUME_THRESHOLD = 10_000_000_000  # Порог высокого объёма ($10B)
    
    # Константы для нормализации score в проценты (диапазон -80 до +80)
    MIN_SCORE = -80  # Минимальный возможный score
    MAX_SCORE = 80   # Максимальный возможный score
    SCORE_RANGE = MAX_SCORE - MIN_SCORE  # Полный диапазон score (160)
    
    # Новые константы для расширенного анализа
    CACHE_TTL_PRICE_HISTORY = 300  # 5 минут
    CACHE_TTL_FEAR_GREED = 1800  # 30 минут
    CACHE_TTL_FUNDING_RATE = 300  # 5 минут
    MIN_PRICE_POINTS = 30  # Минимум точек для индикаторов
    
    # Веса для 22-факторной системы (100% total)
    # Долгосрочные факторы (35% веса)
    WHALE_WEIGHT = 0.04          # 4%
    TREND_WEIGHT = 0.05          # 5%
    MOMENTUM_WEIGHT = 0.04       # 4%
    VOLATILITY_WEIGHT = 0.04     # 4%
    VOLUME_WEIGHT = 0.04         # 4%
    MARKET_WEIGHT = 0.04         # 4%
    ORDERBOOK_WEIGHT = 0.04      # 4%
    DERIVATIVES_WEIGHT = 0.03    # 3%
    ONCHAIN_WEIGHT = 0.02        # 2%
    SENTIMENT_WEIGHT = 0.01      # 1%
    
    # Краткосрочные факторы (35% веса)
    SHORT_TREND_WEIGHT = 0.08    # 8% - RSI 5м/15м, EMA
    TRADES_FLOW_WEIGHT = 0.07    # 7% - Buy/Sell flow
    LIQUIDATIONS_WEIGHT = 0.06   # 6% - Ликвидации
    ORDERBOOK_DELTA_WEIGHT = 0.07 # 7% - Изменение order book
    PRICE_MOMENTUM_WEIGHT = 0.07 # 7% - Движение цены за 10 мин
    
    # Новые источники (30% веса)
    COINGLASS_OI_WEIGHT = 0.05    # 5% - Open Interest Change
    COINGLASS_TOP_TRADERS_WEIGHT = 0.05  # 5% - Top Traders L/S
    NEWS_SENTIMENT_WEIGHT = 0.05  # 5% - CryptoPanic
    TRADINGVIEW_WEIGHT = 0.06     # 6% - TradingView Rating
    WHALE_ALERT_WEIGHT = 0.05     # 5% - Whale Alert
    SOCIAL_WEIGHT = 0.04          # 4% - LunarCrush
    
    # Scaling factor for final score calculation
    SCORE_SCALE_FACTOR = 10  # Scale weighted sum from -10/+10 to -100/+100
    
    # Short-term analysis constants
    EMA_CROSSOVER_THRESHOLD = 0.001  # 0.1% threshold for EMA crossover detection
    LONG_LIQUIDATION_RATIO = 0.7     # Assumed ratio of long liquidations in total
    SHORT_LIQUIDATION_RATIO = 0.3    # Assumed ratio of short liquidations in total
    TRADES_FLOW_BULLISH_THRESHOLD = 1.5   # Buy/Sell ratio threshold for bullish
    TRADES_FLOW_BEARISH_THRESHOLD = 0.67  # Buy/Sell ratio threshold for bearish
    TRADES_FLOW_NEUTRAL_DIVISOR = 0.33    # Normalization divisor for neutral range
    
    def __init__(self, whale_tracker):
        """
        Инициализация анализатора.
        
        Args:
            whale_tracker: Экземпляр WhaleTracker для получения данных о транзакциях китов
        """
        self.whale_tracker = whale_tracker
        self.data_source_manager = DataSourceManager()
        
        # Маппинг символов для whale tracker
        self.blockchain_mapping = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
        }
        
        # Маппинг для CoinGecko API
        self.coingecko_mapping = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
        }
        
        # Маппинг для Bybit
        self.bybit_mapping = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
        }
        
        # Простой кэш для внешних API
        self._cache = {}
        self._cache_timestamps = {}
        
        # Хранилище для расчёта delta (краткосрочные данные)
        self._previous_orderbook = {}  # {"BTC": {...}, "ETH": {...}}
        self._previous_prices = {}  # {"BTC": [(timestamp, price), ...], "ETH": [...]}
        
        logger.info("AISignalAnalyzer initialized with 22-factor system")
    
    def _get_cache(self, key: str, ttl_seconds: int) -> Optional[Dict]:
        """
        Получить данные из кэша, если они еще актуальны.
        
        Args:
            key: Ключ кэша
            ttl_seconds: Время жизни кэша в секундах
            
        Returns:
            Данные из кэша или None если кэш устарел
        """
        if key not in self._cache:
            return None
        
        age = datetime.now() - self._cache_timestamps.get(key, datetime.min)
        if age > timedelta(seconds=ttl_seconds):
            return None
        
        return self._cache[key]
    
    def _set_cache(self, key: str, value: Dict):
        """
        Сохранить данные в кэш.
        
        Args:
            key: Ключ кэша
            value: Данные для сохранения
        """
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()
    
    def clear_cache(self):
        """Очистить весь кэш для получения свежих данных."""
        self._cache = {}
        self._cache_timestamps = {}
        logger.info("AISignalAnalyzer cache cleared")
    
    async def get_whale_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение данных о транзакциях китов за последний час.
        
        Args:
            symbol: Символ монеты (BTC, ETH)
            
        Returns:
            Dict с данными китов или None если данные недоступны
        """
        try:
            blockchain = self.blockchain_mapping.get(symbol)
            if not blockchain:
                logger.warning(f"Unknown symbol for whale tracking: {symbol}")
                return None
            
            # Получаем транзакции для конкретного блокчейна
            transactions = await self.whale_tracker.get_transactions_by_blockchain(
                blockchain=blockchain.lower(),
                limit=50
            )
            
            if not transactions:
                logger.info(f"No whale transactions found for {symbol}")
                return {
                    "transaction_count": 0,
                    "total_volume_usd": 0,
                    "deposits": 0,
                    "withdrawals": 0,
                    "largest_transaction": 0,
                    "sentiment": "neutral"
                }
            
            # Подсчитываем депозиты и выводы
            deposits = sum(1 for tx in transactions if tx.is_exchange_deposit)
            withdrawals = sum(1 for tx in transactions if tx.is_exchange_withdrawal)
            total_volume = sum(tx.amount_usd for tx in transactions)
            largest_tx = max((tx.amount_usd for tx in transactions), default=0)
            
            # Определяем настроение
            if withdrawals > deposits:
                sentiment = "bullish"
            elif deposits > withdrawals:
                sentiment = "bearish"
            else:
                sentiment = "neutral"
            
            return {
                "transaction_count": len(transactions),
                "total_volume_usd": total_volume,
                "deposits": deposits,
                "withdrawals": withdrawals,
                "largest_transaction": largest_tx,
                "sentiment": sentiment
            }
            
        except Exception as e:
            logger.error(f"Error getting whale data for {symbol}: {e}")
            return None
    
    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение рыночных данных.
        
        Args:
            symbol: Символ монеты (BTC, ETH)
            
        Returns:
            Dict с рыночными данными или None если данные недоступны
        """
        try:
            price_data = await get_coin_price(symbol)
            
            if not price_data.get("success"):
                logger.warning(f"Failed to get market data for {symbol}")
                return None
            
            return {
                "price_usd": price_data.get("price_usd", 0),
                "change_24h": price_data.get("change_24h", 0),
                "volume_24h": price_data.get("volume_24h", 0),
                "market_cap": price_data.get("market_cap", 0),
            }
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
    
    async def get_price_history_bybit(self, symbol: str, interval: str = "60", limit: int = 300) -> Optional[List[float]]:
        """
        Получение истории цен с Bybit вместо CoinGecko (fallback для rate limit).
        
        Endpoint: https://api.bybit.com/v5/market/kline?category=spot&symbol=ETHUSDT&interval=60&limit=300
        
        Args:
            symbol: BTC или ETH
            interval: Интервал в минутах (60 = 1 час)
            limit: Количество свечей (макс 1000)
        
        Returns:
            List[float]: Список цен закрытия
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown Bybit symbol for price history: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/kline"
            params = {
                "category": "spot",
                "symbol": bybit_symbol,
                "interval": interval,
                "limit": limit
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data.get("result", {})
                        klines = result.get("list", [])
                        
                        if klines:
                            # Bybit returns [startTime, open, high, low, close, volume, turnover]
                            # Reverse order (most recent first -> oldest first)
                            prices = [float(kline[4]) for kline in reversed(klines)]
                            logger.info(f"Fetched {len(prices)} price points from Bybit for {symbol}")
                            return prices
                    else:
                        logger.warning(f"Failed to fetch Bybit price history for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting Bybit price history for {symbol}: {e}")
            return None
    
    async def get_price_history(self, symbol: str, days: int = 1) -> Optional[List[float]]:
        """
        Получение исторических цен для расчёта индикаторов.
        Сначала пробует CoinGecko API, при rate limit использует Bybit.
        
        Args:
            symbol: BTC или ETH
            days: Количество дней (1 день = ~288 точек при интервале 5 мин)
        
        Returns:
            List[float]: Список цен закрытия
        """
        cache_key = f"price_history_{symbol}_{days}"
        
        # Проверяем кэш
        cached_data = self._get_cache(cache_key, self.CACHE_TTL_PRICE_HISTORY)
        if cached_data is not None:
            return cached_data
        
        try:
            coin_id = self.coingecko_mapping.get(symbol)
            if not coin_id:
                logger.warning(f"Unknown coin for price history: {symbol}")
                return None
            
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": "usd",
                "days": days
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices = [price[1] for price in data.get("prices", [])]
                        
                        if prices:
                            self._set_cache(cache_key, prices)
                            logger.info(f"Fetched {len(prices)} price points from CoinGecko for {symbol}")
                            return prices
                    elif response.status == 429:
                        logger.warning(f"CoinGecko rate limit reached for {symbol}, trying Bybit fallback...")
                        # Use Bybit as fallback
                        bybit_prices = await self.get_price_history_bybit(symbol, interval="60", limit=min(days * 24, 300))
                        if bybit_prices:
                            self._set_cache(cache_key, bybit_prices)
                            return bybit_prices
                        return None
                    else:
                        logger.warning(f"Failed to fetch price history for {symbol}: {response.status}")
                        # Try Bybit as fallback for any error
                        bybit_prices = await self.get_price_history_bybit(symbol, interval="60", limit=min(days * 24, 300))
                        if bybit_prices:
                            self._set_cache(cache_key, bybit_prices)
                            return bybit_prices
                        return None
        except Exception as e:
            logger.error(f"Error getting price history for {symbol}: {e}")
            # Try Bybit as last resort fallback
            try:
                bybit_prices = await self.get_price_history_bybit(symbol, interval="60", limit=min(days * 24, 300))
                if bybit_prices:
                    self._set_cache(cache_key, bybit_prices)
                    return bybit_prices
            except Exception as e2:
                logger.error(f"Error getting Bybit fallback for {symbol}: {e2}")
            return None
    
    async def calculate_technical_indicators(self, symbol: str, ohlcv_data: Optional[List] = None) -> Optional[Dict]:
        """
        Calculate all technical indicators.
        
        Args:
            symbol: Symbol (BTC, ETH)
            ohlcv_data: Optional OHLCV data from CryptoCompare
        
        Returns:
            Dict with all technical indicators
        """
        try:
            # Get historical data
            prices = await self.get_price_history(symbol, days=1)
            
            if not prices or len(prices) < self.MIN_PRICE_POINTS:
                logger.warning(f"Insufficient price data for technical indicators: {symbol}")
                return None
            
            result = {}
            
            # Basic indicators (existing)
            rsi = calculate_rsi(prices, period=14)
            macd = calculate_macd(prices)
            bb = calculate_bollinger_bands(prices, period=20)
            
            if rsi:
                result["rsi"] = {
                    "value": rsi.value,
                    "signal": rsi.signal,
                    "period": rsi.period
                }
            
            if macd:
                result["macd"] = {
                    "macd_line": macd.macd_line,
                    "signal_line": macd.signal_line,
                    "histogram": macd.histogram,
                    "signal": macd.signal
                }
            
            if bb:
                result["bollinger_bands"] = {
                    "upper": bb.upper,
                    "middle": bb.middle,
                    "lower": bb.lower,
                    "current_price": bb.current_price,
                    "position": bb.position,
                    "bandwidth": bb.bandwidth,
                    "percent_b": bb.percent_b
                }
            
            # New Trend Indicators
            if len(prices) >= 200:
                ma_cross = calculate_ma_crossover(prices, short_period=50, long_period=200)
                if ma_cross:
                    result["ma_crossover"] = {
                        "ma_short": ma_cross.ma_short,
                        "ma_long": ma_cross.ma_long,
                        "crossover": ma_cross.crossover,
                        "trend": ma_cross.trend
                    }
            
            # New Momentum Indicators
            stoch_rsi = calculate_stochastic_rsi(prices, period=14, smooth_k=3, smooth_d=3)
            if stoch_rsi:
                result["stoch_rsi"] = {
                    "k": stoch_rsi.k,
                    "d": stoch_rsi.d,
                    "signal": stoch_rsi.signal
                }
            
            roc = calculate_roc(prices, period=12)
            if roc:
                result["roc"] = {
                    "value": roc.value,
                    "momentum": roc.momentum
                }
            
            # Indicators requiring OHLCV data
            if ohlcv_data and len(ohlcv_data) >= 14:
                high_prices = [c["high"] for c in ohlcv_data]
                low_prices = [c["low"] for c in ohlcv_data]
                close_prices = [c["close"] for c in ohlcv_data]
                volumes = [c["volumeto"] for c in ohlcv_data]  # Volume in USD
                
                # MFI
                mfi = calculate_mfi(high_prices, low_prices, close_prices, volumes, period=14)
                if mfi:
                    result["mfi"] = {
                        "value": mfi.value,
                        "signal": mfi.signal
                    }
                
                # Williams %R
                williams = calculate_williams_r(high_prices, low_prices, close_prices, period=14)
                if williams:
                    result["williams_r"] = {
                        "value": williams.value,
                        "signal": williams.signal
                    }
                
                # ATR
                atr = calculate_atr(high_prices, low_prices, close_prices, period=14)
                if atr:
                    result["atr"] = {
                        "value": atr.value,
                        "percent": atr.percent,
                        "volatility": atr.volatility
                    }
                
                # Keltner Channels
                keltner = calculate_keltner_channels(high_prices, low_prices, close_prices, period=20, multiplier=2.0)
                if keltner:
                    result["keltner_channels"] = {
                        "upper": keltner.upper,
                        "middle": keltner.middle,
                        "lower": keltner.lower,
                        "position": keltner.position
                    }
                
                # OBV
                obv = calculate_obv(close_prices, volumes)
                if obv:
                    result["obv"] = {
                        "value": obv.value,
                        "trend": obv.trend,
                        "sma": obv.sma
                    }
                
                # VWAP
                vwap = calculate_vwap(high_prices, low_prices, close_prices, volumes)
                if vwap:
                    result["vwap"] = {
                        "value": vwap.value,
                        "position": vwap.position,
                        "deviation_percent": vwap.deviation_percent
                    }
                
                # Volume SMA
                vol_sma = calculate_volume_sma(volumes, period=20)
                if vol_sma:
                    result["volume_sma"] = {
                        "current_volume": vol_sma.current_volume,
                        "sma": vol_sma.sma,
                        "ratio": vol_sma.ratio,
                        "status": vol_sma.status
                    }
                
                # Pivot Points (using previous day's data)
                if len(ohlcv_data) >= 2:
                    prev_candle = ohlcv_data[-2]
                    current_price = close_prices[-1]
                    pivot = calculate_pivot_points(
                        prev_candle["high"],
                        prev_candle["low"],
                        prev_candle["close"],
                        current_price
                    )
                    result["pivot_points"] = {
                        "pivot": pivot.pivot,
                        "r1": pivot.r1,
                        "r2": pivot.r2,
                        "r3": pivot.r3,
                        "s1": pivot.s1,
                        "s2": pivot.s2,
                        "s3": pivot.s3,
                        "current_zone": pivot.current_zone
                    }
                
                # Fibonacci Levels
                if len(high_prices) >= 20:
                    period_high = max(high_prices[-20:])
                    period_low = min(low_prices[-20:])
                    current_price = close_prices[-1]
                    fib = calculate_fibonacci_levels(period_high, period_low, current_price)
                    result["fibonacci"] = {
                        "level_0": fib.level_0,
                        "level_236": fib.level_236,
                        "level_382": fib.level_382,
                        "level_50": fib.level_50,
                        "level_618": fib.level_618,
                        "level_786": fib.level_786,
                        "level_100": fib.level_100,
                        "nearest_level": fib.nearest_level,
                        "nearest_value": fib.nearest_value
                    }
            
            logger.info(f"Calculated {len(result)} technical indicators for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators for {symbol}: {e}")
            return None
    
    async def get_fear_greed_index(self) -> Optional[Dict]:
        """
        Получение Fear & Greed Index.
        API: https://api.alternative.me/fng/
        
        Returns:
            Dict: {"value": 75, "classification": "Greed"}
        """
        cache_key = "fear_greed_index"
        
        # Проверяем кэш
        cached_data = self._get_cache(cache_key, self.CACHE_TTL_FEAR_GREED)
        if cached_data is not None:
            return cached_data
        
        try:
            url = "https://api.alternative.me/fng/"
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        fng_data = data.get("data", [{}])[0]
                        
                        result = {
                            "value": int(fng_data.get("value", 50)),
                            "classification": fng_data.get("value_classification", "Neutral")
                        }
                        
                        self._set_cache(cache_key, result)
                        logger.info(f"Fetched Fear & Greed Index: {result['value']}")
                        return result
                    else:
                        logger.warning(f"Failed to fetch Fear & Greed Index: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting Fear & Greed Index: {e}")
            return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        Получение Funding Rate с Bybit.
        API: https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1
        
        Returns:
            Dict: {"rate": 0.0001, "rate_percent": 0.01}
        """
        cache_key = f"funding_rate_{symbol}"
        
        # Проверяем кэш
        cached_data = self._get_cache(cache_key, self.CACHE_TTL_FUNDING_RATE)
        if cached_data is not None:
            return cached_data
        
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for funding rate: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/funding/history"
            params = {
                "category": "linear",
                "symbol": bybit_symbol,
                "limit": 1
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        result_data = data.get("result", {})
                        funding_list = result_data.get("list", [])
                        
                        if funding_list and len(funding_list) > 0:
                            latest_funding = funding_list[0]
                            funding_rate = float(latest_funding.get("fundingRate", 0))
                            rate_percent = funding_rate * 100
                            
                            result = {
                                "rate": funding_rate,
                                "rate_percent": rate_percent
                            }
                            
                            self._set_cache(cache_key, result)
                            logger.info(f"Fetched funding rate for {symbol}: {rate_percent:.4f}%")
                            return result
                        else:
                            logger.warning(f"Empty funding rate data for {symbol}")
                            return None
                    else:
                        logger.warning(f"Failed to fetch funding rate for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            return None
    
    async def get_short_term_ohlcv(self, symbol: str, interval: str = "5", limit: int = 50) -> Optional[List]:
        """
        Получение краткосрочных свечей с Bybit.
        НЕ кэшируется для получения свежих данных!
        
        Args:
            symbol: BTC или ETH
            interval: "5" (5 мин), "15" (15 мин)
            limit: количество свечей
        
        API: https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval=5&limit=50
        
        Returns:
            List of candles: [{"open": 97000, "high": 98000, "low": 96500, "close": 97500, 
                               "volume": 123.45, "timestamp": 1234567890}, ...]
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for short-term OHLCV: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/kline"
            params = {
                "category": "spot",
                "symbol": bybit_symbol,
                "interval": interval,
                "limit": limit
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit kline error: {data.get('retMsg')}")
                            return None
                        
                        klines = data.get("result", {}).get("list", [])
                        
                        if not klines:
                            return None
                        
                        result = []
                        for kline in klines:
                            # Bybit format: [timestamp, open, high, low, close, volume, turnover]
                            result.append({
                                "timestamp": int(kline[0]),
                                "open": float(kline[1]),
                                "high": float(kline[2]),
                                "low": float(kline[3]),
                                "close": float(kline[4]),
                                "volume": float(kline[5])
                            })
                        
                        logger.info(f"Fetched {len(result)} short-term {interval}m candles for {symbol}")
                        return result
                    else:
                        logger.warning(f"Failed to fetch short-term OHLCV for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting short-term OHLCV for {symbol}: {e}")
            return None
    
    async def get_recent_trades_flow(self, symbol: str) -> Optional[Dict]:
        """
        Анализ потока сделок за последние 10 минут.
        НЕ кэшируется для получения свежих данных!
        
        Args:
            symbol: BTC или ETH
        
        API: https://api.bybit.com/v5/market/recent-trade?category=spot&symbol=BTCUSDT&limit=1000
        
        Returns:
            {
                "buy_volume": 1234567,
                "sell_volume": 987654,
                "buy_count": 150,
                "sell_count": 120,
                "flow_ratio": 1.25,  # buy/sell
                "sentiment": "bullish"  # bullish/bearish/neutral
            }
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for trades flow: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/recent-trade"
            params = {
                "category": "spot",
                "symbol": bybit_symbol,
                "limit": 1000
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit trades error: {data.get('retMsg')}")
                            return None
                        
                        trades = data.get("result", {}).get("list", [])
                        
                        if not trades:
                            return None
                        
                        # Filter only last 10 minutes
                        now_ms = datetime.now().timestamp() * 1000
                        ten_min_ago_ms = now_ms - (10 * 60 * 1000)
                        
                        buy_volume = 0.0
                        sell_volume = 0.0
                        buy_count = 0
                        sell_count = 0
                        
                        for trade in trades:
                            trade_time = int(trade.get("time", 0))
                            if trade_time < ten_min_ago_ms:
                                continue
                            
                            price = float(trade.get("price", 0))
                            size = float(trade.get("size", 0))
                            side = trade.get("side", "")
                            
                            if price <= 0 or size <= 0 or not side:
                                continue
                            
                            volume_usd = price * size
                            
                            if side == "Buy":
                                buy_volume += volume_usd
                                buy_count += 1
                            elif side == "Sell":
                                sell_volume += volume_usd
                                sell_count += 1
                        
                        # Calculate flow ratio and sentiment
                        flow_ratio = buy_volume / sell_volume if sell_volume > 0 else 1.0
                        
                        if flow_ratio > 1.2:
                            sentiment = "bullish"
                        elif flow_ratio < 0.83:
                            sentiment = "bearish"
                        else:
                            sentiment = "neutral"
                        
                        result = {
                            "buy_volume": round(buy_volume, 2),
                            "sell_volume": round(sell_volume, 2),
                            "buy_count": buy_count,
                            "sell_count": sell_count,
                            "flow_ratio": round(flow_ratio, 3),
                            "sentiment": sentiment
                        }
                        
                        logger.info(f"Analyzed trades flow for {symbol}: {sentiment} (ratio: {flow_ratio:.2f})")
                        return result
                    else:
                        logger.warning(f"Failed to fetch trades flow for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting trades flow for {symbol}: {e}")
            return None
    
    async def get_liquidations(self, symbol: str) -> Optional[Dict]:
        """
        Получение данных о ликвидациях из Bybit futures.
        НЕ кэшируется для получения свежих данных!
        
        Args:
            symbol: BTC или ETH
        
        Note: Bybit не предоставляет прямого API для ликвидаций.
        Используем Open Interest изменения как прокси для ликвидаций.
        
        Returns:
            {
                "long_liquidations": 5000000,
                "short_liquidations": 3000000,
                "net_liquidations": 2000000,  # long - short
                "sentiment": "bearish"  # много лонг ликвидаций = bearish
            }
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for liquidations: {symbol}")
                return None
            
            # Используем open interest change как прокси для ликвидаций
            url = "https://api.bybit.com/v5/market/open-interest"
            params = {
                "category": "linear",
                "symbol": bybit_symbol,
                "intervalTime": "5min",
                "limit": 10
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit OI error: {data.get('retMsg')}")
                            return None
                        
                        oi_list = data.get("result", {}).get("list", [])
                        
                        if not oi_list or len(oi_list) < 2:
                            return None
                        
                        # Calculate OI change
                        latest_oi = float(oi_list[0].get("openInterest", 0))
                        prev_oi = float(oi_list[-1].get("openInterest", 0))
                        oi_change = latest_oi - prev_oi
                        
                        # Negative OI change suggests liquidations
                        # Positive suggests new positions opening
                        if oi_change < 0:
                            # OI decreased = liquidations happened
                            liquidation_volume = abs(oi_change)
                            # Estimate split based on historical ratios
                            long_liquidations = liquidation_volume * self.LONG_LIQUIDATION_RATIO
                            short_liquidations = liquidation_volume * self.SHORT_LIQUIDATION_RATIO
                            sentiment = "bearish"  # More longs liquidated
                        else:
                            # OI increased or stable
                            long_liquidations = 0
                            short_liquidations = 0
                            sentiment = "neutral"
                        
                        net_liquidations = long_liquidations - short_liquidations
                        
                        result = {
                            "long_liquidations": round(long_liquidations, 2),
                            "short_liquidations": round(short_liquidations, 2),
                            "net_liquidations": round(net_liquidations, 2),
                            "sentiment": sentiment
                        }
                        
                        logger.info(f"Analyzed liquidations for {symbol}: {sentiment}")
                        return result
                    else:
                        logger.warning(f"Failed to fetch liquidations for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting liquidations for {symbol}: {e}")
            return None
    
    async def get_orderbook_delta(self, symbol: str) -> Optional[Dict]:
        """
        Изменение order book за последние запросы.
        Сравнивает текущий order book с предыдущим (хранится в памяти).
        НЕ кэшируется для получения свежих данных!
        
        Args:
            symbol: BTC или ETH
        
        Returns:
            {
                "bid_change": +5.2,  # % изменение bid wall
                "ask_change": -3.1,  # % изменение ask wall
                "delta": +8.3,  # bid_change - ask_change
                "sentiment": "bullish"
            }
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for orderbook delta: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/orderbook"
            params = {
                "category": "spot",
                "symbol": bybit_symbol,
                "limit": 50
            }
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        result_data = data.get("result", {})
                        bids = result_data.get("b", [])
                        asks = result_data.get("a", [])
                        
                        if not bids or not asks:
                            return None
                        
                        # Calculate current volumes
                        bid_volume = sum(float(b[1]) for b in bids)
                        ask_volume = sum(float(a[1]) for a in asks)
                        
                        # Get previous orderbook data
                        prev_orderbook = self._previous_orderbook.get(symbol)
                        
                        if prev_orderbook:
                            prev_bid_volume = prev_orderbook["bid_volume"]
                            prev_ask_volume = prev_orderbook["ask_volume"]
                            
                            # Calculate percentage change
                            bid_change = ((bid_volume - prev_bid_volume) / prev_bid_volume * 100) if prev_bid_volume > 0 else 0
                            ask_change = ((ask_volume - prev_ask_volume) / prev_ask_volume * 100) if prev_ask_volume > 0 else 0
                            delta = bid_change - ask_change
                            
                            # Determine sentiment
                            if delta > 5:
                                sentiment = "bullish"
                            elif delta < -5:
                                sentiment = "bearish"
                            else:
                                sentiment = "neutral"
                            
                            result = {
                                "bid_change": round(bid_change, 2),
                                "ask_change": round(ask_change, 2),
                                "delta": round(delta, 2),
                                "sentiment": sentiment
                            }
                        else:
                            # First call, no delta yet
                            result = {
                                "bid_change": 0.0,
                                "ask_change": 0.0,
                                "delta": 0.0,
                                "sentiment": "neutral"
                            }
                        
                        # Store current orderbook for next comparison
                        self._previous_orderbook[symbol] = {
                            "bid_volume": bid_volume,
                            "ask_volume": ask_volume,
                            "timestamp": datetime.now()
                        }
                        
                        logger.info(f"Calculated orderbook delta for {symbol}: {result.get('delta', 0):.2f}%")
                        return result
                    else:
                        logger.warning(f"Failed to fetch orderbook delta for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting orderbook delta for {symbol}: {e}")
            return None
    
    async def get_coinglass_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение данных с Coinglass.
        
        Endpoints:
        - Open Interest: https://open-api.coinglass.com/public/v2/open_interest?symbol=BTC
        - Liquidations: https://open-api.coinglass.com/public/v2/liquidation_history?symbol=BTC&time_type=h1
        - Top Traders L/S: https://open-api.coinglass.com/public/v2/long_short?symbol=BTC&time_type=h1
        
        Returns:
            {
                "oi_change_24h": 2.3,  # % изменение Open Interest
                "liquidations_long": 12000000,  # $ ликвидаций лонгов
                "liquidations_short": 8000000,  # $ ликвидаций шортов
                "top_traders_ratio": 1.8,  # Long/Short ratio топ трейдеров
            }
        """
        try:
            # Coinglass uses uppercase symbols without USDT
            cg_symbol = symbol.upper()
            
            result = {}
            
            # Fetch Open Interest
            try:
                oi_url = f"https://open-api.coinglass.com/public/v2/open_interest"
                params = {"symbol": cg_symbol}
                
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession() as session:
                    async with session.get(oi_url, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("success") and data.get("data"):
                                oi_data = data["data"]
                                result["oi_change_24h"] = float(oi_data.get("oiChangePercent", 0))
                                logger.info(f"Fetched Coinglass OI for {symbol}: {result['oi_change_24h']}%")
            except Exception as e:
                logger.warning(f"Could not fetch Coinglass OI for {symbol}: {e}")
            
            # Fetch Liquidations
            try:
                liq_url = f"https://open-api.coinglass.com/public/v2/liquidation_history"
                params = {"symbol": cg_symbol, "time_type": "h1"}
                
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession() as session:
                    async with session.get(liq_url, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("success") and data.get("data"):
                                liq_data = data["data"]
                                # Assuming structure has long/short liquidations
                                result["liquidations_long"] = float(liq_data.get("longLiquidation", 0))
                                result["liquidations_short"] = float(liq_data.get("shortLiquidation", 0))
                                logger.info(f"Fetched Coinglass liquidations for {symbol}")
            except Exception as e:
                logger.warning(f"Could not fetch Coinglass liquidations for {symbol}: {e}")
            
            # Fetch Top Traders L/S Ratio
            try:
                ls_url = f"https://open-api.coinglass.com/public/v2/long_short"
                params = {"symbol": cg_symbol, "time_type": "h1"}
                
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession() as session:
                    async with session.get(ls_url, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("success") and data.get("data"):
                                ls_data = data["data"]
                                # Calculate ratio from percentages
                                long_pct = float(ls_data.get("longPercent", 50))
                                short_pct = float(ls_data.get("shortPercent", 50))
                                if short_pct > 0:
                                    result["top_traders_ratio"] = long_pct / short_pct
                                else:
                                    result["top_traders_ratio"] = 2.0  # Default bullish
                                logger.info(f"Fetched Coinglass top traders for {symbol}: {result['top_traders_ratio']:.2f}")
            except Exception as e:
                logger.warning(f"Could not fetch Coinglass top traders for {symbol}: {e}")
            
            return result if result else None
            
        except Exception as e:
            logger.error(f"Error getting Coinglass data for {symbol}: {e}")
            return None
    
    async def get_crypto_news_sentiment(self, symbol: str) -> Optional[Dict]:
        """
        Получение новостей и сентимента с CryptoPanic.
        
        Endpoint: https://cryptopanic.com/api/v1/posts/?auth_token=FREE&currencies=BTC&filter=hot
        
        Для бесплатного API можно использовать публичный endpoint или парсить.
        
        Returns:
            {
                "news_count": 10,
                "bullish_count": 6,
                "bearish_count": 2,
                "neutral_count": 2,
                "sentiment_score": 0.6,  # (bullish - bearish) / total
                "important_news": ["Bitcoin ETF approved", ...],
            }
        """
        try:
            # Use free public endpoint (no auth required for some endpoints)
            url = "https://cryptopanic.com/api/free/v1/posts/"
            params = {
                "currencies": symbol.upper(),
                "filter": "hot",
                "public": "true"
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])
                        
                        if not results:
                            logger.info(f"No CryptoPanic news found for {symbol}")
                            return None
                        
                        news_count = len(results)
                        bullish_count = 0
                        bearish_count = 0
                        neutral_count = 0
                        important_news = []
                        
                        for post in results[:10]:  # Analyze top 10
                            title = post.get("title", "")
                            votes = post.get("votes", {})
                            
                            # Analyze sentiment from votes
                            positive = votes.get("positive", 0)
                            negative = votes.get("negative", 0)
                            important = votes.get("important", 0)
                            
                            if positive > negative:
                                bullish_count += 1
                            elif negative > positive:
                                bearish_count += 1
                            else:
                                neutral_count += 1
                            
                            if important > 5:
                                important_news.append(title[:50])
                        
                        # Calculate sentiment score
                        total = bullish_count + bearish_count + neutral_count
                        sentiment_score = (bullish_count - bearish_count) / total if total > 0 else 0
                        
                        result = {
                            "news_count": news_count,
                            "bullish_count": bullish_count,
                            "bearish_count": bearish_count,
                            "neutral_count": neutral_count,
                            "sentiment_score": round(sentiment_score, 2),
                            "important_news": important_news[:3]
                        }
                        
                        logger.info(f"Fetched CryptoPanic news for {symbol}: sentiment {sentiment_score:.2f}")
                        return result
                    else:
                        logger.warning(f"Failed to fetch CryptoPanic news for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting CryptoPanic news for {symbol}: {e}")
            return None
    
    async def get_tradingview_rating(self, symbol: str) -> Optional[Dict]:
        """
        Получение технического рейтинга TradingView.
        
        Использовать библиотеку tradingview_ta.
        
        Returns:
            {
                "recommendation": "STRONG_BUY",  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
                "buy_signals": 15,
                "sell_signals": 3,
                "neutral_signals": 8,
                "moving_averages": "BUY",
                "oscillators": "BUY",
            }
        """
        try:
            from tradingview_ta import TA_Handler, Interval
            
            bybit_symbol = self.bybit_mapping.get(symbol, f"{symbol}USDT")
            
            handler = TA_Handler(
                symbol=bybit_symbol,
                exchange="BYBIT",
                screener="crypto",
                interval=Interval.INTERVAL_1_HOUR
            )
            
            analysis = handler.get_analysis()
            
            result = {
                "recommendation": analysis.summary["RECOMMENDATION"],
                "buy_signals": analysis.summary["BUY"],
                "sell_signals": analysis.summary["SELL"],
                "neutral_signals": analysis.summary["NEUTRAL"],
                "moving_averages": analysis.moving_averages["RECOMMENDATION"],
                "oscillators": analysis.oscillators["RECOMMENDATION"],
            }
            
            logger.info(f"Fetched TradingView rating for {symbol}: {result['recommendation']}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting TradingView rating for {symbol}: {e}")
            return None
    
    async def get_whale_alert_transactions(self, symbol: str) -> Optional[Dict]:
        """
        Получение крупных транзакций с Whale Alert.
        
        Бесплатный endpoint (ограниченный) или mock data для демонстрации.
        
        Returns:
            {
                "transactions_1h": 5,
                "to_exchange_usd": 45000000,  # На биржи (продажа)
                "from_exchange_usd": 120000000,  # С бирж (накопление)
                "unknown_usd": 30000000,
                "net_flow": 75000000,  # from_exchange - to_exchange (положительный = бычье)
            }
        """
        try:
            # Note: Whale Alert API requires API key for production use
            # Using mock/simulated data based on our existing whale tracker data
            
            # Get whale data from our tracker
            whale_data = await self.get_whale_data(symbol)
            
            if not whale_data:
                return None
            
            # Simulate Whale Alert style data from our whale tracker
            deposits = whale_data.get("deposits", 0)
            withdrawals = whale_data.get("withdrawals", 0)
            total_volume = whale_data.get("total_volume_usd", 0)
            
            # Estimate flows
            to_exchange_usd = (deposits / (deposits + withdrawals + 0.001)) * total_volume if (deposits + withdrawals) > 0 else 0
            from_exchange_usd = (withdrawals / (deposits + withdrawals + 0.001)) * total_volume if (deposits + withdrawals) > 0 else 0
            unknown_usd = total_volume * 0.1  # Assume 10% unknown
            
            net_flow = from_exchange_usd - to_exchange_usd
            
            result = {
                "transactions_1h": whale_data.get("transaction_count", 0),
                "to_exchange_usd": round(to_exchange_usd, 0),
                "from_exchange_usd": round(from_exchange_usd, 0),
                "unknown_usd": round(unknown_usd, 0),
                "net_flow": round(net_flow, 0)
            }
            
            logger.info(f"Calculated Whale Alert transactions for {symbol}: net_flow ${net_flow:,.0f}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting Whale Alert transactions for {symbol}: {e}")
            return None
    
    async def get_lunarcrush_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение социальных метрик с LunarCrush.
        
        Endpoint: https://lunarcrush.com/api3/coins/{symbol}
        
        Returns:
            {
                "galaxy_score": 72,  # 0-100, общий рейтинг
                "social_volume": 15000,  # упоминания
                "social_volume_change": 15.5,  # % изменение
                "sentiment": 0.65,  # -1 to 1
                "social_dominance": 45.2,  # % от всего крипто
            }
        """
        try:
            # LunarCrush API v3 (free tier available)
            coin_symbol = symbol.lower()
            url = f"https://lunarcrush.com/api3/coins/{coin_symbol}"
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    # Check if request was successful before using mock data
                    if response.status != 200:
                        logger.warning(f"Failed to fetch LunarCrush data for {symbol}: {response.status}")
                        return None
                    
                    # TODO: Parse actual LunarCrush API response structure
                    # Currently using mock data - implement proper parsing when API structure is confirmed
                    # For now, only return data if the API is accessible
                    data = await response.json()
                    
                    # Use mock data based on symbol (to be replaced with actual parsing)
                    if symbol == "BTC":
                        galaxy_score = 75
                        social_volume = 18000
                        social_volume_change = 5.5
                        sentiment = 0.65
                        social_dominance = 45.0
                    elif symbol == "ETH":
                        galaxy_score = 70
                        social_volume = 12000
                        social_volume_change = 3.2
                        sentiment = 0.60
                        social_dominance = 25.0
                    else:
                        return None
                    
                    result = {
                        "galaxy_score": galaxy_score,
                        "social_volume": social_volume,
                        "social_volume_change": social_volume_change,
                        "sentiment": sentiment,
                        "social_dominance": social_dominance
                    }
                    
                    logger.info(f"Fetched LunarCrush data for {symbol}: galaxy_score {galaxy_score}")
                    return result
        except Exception as e:
            logger.error(f"Error getting LunarCrush data for {symbol}: {e}")
            return None
    
    async def calculate_short_term_indicators(self, symbol: str, ohlcv_5m: Optional[List], 
                                             ohlcv_15m: Optional[List]) -> Optional[Dict]:
        """
        Расчёт краткосрочных индикаторов на основе 5м и 15м данных.
        
        Args:
            symbol: BTC или ETH
            ohlcv_5m: Свечи 5 минут
            ohlcv_15m: Свечи 15 минут
        
        Returns:
            Dict: {
                "rsi_5m": 65.5,
                "rsi_15m": 58.2,
                "ema_9_5m": 97500,
                "ema_21_5m": 97200,
                "ema_crossover": "bullish",  # bullish/bearish/neutral
                "price_10min_ago": 97000,
                "current_price": 97500
            }
        """
        try:
            result = {}
            
            # RSI 5m
            if ohlcv_5m and len(ohlcv_5m) >= 14:
                closes_5m = [c["close"] for c in ohlcv_5m]
                rsi_5m = calculate_rsi(closes_5m, period=14)
                if rsi_5m:
                    result["rsi_5m"] = rsi_5m.value
            
            # RSI 15m
            if ohlcv_15m and len(ohlcv_15m) >= 14:
                closes_15m = [c["close"] for c in ohlcv_15m]
                rsi_15m = calculate_rsi(closes_15m, period=14)
                if rsi_15m:
                    result["rsi_15m"] = rsi_15m.value
            
            # EMA crossover on 5m
            if ohlcv_5m and len(ohlcv_5m) >= 21:
                closes_5m = [c["close"] for c in ohlcv_5m]
                
                # Calculate EMA 9 and 21
                closes_array = np.array(closes_5m)
                
                # EMA formula: EMA = price * k + EMA(prev) * (1-k), where k = 2/(N+1)
                ema_9 = closes_array[0]
                k_9 = 2 / (9 + 1)
                for price in closes_array:
                    ema_9 = price * k_9 + ema_9 * (1 - k_9)
                
                ema_21 = closes_array[0]
                k_21 = 2 / (21 + 1)
                for price in closes_array:
                    ema_21 = price * k_21 + ema_21 * (1 - k_21)
                
                result["ema_9_5m"] = round(ema_9, 2)
                result["ema_21_5m"] = round(ema_21, 2)
                
                # Crossover detection with threshold to avoid false signals
                threshold = self.EMA_CROSSOVER_THRESHOLD
                if ema_9 > ema_21 * (1 + threshold):
                    result["ema_crossover"] = "bullish"
                elif ema_9 < ema_21 * (1 - threshold):
                    result["ema_crossover"] = "bearish"
                else:
                    result["ema_crossover"] = "neutral"
            
            # Price 10 minutes ago (index -3 represents 2 candles back = 10 min on 5m chart)
            if ohlcv_5m and len(ohlcv_5m) >= 3:
                result["price_10min_ago"] = ohlcv_5m[-3]["close"]
                result["current_price"] = ohlcv_5m[0]["close"]
            
            logger.info(f"Calculated short-term indicators for {symbol}")
            return result if result else None
            
        except Exception as e:
            logger.error(f"Error calculating short-term indicators for {symbol}: {e}")
            return None
    
    def _calculate_short_term_trend_score(self, short_term_data: Dict) -> float:
        """
        Краткосрочный тренд на основе 5м/15м данных.
        
        Использует:
        - RSI 5м (oversold < 30, overbought > 70)
        - RSI 15м
        - EMA 9/21 crossover на 5м
        - Price momentum (цена сейчас vs 10 мин назад)
        
        Args:
            short_term_data: Краткосрочные индикаторы
        
        Returns: -10 to +10
        """
        if not short_term_data:
            return 0.0
        
        score = 0.0
        
        # RSI 5m score (max ±3)
        rsi_5m = short_term_data.get("rsi_5m")
        if rsi_5m:
            if rsi_5m < 30:
                score += 3  # Oversold = bullish
            elif rsi_5m > 70:
                score -= 3  # Overbought = bearish
            else:
                # Gradient
                score += (50 - rsi_5m) / 20
        
        # RSI 15m score (max ±2)
        rsi_15m = short_term_data.get("rsi_15m")
        if rsi_15m:
            if rsi_15m < 30:
                score += 2
            elif rsi_15m > 70:
                score -= 2
            else:
                score += (50 - rsi_15m) / 30
        
        # EMA crossover score (max ±3)
        ema_crossover = short_term_data.get("ema_crossover")
        if ema_crossover == "bullish":
            score += 3
        elif ema_crossover == "bearish":
            score -= 3
        
        # Price momentum score (max ±2)
        current_price = short_term_data.get("current_price")
        price_10min_ago = short_term_data.get("price_10min_ago")
        if current_price and price_10min_ago:
            price_change_pct = ((current_price - price_10min_ago) / price_10min_ago) * 100
            if price_change_pct > 0.5:
                score += 2
            elif price_change_pct < -0.5:
                score -= 2
            else:
                score += price_change_pct * 4  # Gradient
        
        return max(min(score, 10), -10)
    
    def _calculate_trades_flow_score(self, trades_flow: Optional[Dict]) -> float:
        """
        Score на основе потока сделок.
        
        - flow_ratio > 1.5 = +5 (много покупок)
        - flow_ratio < 0.67 = -5 (много продаж)
        - Градиент между ними
        
        Args:
            trades_flow: Данные о потоке сделок
        
        Returns: -10 to +10
        """
        if not trades_flow:
            return 0.0
        
        flow_ratio = trades_flow.get("flow_ratio", 1.0)
        
        if flow_ratio > self.TRADES_FLOW_BULLISH_THRESHOLD:
            # Много покупок - максимально бычье
            score = 10
        elif flow_ratio < self.TRADES_FLOW_BEARISH_THRESHOLD:
            # Много продаж - максимально медвежье
            score = -10
        else:
            # Градиент между thresholds
            # Normalize to -10 to +10
            # flow_ratio: 0.67 -> -10, 1.0 -> 0, 1.5 -> +10
            if flow_ratio >= 1.0:
                bullish_range = self.TRADES_FLOW_BULLISH_THRESHOLD - 1.0
                score = ((flow_ratio - 1.0) / bullish_range) * 10
            else:
                score = ((flow_ratio - 1.0) / self.TRADES_FLOW_NEUTRAL_DIVISOR) * 10
        
        return max(min(score, 10), -10)
    
    def _calculate_liquidations_score(self, liquidations: Optional[Dict]) -> float:
        """
        Score на основе ликвидаций.
        
        - Много лонг ликвидаций = bearish (цена падает, лонги закрываются)
        - Много шорт ликвидаций = bullish (цена растёт, шорты закрываются)
        
        Args:
            liquidations: Данные о ликвидациях
        
        Returns: -10 to +10
        """
        if not liquidations:
            return 0.0
        
        sentiment = liquidations.get("sentiment", "neutral")
        net_liquidations = liquidations.get("net_liquidations", 0)
        
        if sentiment == "bearish":
            # Много лонг ликвидаций
            score = -8
        elif sentiment == "bullish":
            # Много шорт ликвидаций
            score = 8
        else:
            # Нейтрально
            score = 0
        
        return max(min(score, 10), -10)
    
    def _calculate_orderbook_delta_score(self, orderbook_delta: Optional[Dict]) -> float:
        """
        Score на основе изменения order book.
        
        - Bid wall растёт, Ask wall падает = bullish
        - Bid wall падает, Ask wall растёт = bearish
        
        Args:
            orderbook_delta: Изменение order book
        
        Returns: -10 to +10
        """
        if not orderbook_delta:
            return 0.0
        
        delta = orderbook_delta.get("delta", 0)
        
        # Delta > 10% = strong bullish
        # Delta < -10% = strong bearish
        if delta > 10:
            score = 10
        elif delta < -10:
            score = -10
        else:
            # Gradient
            score = delta
        
        return max(min(score, 10), -10)
    
    def _calculate_price_momentum_score(self, current_price: float, price_10min_ago: float) -> float:
        """
        Score на основе движения цены за 10 минут.
        
        - Рост > 0.5% = bullish
        - Падение > 0.5% = bearish
        
        Args:
            current_price: Текущая цена
            price_10min_ago: Цена 10 минут назад
        
        Returns: -10 to +10
        """
        if not current_price or not price_10min_ago:
            return 0.0
        
        price_change_pct = ((current_price - price_10min_ago) / price_10min_ago) * 100
        
        if price_change_pct > 0.5:
            # Strong bullish
            score = min(price_change_pct * 10, 10)
        elif price_change_pct < -0.5:
            # Strong bearish
            score = max(price_change_pct * 10, -10)
        else:
            # Gradient
            score = price_change_pct * 20
        
        return max(min(score, 10), -10)
    
    def _calculate_oi_change_score(self, oi_change: float, price_change: float) -> float:
        """
        Score на основе изменения Open Interest.
        
        Логика:
        - OI растёт + цена растёт = сильный бычий тренд (+10)
        - OI растёт + цена падает = накопление шортов (-5)
        - OI падает + цена растёт = слабый рост (-3)
        - OI падает + цена падает = капитуляция, возможно дно (+3)
        
        Returns: -10 to +10
        """
        if oi_change > 2:  # OI растёт
            if price_change > 0:
                return 10  # Сильный бычий тренд
            else:
                return -5  # Накопление шортов
        elif oi_change < -2:  # OI падает
            if price_change > 0:
                return -3  # Слабый рост
            else:
                return 3  # Капитуляция, возможно дно
        else:
            # Нейтрально
            return 0
    
    def _calculate_coinglass_liquidations_score(self, liq_long: float, liq_short: float) -> float:
        """
        Score на основе ликвидаций Coinglass (улучшенный).
        
        Логика:
        - Много лонг ликвидаций = цена падала, медвежье (-10)
        - Много шорт ликвидаций = цена росла, бычье (+10)
        - Баланс = нейтрально (0)
        
        Returns: -10 to +10
        """
        total = liq_long + liq_short
        if total == 0:
            return 0
        
        # Calculate ratio
        long_ratio = liq_long / total
        
        if long_ratio > 0.7:
            # Много лонг ликвидаций
            return -10
        elif long_ratio > 0.6:
            return -5
        elif long_ratio < 0.3:
            # Много шорт ликвидаций
            return 10
        elif long_ratio < 0.4:
            return 5
        else:
            # Баланс
            return 0
    
    def _calculate_top_traders_score(self, ratio: float) -> float:
        """
        Score на основе позиций топ трейдеров.
        
        Логика:
        - ratio > 2.0 = топы в лонгах, бычье (+8)
        - ratio > 1.5 = умеренно бычье (+4)
        - ratio < 0.67 = топы в шортах, медвежье (-8)
        - ratio < 0.5 = сильно медвежье (-10)
        
        Returns: -10 to +10
        """
        if ratio > 2.0:
            return 8
        elif ratio > 1.5:
            return 4
        elif ratio < 0.5:
            return -10
        elif ratio < 0.67:
            return -8
        else:
            # Градиент между 0.67 и 1.5
            return (ratio - 1.0) * 5
    
    def _calculate_news_sentiment_score(self, sentiment_data: Dict) -> float:
        """
        Score на основе новостного сентимента.
        
        Логика:
        - sentiment_score > 0.5 = очень бычьи новости (+10)
        - sentiment_score > 0.2 = бычьи новости (+5)
        - sentiment_score < -0.2 = медвежьи новости (-5)
        - sentiment_score < -0.5 = очень медвежьи (-10)
        
        Returns: -10 to +10
        """
        if not sentiment_data:
            return 0
        
        sentiment_score = sentiment_data.get("sentiment_score", 0)
        
        if sentiment_score > 0.5:
            return 10
        elif sentiment_score > 0.2:
            return 5
        elif sentiment_score < -0.5:
            return -10
        elif sentiment_score < -0.2:
            return -5
        else:
            # Градиент
            return sentiment_score * 10
    
    def _calculate_tradingview_score(self, tv_data: Dict) -> float:
        """
        Score на основе TradingView рейтинга.
        
        Логика:
        - STRONG_BUY = +10
        - BUY = +5
        - NEUTRAL = 0
        - SELL = -5
        - STRONG_SELL = -10
        
        Returns: -10 to +10
        """
        if not tv_data:
            return 0
        
        recommendation = tv_data.get("recommendation", "NEUTRAL")
        
        if recommendation == "STRONG_BUY":
            return 10
        elif recommendation == "BUY":
            return 5
        elif recommendation == "SELL":
            return -5
        elif recommendation == "STRONG_SELL":
            return -10
        else:
            return 0
    
    def _calculate_whale_alert_score(self, whale_data: Dict) -> float:
        """
        Score на основе Whale Alert транзакций.
        
        Логика:
        - net_flow > $50M = сильный вывод с бирж, бычье (+10)
        - net_flow > $20M = умеренный вывод (+5)
        - net_flow < -$20M = приток на биржи, медвежье (-5)
        - net_flow < -$50M = сильный приток, очень медвежье (-10)
        
        Returns: -10 to +10
        """
        if not whale_data:
            return 0
        
        net_flow = whale_data.get("net_flow", 0)
        
        if net_flow > 50_000_000:
            return 10
        elif net_flow > 20_000_000:
            return 5
        elif net_flow < -50_000_000:
            return -10
        elif net_flow < -20_000_000:
            return -5
        else:
            # Градиент
            return (net_flow / 10_000_000)
    
    def _calculate_social_score(self, social_data: Dict) -> float:
        """
        Score на основе социальных метрик.
        
        Логика:
        - galaxy_score > 70 + sentiment > 0.5 = очень бычье (+10)
        - galaxy_score > 60 + sentiment > 0.3 = бычье (+5)
        - galaxy_score < 40 + sentiment < -0.3 = медвежье (-5)
        - galaxy_score < 30 + sentiment < -0.5 = очень медвежье (-10)
        
        Returns: -10 to +10
        """
        if not social_data:
            return 0
        
        galaxy_score = social_data.get("galaxy_score", 50)
        sentiment = social_data.get("sentiment", 0)
        
        if galaxy_score > 70 and sentiment > 0.5:
            return 10
        elif galaxy_score > 60 and sentiment > 0.3:
            return 5
        elif galaxy_score < 30 and sentiment < -0.5:
            return -10
        elif galaxy_score < 40 and sentiment < -0.3:
            return -5
        else:
            # Комбинированный градиент
            score = ((galaxy_score - 50) / 10) + (sentiment * 5)
            return max(min(score, 10), -10)
    
    
    def _calculate_whale_score(self, whale_data: Dict, exchange_flows: Optional[Dict] = None) -> float:
        """
        Calculate whale score (-10 to +10).
        
        Args:
            whale_data: Whale transaction data
            exchange_flows: Exchange flow data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Whale transactions score (max ±6)
        total_txs = whale_data["withdrawals"] + whale_data["deposits"]
        if total_txs > 0:
            ratio = (whale_data["withdrawals"] - whale_data["deposits"]) / total_txs
            score += ratio * 6
        
        # Exchange flows score (max ±4)
        if exchange_flows:
            net_flow = exchange_flows.get("net_flow_usd", 0)
            total_flow = exchange_flows.get("inflow_volume_usd", 0) + exchange_flows.get("outflow_volume_usd", 0)
            if total_flow > 0:
                flow_ratio = net_flow / total_flow
                score += flow_ratio * 4
        
        return max(min(score, 10), -10)
    
    def _calculate_trend_score(self, technical_data: Dict) -> float:
        """
        Calculate trend score (-10 to +10).
        Combines RSI, MACD, MA Crossover.
        
        Args:
            technical_data: Technical indicator data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # RSI (max ±4)
        if "rsi" in technical_data:
            rsi_value = technical_data["rsi"]["value"]
            if rsi_value < 30:
                score += 4
            elif rsi_value > 70:
                score -= 4
            else:
                score += (50 - rsi_value) / 20 * 2
        
        # MACD (max ±3)
        if "macd" in technical_data:
            if technical_data["macd"]["signal"] == "bullish":
                score += 3
            elif technical_data["macd"]["signal"] == "bearish":
                score -= 3
        
        # MA Crossover (max ±3)
        if "ma_crossover" in technical_data:
            if technical_data["ma_crossover"]["crossover"] == "golden_cross":
                score += 3
            elif technical_data["ma_crossover"]["crossover"] == "death_cross":
                score -= 3
            elif technical_data["ma_crossover"]["trend"] == "bullish":
                score += 1
            elif technical_data["ma_crossover"]["trend"] == "bearish":
                score -= 1
        
        return max(min(score, 10), -10)
    
    def _calculate_momentum_score(self, technical_data: Dict) -> float:
        """
        Calculate momentum score (-10 to +10).
        Combines Stochastic RSI, MFI, ROC, Williams %R.
        
        Args:
            technical_data: Technical indicator data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Stochastic RSI (max ±3)
        if "stoch_rsi" in technical_data:
            signal = technical_data["stoch_rsi"]["signal"]
            if signal == "oversold":
                score += 3
            elif signal == "overbought":
                score -= 3
            elif signal == "bullish":
                score += 1.5
            elif signal == "bearish":
                score -= 1.5
        
        # MFI (max ±2.5)
        if "mfi" in technical_data:
            signal = technical_data["mfi"]["signal"]
            if signal == "oversold":
                score += 2.5
            elif signal == "overbought":
                score -= 2.5
        
        # ROC (max ±2.5)
        if "roc" in technical_data:
            momentum = technical_data["roc"]["momentum"]
            if momentum == "strong_up":
                score += 2.5
            elif momentum == "up":
                score += 1.5
            elif momentum == "strong_down":
                score -= 2.5
            elif momentum == "down":
                score -= 1.5
        
        # Williams %R (max ±2)
        if "williams_r" in technical_data:
            signal = technical_data["williams_r"]["signal"]
            if signal == "oversold":
                score += 2
            elif signal == "overbought":
                score -= 2
        
        return max(min(score, 10), -10)
    
    def _calculate_volatility_score(self, technical_data: Dict) -> float:
        """
        Calculate volatility score (-10 to +10).
        Combines Bollinger Bands, ATR, Keltner Channels.
        
        Args:
            technical_data: Technical indicator data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Bollinger Bands (max ±4)
        if "bollinger_bands" in technical_data:
            position = technical_data["bollinger_bands"]["position"]
            if position == "below_lower":
                score += 4
            elif position == "above_upper":
                score -= 4
            elif position == "lower_half":
                score += 1
            elif position == "upper_half":
                score -= 1
        
        # ATR (max ±3)
        if "atr" in technical_data:
            volatility = technical_data["atr"]["volatility"]
            if volatility in ["high", "extreme"]:
                score -= 2  # High volatility is risky
        
        # Keltner Channels (max ±3)
        if "keltner_channels" in technical_data:
            position = technical_data["keltner_channels"]["position"]
            if position == "below":
                score += 3
            elif position == "above":
                score -= 3
        
        return max(min(score, 10), -10)
    
    def _calculate_volume_score(self, technical_data: Dict, ohlcv_data: Optional[List] = None) -> float:
        """
        Calculate volume score (-10 to +10).
        Combines OBV, VWAP, Volume SMA.
        
        Args:
            technical_data: Technical indicator data
            ohlcv_data: OHLCV candle data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # OBV (max ±4)
        if "obv" in technical_data:
            trend = technical_data["obv"]["trend"]
            if trend == "rising":
                score += 4
            elif trend == "falling":
                score -= 4
        
        # VWAP (max ±3)
        if "vwap" in technical_data:
            position = technical_data["vwap"]["position"]
            deviation = technical_data["vwap"]["deviation_percent"]
            if position == "above":
                score += min(3, deviation / 2)
            else:
                score -= min(3, abs(deviation) / 2)
        
        # Volume SMA (max ±3)
        if "volume_sma" in technical_data:
            status = technical_data["volume_sma"]["status"]
            if status == "high":
                score += 3
            elif status == "low":
                score -= 2
        
        return max(min(score, 10), -10)
    
    def _calculate_market_score(self, market_data: Dict) -> float:
        """
        Calculate market score (-10 to +10).
        Based on price change and volume.
        
        Args:
            market_data: Market data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Price change (max ±7)
        change_24h = market_data.get("change_24h", 0)
        score += min(max(change_24h * 0.7, -7), 7)
        
        # Volume (max ±3)
        volume_24h = market_data.get("volume_24h", 0)
        if volume_24h > self.HIGH_VOLUME_THRESHOLD:
            score += 3
        elif volume_24h < self.HIGH_VOLUME_THRESHOLD * 0.3:
            score -= 2
        
        return max(min(score, 10), -10)
    
    def _calculate_orderbook_score(self, order_book: Optional[Dict]) -> float:
        """
        Calculate order book score (-10 to +10).
        Based on bid/ask imbalance and spread.
        
        Args:
            order_book: Order book data
            
        Returns:
            Score from -10 to +10
        """
        if not order_book:
            return 0.0
        
        score = 0.0
        
        # Imbalance (max ±7)
        imbalance = order_book.get("imbalance", 0)
        score += imbalance * 7
        
        # Spread (max ±3)
        spread = order_book.get("spread", 0)
        if spread < 0.01:  # Tight spread
            score += 2
        elif spread > 0.05:  # Wide spread
            score -= 3
        
        return max(min(score, 10), -10)
    
    def _calculate_derivatives_score(self, futures_data: Optional[Dict], funding_rate: Optional[Dict]) -> float:
        """
        Calculate derivatives score (-10 to +10).
        Based on Open Interest, Long/Short ratio, Funding Rate.
        
        Args:
            futures_data: Futures data
            funding_rate: Funding rate data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Long/Short Ratio (max ±5)
        if futures_data:
            ls_ratio = futures_data.get("long_short_ratio", 1.0)
            if ls_ratio > 1.5:
                score += 4
            elif ls_ratio > 1.2:
                score += 2
            elif ls_ratio < 0.7:
                score -= 4
            elif ls_ratio < 0.9:
                score -= 2
        
        # Funding Rate (max ±5)
        if funding_rate:
            rate_percent = funding_rate.get("rate_percent", 0)
            if rate_percent < -0.01:
                score += 5
            elif rate_percent > 0.05:
                score -= 5
            else:
                # Gradient
                if rate_percent < 0.02:
                    score += (0.02 - rate_percent) / 0.03 * 3
                else:
                    score -= (rate_percent - 0.02) / 0.03 * 3
        
        return max(min(score, 10), -10)
    
    def _calculate_onchain_score(self, onchain_data: Optional[Dict]) -> float:
        """
        Calculate on-chain score (-10 to +10).
        Based on mempool and hashrate.
        
        Args:
            onchain_data: On-chain data
            
        Returns:
            Score from -10 to +10
        """
        if not onchain_data:
            return 0.0
        
        score = 0.0
        
        # Mempool status (max ±5)
        mempool_status = onchain_data.get("mempool_status", "unknown")
        if mempool_status == "low":
            score += 3  # Low congestion = bullish
        elif mempool_status == "congested":
            score -= 5  # High congestion = bearish
        
        # Hashrate (max ±5)
        # Increasing hashrate is bullish for BTC
        # This would require historical data, so we'll skip for now
        
        return max(min(score, 10), -10)
    
    def _calculate_sentiment_score(self, fear_greed: Optional[Dict]) -> float:
        """
        Calculate sentiment score (-10 to +10).
        Based on Fear & Greed Index.
        
        Args:
            fear_greed: Fear & Greed data
            
        Returns:
            Score from -10 to +10
        """
        if not fear_greed:
            return 0.0
        
        fg_value = fear_greed.get("value", 50)
        
        # Extreme Fear = Buy, Extreme Greed = Sell
        if fg_value < 25:
            return 10
        elif fg_value > 75:
            return -10
        else:
            # Gradient
            return (50 - fg_value) / 5
    
    def count_consensus(self, scores: Dict) -> Dict:
        """
        Подсчёт консенсуса факторов.
        
        Args:
            scores: Dictionary containing all factor scores
        
        Returns:
            Dict: {
                "bullish_count": 7,
                "bearish_count": 2,
                "neutral_count": 1,
                "consensus": "bullish"
            }
        """
        bullish = 0
        bearish = 0
        neutral = 0
        
        for key, value in scores.items():
            if key.endswith("_score"):
                if value > 1:
                    bullish += 1
                elif value < -1:
                    bearish += 1
                else:
                    neutral += 1
        
        if bullish > bearish:
            consensus = "bullish"
        elif bearish > bullish:
            consensus = "bearish"
        else:
            consensus = "neutral"
        
        return {
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
            "consensus": consensus
        }
    
    def calculate_probability(self, 
        total_score: float,
        data_sources_count: int,
        consensus_count: int,
        total_factors: int = 10
    ) -> Dict:
        """
        Расчёт вероятности исполнения сигнала.
        
        Args:
            total_score: Итоговый score (-100 to +100)
            data_sources_count: Сколько источников данных доступно
            consensus_count: Сколько факторов указывают в одном направлении
            total_factors: Всего факторов (10)
        
        Returns:
            Dict: {
                "probability": 72,  # Вероятность в %
                "direction": "up",  # up/down
                "confidence": "high",  # high/medium/low
                "data_quality": 0.8  # Качество данных (0-1)
            }
        
        Формула:
        1. Base probability = 50% (нейтральный рынок)
        2. Score adjustment = total_score * 0.4 (макс ±40%)
        3. Data quality bonus = (sources/10) * 5% (макс +5%)
        4. Consensus bonus = (consensus/10) * 5% (макс +5%)
        
        Max probability = 50 + 40 + 5 + 5 = 100%
        Min probability = 50 - 40 = 10%
        """
        # Base probability
        base = 50.0
        
        # Score adjustment (±40%)
        score_adj = (total_score / 100) * 40
        
        # Data quality (0-5%)
        data_quality = data_sources_count / 10
        data_bonus = data_quality * 5
        
        # Consensus bonus (0-5%)
        consensus_ratio = consensus_count / total_factors
        consensus_bonus = consensus_ratio * 5
        
        # Direction and probability calculation
        if total_score > 0:
            direction = "up"
            # For bullish: higher score = higher probability of going up
            probability = base + abs(score_adj) + data_bonus + consensus_bonus
        else:
            direction = "down"
            # For bearish: more negative score = higher probability of going down
            probability = base + abs(score_adj) + data_bonus + consensus_bonus
        
        # Clamp to 20-95% (never 100% certain)
        probability = max(20, min(95, probability))
        
        # Confidence level
        if probability >= 75 or probability <= 25:
            confidence = "high"
        elif probability >= 60 or probability <= 40:
            confidence = "medium"
        else:
            confidence = "low"
        
        return {
            "probability": round(probability),
            "direction": direction,
            "confidence": confidence,
            "data_quality": round(data_quality, 2)
        }
    
    def calculate_signal(self, whale_data: Dict, market_data: Dict, technical_data: Optional[Dict] = None, 
                        fear_greed: Optional[Dict] = None, funding_rate: Optional[Dict] = None,
                        order_book: Optional[Dict] = None, trades: Optional[Dict] = None,
                        futures_data: Optional[Dict] = None, onchain_data: Optional[Dict] = None,
                        exchange_flows: Optional[Dict] = None, ohlcv_data: Optional[List] = None,
                        short_term_data: Optional[Dict] = None, trades_flow: Optional[Dict] = None,
                        liquidations: Optional[Dict] = None, orderbook_delta: Optional[Dict] = None,
                        # New data sources
                        coinglass_data: Optional[Dict] = None,
                        news_sentiment: Optional[Dict] = None,
                        tradingview_rating: Optional[Dict] = None,
                        whale_alert: Optional[Dict] = None,
                        social_data: Optional[Dict] = None) -> Dict:
        """
        22-факторная система расчёта сигнала.
        
        Веса факторов (100% total):
        Долгосрочные (35%):
        - Whale Score (4%): Whale transactions + Exchange flows
        - Trend Score (5%): RSI + MACD + MA Crossover
        - Momentum Score (4%): Stoch RSI + MFI + ROC + Williams %R
        - Volatility Score (4%): Bollinger Bands + ATR + Keltner
        - Volume Score (4%): OBV + VWAP + Volume SMA
        - Market Score (4%): Price change + Volume
        - Order Book Score (4%): Bid/Ask imbalance + Spread
        - Derivatives Score (3%): OI + Long/Short + Funding
        - On-Chain Score (2%): Mempool + Hashrate
        - Sentiment Score (1%): Fear & Greed Index
        
        Краткосрочные (35%):
        - Short Trend Score (8%): RSI 5м/15м, EMA crossover
        - Trades Flow Score (7%): Buy/Sell flow ratio
        - Liquidations Score (6%): Long/Short liquidations
        - Orderbook Delta Score (7%): Bid/Ask wall changes
        - Price Momentum Score (7%): 10-min price movement
        
        Новые источники (30%):
        - Coinglass OI Score (5%): Open Interest change
        - Top Traders Score (5%): Top traders L/S ratio
        - News Sentiment Score (5%): CryptoPanic news sentiment
        - TradingView Score (6%): TradingView technical rating
        - Whale Alert Score (5%): Large transactions net flow
        - Social Score (4%): LunarCrush social metrics
        
        Each factor gives -10 to +10 points.
        Total score: -100 to +100 (weighted sum).
        Signal strength normalized to 0-100%.
        
        Args:
            whale_data: Whale transaction data
            market_data: Market data
            technical_data: Technical indicators (optional)
            fear_greed: Fear & Greed Index (optional)
            funding_rate: Funding Rate (optional)
            order_book: Order book analysis (optional)
            trades: Recent trades analysis (optional)
            futures_data: Futures data (optional)
            onchain_data: On-chain data (optional)
            exchange_flows: Exchange flows (optional)
            short_term_data: Short-term indicators (optional)
            trades_flow: Trades flow analysis (optional)
            liquidations: Liquidations data (optional)
            orderbook_delta: Orderbook delta analysis (optional)
            coinglass_data: Coinglass OI, liquidations, top traders (optional)
            news_sentiment: CryptoPanic news sentiment (optional)
            tradingview_rating: TradingView technical rating (optional)
            whale_alert: Whale Alert large transactions (optional)
            social_data: LunarCrush social metrics (optional)
            
        Returns:
            Dict with analysis results
        """
        # Calculate 10 long-term factor scores
        whale_score = self._calculate_whale_score(whale_data, exchange_flows)
        
        trend_score = 0.0
        momentum_score = 0.0
        volatility_score = 0.0
        volume_score = 0.0
        if technical_data:
            trend_score = self._calculate_trend_score(technical_data)
            momentum_score = self._calculate_momentum_score(technical_data)
            volatility_score = self._calculate_volatility_score(technical_data)
            volume_score = self._calculate_volume_score(technical_data, ohlcv_data)
        
        market_score = self._calculate_market_score(market_data)
        orderbook_score = self._calculate_orderbook_score(order_book)
        derivatives_score = self._calculate_derivatives_score(futures_data, funding_rate)
        onchain_score = self._calculate_onchain_score(onchain_data)
        sentiment_score = self._calculate_sentiment_score(fear_greed)
        
        # Calculate 5 short-term factor scores
        short_trend_score = self._calculate_short_term_trend_score(short_term_data)
        trades_flow_score = self._calculate_trades_flow_score(trades_flow)
        liquidations_score = self._calculate_liquidations_score(liquidations)
        orderbook_delta_score = self._calculate_orderbook_delta_score(orderbook_delta)
        
        # Price momentum from short_term_data
        price_momentum_score = 0.0
        if short_term_data:
            current_price = short_term_data.get("current_price")
            price_10min_ago = short_term_data.get("price_10min_ago")
            if current_price and price_10min_ago:
                price_momentum_score = self._calculate_price_momentum_score(current_price, price_10min_ago)
        
        # Calculate 7 new data source scores
        coinglass_oi_score = 0.0
        coinglass_top_traders_score = 0.0
        if coinglass_data:
            oi_change = coinglass_data.get("oi_change_24h", 0)
            price_change = market_data.get("change_24h", 0)
            coinglass_oi_score = self._calculate_oi_change_score(oi_change, price_change)
            
            # Note: Coinglass liquidations are available but not used separately
            # as we already have liquidations_score from Bybit real-time data
            # which is more suitable for short-term analysis
            
            ratio = coinglass_data.get("top_traders_ratio", 1.0)
            coinglass_top_traders_score = self._calculate_top_traders_score(ratio)
        
        news_sentiment_score = self._calculate_news_sentiment_score(news_sentiment)
        tradingview_score = self._calculate_tradingview_score(tradingview_rating)
        whale_alert_score = self._calculate_whale_alert_score(whale_alert)
        social_score = self._calculate_social_score(social_data)
        
        # Calculate weighted total score (22 factors)
        total_score = (
            # Long-term (35%)
            whale_score * self.WHALE_WEIGHT +
            trend_score * self.TREND_WEIGHT +
            momentum_score * self.MOMENTUM_WEIGHT +
            volatility_score * self.VOLATILITY_WEIGHT +
            volume_score * self.VOLUME_WEIGHT +
            market_score * self.MARKET_WEIGHT +
            orderbook_score * self.ORDERBOOK_WEIGHT +
            derivatives_score * self.DERIVATIVES_WEIGHT +
            onchain_score * self.ONCHAIN_WEIGHT +
            sentiment_score * self.SENTIMENT_WEIGHT +
            # Short-term (35%)
            short_trend_score * self.SHORT_TREND_WEIGHT +
            trades_flow_score * self.TRADES_FLOW_WEIGHT +
            liquidations_score * self.LIQUIDATIONS_WEIGHT +
            orderbook_delta_score * self.ORDERBOOK_DELTA_WEIGHT +
            price_momentum_score * self.PRICE_MOMENTUM_WEIGHT +
            # New sources (30%)
            coinglass_oi_score * self.COINGLASS_OI_WEIGHT +
            coinglass_top_traders_score * self.COINGLASS_TOP_TRADERS_WEIGHT +
            news_sentiment_score * self.NEWS_SENTIMENT_WEIGHT +
            tradingview_score * self.TRADINGVIEW_WEIGHT +
            whale_alert_score * self.WHALE_ALERT_WEIGHT +
            social_score * self.SOCIAL_WEIGHT
        ) * self.SCORE_SCALE_FACTOR  # Scale to -100 to +100
        
        # Count consensus (22 factors)
        all_scores = {
            # Long-term
            "whale_score": whale_score,
            "trend_score": trend_score,
            "momentum_score": momentum_score,
            "volatility_score": volatility_score,
            "volume_score": volume_score,
            "market_score": market_score,
            "orderbook_score": orderbook_score,
            "derivatives_score": derivatives_score,
            "onchain_score": onchain_score,
            "sentiment_score": sentiment_score,
            # Short-term
            "short_trend_score": short_trend_score,
            "trades_flow_score": trades_flow_score,
            "liquidations_score": liquidations_score,
            "orderbook_delta_score": orderbook_delta_score,
            "price_momentum_score": price_momentum_score,
            # New sources
            "coinglass_oi_score": coinglass_oi_score,
            "coinglass_top_traders_score": coinglass_top_traders_score,
            "news_sentiment_score": news_sentiment_score,
            "tradingview_score": tradingview_score,
            "whale_alert_score": whale_alert_score,
            "social_score": social_score,
        }
        consensus_data = self.count_consensus(all_scores)
        
        # Count available data sources (22 total)
        data_sources_available = sum([
            # Long-term
            whale_data is not None and whale_data.get("transaction_count", 0) > 0,
            market_data is not None,
            technical_data is not None,
            fear_greed is not None,
            funding_rate is not None,
            order_book is not None,
            trades is not None,
            futures_data is not None,
            onchain_data is not None,
            exchange_flows is not None,
            # Short-term
            short_term_data is not None,
            trades_flow is not None,
            liquidations is not None,
            orderbook_delta is not None,
            short_term_data is not None and short_term_data.get("current_price") is not None,
            # New sources
            coinglass_data is not None,
            news_sentiment is not None,
            tradingview_rating is not None,
            whale_alert is not None,
            social_data is not None,
        ])
        
        # Calculate probability (22 factors)
        probability_data = self.calculate_probability(
            total_score=total_score,
            data_sources_count=data_sources_available,
            consensus_count=consensus_data["bullish_count"] if total_score > 0 else consensus_data["bearish_count"],
            total_factors=22
        )
        
        # Determine direction and strength
        if total_score > 20:
            direction = "📈 ВВЕРХ"
            strength = "сильный"
            confidence = "Высокая"
        elif total_score > 10:
            direction = "📈 Вероятно вверх"
            strength = "средний"
            confidence = "Средняя"
        elif total_score < -20:
            direction = "📉 ВНИЗ"
            strength = "сильный"
            confidence = "Высокая"
        elif total_score < -10:
            direction = "📉 Вероятно вниз"
            strength = "средний"
            confidence = "Средняя"
        else:
            direction = "➡️ Боковик"
            strength = "слабый"
            confidence = "Низкая"
        
        # Normalize strength to 0-100%
        strength_percent = min(max((total_score + 100) / 200 * 100, 0), 100)
        
        return {
            "direction": direction,
            "strength": strength,
            "strength_percent": round(strength_percent),
            "confidence": confidence,
            "total_score": round(total_score, 2),
            # Long-term scores
            "whale_score": round(whale_score, 2),
            "trend_score": round(trend_score, 2),
            "momentum_score": round(momentum_score, 2),
            "volatility_score": round(volatility_score, 2),
            "volume_score": round(volume_score, 2),
            "market_score": round(market_score, 2),
            "orderbook_score": round(orderbook_score, 2),
            "derivatives_score": round(derivatives_score, 2),
            "onchain_score": round(onchain_score, 2),
            "sentiment_score": round(sentiment_score, 2),
            # Short-term scores
            "short_trend_score": round(short_trend_score, 2),
            "trades_flow_score": round(trades_flow_score, 2),
            "liquidations_score": round(liquidations_score, 2),
            "orderbook_delta_score": round(orderbook_delta_score, 2),
            "price_momentum_score": round(price_momentum_score, 2),
            # New source scores
            "coinglass_oi_score": round(coinglass_oi_score, 2),
            "coinglass_top_traders_score": round(coinglass_top_traders_score, 2),
            "news_sentiment_score": round(news_sentiment_score, 2),
            "tradingview_score": round(tradingview_score, 2),
            "whale_alert_score": round(whale_alert_score, 2),
            "social_score": round(social_score, 2),
            # Add probability data
            "probability": probability_data["probability"],
            "probability_direction": probability_data["direction"],
            "probability_confidence": probability_data["confidence"],
            "data_quality": probability_data["data_quality"],
            # Add consensus data
            "bullish_count": consensus_data["bullish_count"],
            "bearish_count": consensus_data["bearish_count"],
            "neutral_count": consensus_data["neutral_count"],
            "consensus": consensus_data["consensus"],
            "data_sources_count": data_sources_available,
        }
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Экранирует специальные символы Markdown для безопасного отображения в Telegram.
        
        Args:
            text: Текст для экранирования
            
        Returns:
            Экранированный текст
            
        Note:
            Uses simple string.replace() in a loop for readability and maintainability.
            Performance is acceptable since we're dealing with short strings (news titles,
            status messages, etc.) typically under 200 characters. For larger texts,
            str.translate() with a translation table would be more efficient.
        """
        if not text or not isinstance(text, str):
            return text
        
        # Список специальных символов Markdown, которые нужно экранировать
        # Based on Telegram's MarkdownV2 spec: https://core.telegram.org/bots/api#markdownv2-style
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    def format_signal_message(
        self, 
        symbol: str, 
        signal_data: Dict,
        whale_data: Dict,
        market_data: Dict,
        technical_data: Optional[Dict] = None,
        fear_greed: Optional[Dict] = None,
        funding_rate: Optional[Dict] = None,
        order_book: Optional[Dict] = None,
        futures_data: Optional[Dict] = None,
        onchain_data: Optional[Dict] = None,
        exchange_flows: Optional[Dict] = None,
        # Short-term data
        short_term_data: Optional[Dict] = None,
        trades_flow: Optional[Dict] = None,
        liquidations: Optional[Dict] = None,
        orderbook_delta: Optional[Dict] = None,
        # New data sources
        coinglass_data: Optional[Dict] = None,
        news_sentiment: Optional[Dict] = None,
        tradingview_rating: Optional[Dict] = None,
        whale_alert: Optional[Dict] = None,
        social_data: Optional[Dict] = None
    ) -> str:
        """
        Форматирование сообщения с AI сигналом (22-факторная система).
        
        Args:
            symbol: Символ монеты
            signal_data: Результаты анализа сигнала
            whale_data: Данные о китах
            market_data: Рыночные данные
            technical_data: Технические индикаторы (опционально)
            fear_greed: Fear & Greed Index (опционально)
            funding_rate: Funding Rate (опционально)
            order_book: Order book data (опционально)
            futures_data: Futures data (опционально)
            onchain_data: On-chain data (опционально)
            exchange_flows: Exchange flows (опционально)
            short_term_data: Short-term indicators (опционально)
            trades_flow: Trades flow analysis (опционально)
            liquidations: Liquidations data (опционально)
            orderbook_delta: Orderbook delta (опционально)
            
        Returns:
            Форматированное сообщение для Telegram
        """
        # Форматирование объёмов
        def format_volume(volume: float) -> str:
            if volume >= 1_000_000_000:
                return f"${volume / 1_000_000_000:.1f}B"
            elif volume >= 1_000_000:
                return f"${volume / 1_000_000:.1f}M"
            elif volume >= 1_000:
                return f"${volume / 1_000:.1f}K"
            return f"${volume:.0f}"
        
        # Форматирование цены
        def format_price(price: float) -> str:
            if price >= 1000:
                return f"${price:,.0f}"
            elif price >= 1:
                return f"${price:,.2f}"
            else:
                return f"${price:.6f}"
        
        # Эмодзи настроения китов
        sentiment_emoji = {
            "bullish": "🟢",
            "bearish": "🔴",
            "neutral": "🟡"
        }
        
        sentiment = whale_data.get("sentiment", "neutral")
        sentiment_text = {
            "bullish": "Бычье",
            "bearish": "Медвежье",
            "neutral": "Нейтральное"
        }
        
        # Формируем сообщение
        text = f"🤖 *AI СИГНАЛ: {symbol}*\n\n"
        
        # Determine direction emoji
        direction_emoji = "📈" if signal_data['probability_direction'] == "up" else "📉"
        direction_text = "ВВЕРХ" if signal_data['probability_direction'] == "up" else "ВНИЗ"
        
        text += f"⏰ Прогноз на 1 час: {direction_emoji} {direction_text}\n"
        text += f"🎯 Вероятность: {signal_data['probability']}%\n"
        
        # Map confidence
        confidence_map = {
            "high": "Высокая",
            "medium": "Средняя",
            "low": "Низкая"
        }
        confidence_text = confidence_map.get(signal_data['probability_confidence'], signal_data['probability_confidence'])
        text += f"📊 Уверенность: {confidence_text}\n"
        
        # Add consensus information
        consensus_count = signal_data.get('bullish_count', 0) if signal_data['probability_direction'] == "up" else signal_data.get('bearish_count', 0)
        consensus_text = "бычьи" if signal_data['probability_direction'] == "up" else "медвежьи"
        text += f"✅ Консенсус: {consensus_count}/22 факторов {consensus_text}\n"
        
        # Fix data quality calculation
        data_sources_count = signal_data.get('data_sources_count', 0)
        data_quality = min(100, int((data_sources_count / 22) * 100))
        text += f"📡 Данные: {data_sources_count}/22 источников\n"
        text += f"💎 Качество данных: {data_quality}%\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Анализ китов
        text += "🐋 *Анализ китов (1ч):*\n"
        text += f"• Транзакций: {whale_data['transaction_count']} | Объём: {format_volume(whale_data['total_volume_usd'])}\n"
        
        deposits_emoji = "⬇️" if whale_data['deposits'] > whale_data['withdrawals'] else ""
        withdrawals_emoji = "⬆️" if whale_data['withdrawals'] > whale_data['deposits'] else ""
        
        text += f"• Депозиты: {whale_data['deposits']} {deposits_emoji} | Выводы: {whale_data['withdrawals']} {withdrawals_emoji}\n"
        
        whale_score = signal_data.get('whale_score', 0)
        whale_score_sign = "+" if whale_score >= 0 else ""
        text += f"• Настроение: {sentiment_emoji.get(sentiment, '🟡')} {sentiment_text.get(sentiment, 'Нейтральное')} ({whale_score_sign}{whale_score:.0f} очков)\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Технический анализ
        if technical_data:
            text += "📈 *Технический анализ:*\n\n"
            
            # RSI
            if "rsi" in technical_data:
                rsi_value = technical_data["rsi"]["value"]
                rsi_signal = technical_data["rsi"]["signal"]
                
                if rsi_signal == "oversold":
                    rsi_zone = "перепроданность"
                    rsi_emoji = "⬇️"
                    rsi_action = "Покупать"
                elif rsi_signal == "overbought":
                    rsi_zone = "перекупленность"
                    rsi_emoji = "⬆️"
                    rsi_action = "Продавать"
                else:
                    rsi_zone = "нормальная"
                    rsi_emoji = "➡️"
                    rsi_action = "Держать"
                
                text += f"RSI (14): {rsi_value:.1f} — "
                if rsi_signal == "neutral":
                    text += "Нейтрально\n"
                else:
                    text += f"{rsi_zone.capitalize()}\n"
                text += f"├─ Зона: 30-70 ({rsi_zone})\n"
                text += f"└─ Сигнал: {rsi_emoji} {rsi_action}\n\n"
            
            # MACD
            if "macd" in technical_data:
                macd = technical_data["macd"]
                macd_signal = macd["signal"]
                
                if macd_signal == "bullish":
                    macd_text = "Бычий ✅"
                elif macd_signal == "bearish":
                    macd_text = "Медвежий ❌"
                else:
                    macd_text = "Нейтральный ➡️"
                
                text += f"MACD: {macd_text}\n"
                text += f"├─ Линия: {macd['macd_line']:.1f}\n"
                text += f"├─ Сигнал: {macd['signal_line']:.1f}\n"
                text += f"└─ Гистограмма: {macd['histogram']:+.1f}\n\n"
            
            # Bollinger Bands
            if "bollinger_bands" in technical_data:
                bb = technical_data["bollinger_bands"]
                bb_position = bb["position"]
                
                if bb_position == "above_upper":
                    position_text = "Выше верхней полосы"
                elif bb_position == "below_lower":
                    position_text = "Ниже нижней полосы"
                elif bb_position == "upper_half":
                    position_text = "Верхняя половина"
                else:
                    position_text = "Нижняя половина"
                
                bandwidth = bb["bandwidth"]
                if bandwidth < 3:
                    vol_text = "низкая волатильность"
                elif bandwidth > 6:
                    vol_text = "высокая волатильность"
                else:
                    vol_text = "средняя волатильность"
                
                text += "Bollinger Bands:\n"
                text += f"├─ Позиция: {position_text}\n"
                text += f"├─ Ширина: {bandwidth:.1f}% ({vol_text})\n"
                text += f"└─ %B: {bb['percent_b']:.2f}\n\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Fear & Greed Index
        if fear_greed:
            fg_value = fear_greed["value"]
            fg_class = self.escape_markdown(str(fear_greed["classification"]))
            text += f"😱 *Fear & Greed Index:* {fg_value} — {fg_class}\n"
        
        # Funding Rate
        if funding_rate:
            rate_percent = funding_rate["rate_percent"]
            if rate_percent < -0.01:
                fr_text = "Бычье"
            elif rate_percent > 0.05:
                fr_text = "Медвежье"
            else:
                fr_text = "Нейтрально"
            text += f"📊 *Funding Rate:* {rate_percent:+.3f}% — {fr_text}\n"
        
        if fear_greed or funding_rate:
            text += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Рыночные данные
        text += "📊 *Рыночные данные:*\n"
        text += f"• Цена: {format_price(market_data['price_usd'])}\n"
        text += f"• 24ч: {market_data['change_24h']:+.1f}%\n"
        text += f"• Объём 24ч: {format_volume(market_data['volume_24h'])}\n"
        
        # Add order book if available
        if order_book:
            text += f"• Order Book: Bid/Ask {order_book.get('imbalance', 0):+.2%}\n"
        
        # Add exchange flows if available
        if exchange_flows:
            flow_trend = exchange_flows.get('flow_trend', 'neutral')
            net_flow = exchange_flows.get('net_flow_usd', 0)
            if flow_trend == "outflow":
                text += f"• Потоки: ⬆️ Выводы {format_volume(abs(net_flow))}\n"
            elif flow_trend == "inflow":
                text += f"• Потоки: ⬇️ Депозиты {format_volume(abs(net_flow))}\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Derivatives & On-Chain (if available)
        has_extra_data = futures_data or onchain_data
        if has_extra_data:
            text += "📈 *Дополнительные данные:*\n"
            
            if futures_data:
                ls_ratio = futures_data.get("long_short_ratio", 1.0)
                if ls_ratio > 1.2:
                    ls_text = f"🟢 Лонгисты {ls_ratio:.2f}"
                elif ls_ratio < 0.8:
                    ls_text = f"🔴 Шортисты {1/ls_ratio:.2f}"
                else:
                    ls_text = f"🟡 Нейтрально {ls_ratio:.2f}"
                text += f"• L/S Ratio: {ls_text}\n"
            
            if onchain_data and symbol == "BTC":
                mempool_status = self.escape_markdown(str(onchain_data.get("mempool_status", "unknown")))
                mempool_size = onchain_data.get("mempool_size", 0)
                text += f"• Mempool: {mempool_status.capitalize()} ({mempool_size:,} tx)\n"
            
            text += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Краткосрочный анализ (5-15м) - NEW SECTION
        has_short_term = short_term_data or trades_flow or liquidations or orderbook_delta
        if has_short_term:
            text += "⚡ *Краткосрочный анализ (5-15м):*\n\n"
            
            # Short-term indicators
            if short_term_data:
                text += "📊 *Индикаторы:*\n"
                
                # RSI 5m
                rsi_5m = short_term_data.get("rsi_5m")
                if rsi_5m:
                    if rsi_5m < 30:
                        rsi_5m_status = "⬇️ Перепродан"
                    elif rsi_5m > 70:
                        rsi_5m_status = "⬆️ Перекуплен"
                    else:
                        rsi_5m_status = "➡️ Нейтрально"
                    text += f"├─ RSI 5м: {rsi_5m:.1f} — {rsi_5m_status}\n"
                
                # RSI 15m
                rsi_15m = short_term_data.get("rsi_15m")
                if rsi_15m:
                    if rsi_15m < 30:
                        rsi_15m_status = "⬇️ Перепродан"
                    elif rsi_15m > 70:
                        rsi_15m_status = "⬆️ Перекуплен"
                    else:
                        rsi_15m_status = "➡️ Нейтрально"
                    text += f"├─ RSI 15м: {rsi_15m:.1f} — {rsi_15m_status}\n"
                
                # EMA Crossover
                ema_crossover = short_term_data.get("ema_crossover")
                if ema_crossover:
                    if ema_crossover == "bullish":
                        ema_text = "🟢 Бычий"
                    elif ema_crossover == "bearish":
                        ema_text = "🔴 Медвежий"
                    else:
                        ema_text = "🟡 Нейтральный"
                    text += f"└─ EMA 9/21: {ema_text}\n\n"
                else:
                    text += "\n"
            
            # Trades Flow
            if trades_flow:
                flow_ratio = trades_flow.get("flow_ratio", 1.0)
                sentiment = trades_flow.get("sentiment", "neutral")
                buy_count = trades_flow.get("buy_count", 0)
                sell_count = trades_flow.get("sell_count", 0)
                
                if sentiment == "bullish":
                    flow_emoji = "🟢"
                    flow_text = "Бычий"
                elif sentiment == "bearish":
                    flow_emoji = "🔴"
                    flow_text = "Медвежий"
                else:
                    flow_emoji = "🟡"
                    flow_text = "Нейтральный"
                
                text += f"💱 *Поток сделок (10 мин):*\n"
                text += f"├─ Покупки/Продажи: {buy_count}/{sell_count}\n"
                text += f"├─ Соотношение: {flow_ratio:.2f}\n"
                text += f"└─ Настроение: {flow_emoji} {flow_text}\n\n"
            
            # Liquidations
            if liquidations:
                liq_sentiment = liquidations.get("sentiment", "neutral")
                long_liq = liquidations.get("long_liquidations", 0)
                short_liq = liquidations.get("short_liquidations", 0)
                
                if liq_sentiment == "bullish":
                    liq_emoji = "🟢"
                    liq_text = "Бычье (шорты закрыты)"
                elif liq_sentiment == "bearish":
                    liq_emoji = "🔴"
                    liq_text = "Медвежье (лонги закрыты)"
                else:
                    liq_emoji = "🟡"
                    liq_text = "Нейтрально"
                
                text += f"⚠️ *Ликвидации:*\n"
                text += f"└─ Настроение: {liq_emoji} {liq_text}\n\n"
            
            # Orderbook Delta
            if orderbook_delta:
                delta = orderbook_delta.get("delta", 0)
                ob_sentiment = orderbook_delta.get("sentiment", "neutral")
                
                if ob_sentiment == "bullish":
                    ob_emoji = "🟢"
                    ob_text = "Bid растёт"
                elif ob_sentiment == "bearish":
                    ob_emoji = "🔴"
                    ob_text = "Ask растёт"
                else:
                    ob_emoji = "🟡"
                    ob_text = "Стабильно"
                
                text += f"📖 *Orderbook:*\n"
                text += f"└─ Изменение: {delta:+.1f}% ({ob_emoji} {ob_text})\n\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # New data sources section
        has_new_sources = coinglass_data or news_sentiment or tradingview_rating or whale_alert or social_data
        if has_new_sources:
            text += "🆕 *ДОПОЛНИТЕЛЬНЫЕ ДАННЫЕ:*\n\n"
            
            # Coinglass
            if coinglass_data:
                text += "📊 *Coinglass:*\n"
                oi_change = coinglass_data.get("oi_change_24h", 0)
                text += f"├─ Open Interest: {oi_change:+.1f}% (24ч)\n"
                
                liq_long = coinglass_data.get("liquidations_long", 0)
                liq_short = coinglass_data.get("liquidations_short", 0)
                if liq_long > 0 or liq_short > 0:
                    text += f"├─ Ликвидации: ${liq_long/1e6:.1f}M long / ${liq_short/1e6:.1f}M short\n"
                
                ratio = coinglass_data.get("top_traders_ratio", 0)
                if ratio > 0:
                    text += f"└─ Top Traders L/S: {ratio:.2f}\n\n"
                else:
                    text += "\n"
            
            # News sentiment
            if news_sentiment:
                text += "📰 *Новости:*\n"
                sentiment_score = news_sentiment.get("sentiment_score", 0)
                bullish = news_sentiment.get("bullish_count", 0)
                bearish = news_sentiment.get("bearish_count", 0)
                total_news = news_sentiment.get("news_count", 0)
                
                if sentiment_score > 0.2:
                    sentiment_emoji = "🟢"
                    sentiment_text = "Бычий"
                elif sentiment_score < -0.2:
                    sentiment_emoji = "🔴"
                    sentiment_text = "Медвежий"
                else:
                    sentiment_emoji = "🟡"
                    sentiment_text = "Нейтральный"
                
                text += f"├─ Сентимент: {sentiment_emoji} {sentiment_text} ({bullish}/{total_news} позитивных)\n"
                
                important = news_sentiment.get("important_news", [])
                if important:
                    # Экранируем новости от внешних API для безопасного отображения
                    escaped_news = self.escape_markdown(str(important[0]))
                    text += f"└─ Важное: \"{escaped_news}...\"\n\n"
                else:
                    text += "\n"
            
            # TradingView
            if tradingview_rating:
                # Get raw values once to avoid redundant lookups
                recommendation_raw = tradingview_rating.get("recommendation", "NEUTRAL")
                buy_signals = tradingview_rating.get("buy_signals", 0)
                sell_signals = tradingview_rating.get("sell_signals", 0)
                ma_raw = tradingview_rating.get("moving_averages", "NEUTRAL")
                osc_raw = tradingview_rating.get("oscillators", "NEUTRAL")
                
                # Escape for display
                ma = self.escape_markdown(str(ma_raw))
                osc = self.escape_markdown(str(osc_raw))
                
                # Map recommendation to display text
                if recommendation_raw == "STRONG_BUY":
                    tv_text = "STRONG BUY ✅✅"
                elif recommendation_raw == "BUY":
                    tv_text = "BUY ✅"
                elif recommendation_raw == "SELL":
                    tv_text = "SELL ❌"
                elif recommendation_raw == "STRONG_SELL":
                    tv_text = "STRONG SELL ❌❌"
                else:
                    tv_text = "NEUTRAL ➡️"
                
                text += f"📈 *TradingView:* {tv_text}\n"
                text += f"├─ MA сигнал: {ma} ({buy_signals} buy / {sell_signals} sell)\n"
                text += f"└─ Oscillators: {osc}\n\n"
            
            # Whale Alert
            if whale_alert:
                transactions = whale_alert.get("transactions_1h", 0)
                to_exchange = whale_alert.get("to_exchange_usd", 0)
                from_exchange = whale_alert.get("from_exchange_usd", 0)
                net_flow = whale_alert.get("net_flow", 0)
                
                text += f"🐋 *Whale Alert (1ч):*\n"
                text += f"├─ На биржи: {format_volume(to_exchange)}\n"
                text += f"├─ С бирж: {format_volume(from_exchange)}\n"
                
                if net_flow > 0:
                    flow_text = "бычье"
                    flow_emoji = "🟢"
                elif net_flow < 0:
                    flow_text = "медвежье"
                    flow_emoji = "🔴"
                else:
                    flow_text = "нейтрально"
                    flow_emoji = "🟡"
                
                text += f"└─ Нетто: {flow_emoji} {format_volume(abs(net_flow))} ({flow_text})\n\n"
            
            # Social (LunarCrush)
            if social_data:
                galaxy_score = social_data.get("galaxy_score", 0)
                sentiment = social_data.get("sentiment", 0)
                
                if sentiment > 0.3:
                    social_emoji = "🟢"
                    social_text = "Позитивный"
                elif sentiment < -0.3:
                    social_emoji = "🔴"
                    social_text = "Негативный"
                else:
                    social_emoji = "🟡"
                    social_text = "Нейтральный"
                
                text += f"🔥 *Social (LunarCrush):*\n"
                text += f"├─ Galaxy Score: {galaxy_score}/100\n"
                text += f"└─ Сентимент: {social_emoji} {social_text}\n\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Breakdown сигнала (22-факторная система)
        text += "🎯 *Breakdown сигнала (22 фактора):*\n\n"
        text += "📊 *Долгосрочные факторы (35%):*\n"
        text += f"├─ 🐋 Whale Score ({self.WHALE_WEIGHT:.0%}): {signal_data['whale_score']:+.1f}\n"
        text += f"├─ 📈 Trend Score ({self.TREND_WEIGHT:.0%}): {signal_data['trend_score']:+.1f}\n"
        text += f"├─ 💪 Momentum Score ({self.MOMENTUM_WEIGHT:.0%}): {signal_data['momentum_score']:+.1f}\n"
        text += f"├─ 📉 Volatility Score ({self.VOLATILITY_WEIGHT:.0%}): {signal_data['volatility_score']:+.1f}\n"
        text += f"├─ 📊 Volume Score ({self.VOLUME_WEIGHT:.0%}): {signal_data['volume_score']:+.1f}\n"
        text += f"├─ 💹 Market Score ({self.MARKET_WEIGHT:.0%}): {signal_data['market_score']:+.1f}\n"
        text += f"├─ 📖 Order Book ({self.ORDERBOOK_WEIGHT:.0%}): {signal_data['orderbook_score']:+.1f}\n"
        text += f"├─ 🔮 Derivatives ({self.DERIVATIVES_WEIGHT:.0%}): {signal_data['derivatives_score']:+.1f}\n"
        text += f"├─ ⛓️ On-Chain ({self.ONCHAIN_WEIGHT:.0%}): {signal_data['onchain_score']:+.1f}\n"
        text += f"└─ 😱 Sentiment ({self.SENTIMENT_WEIGHT:.0%}): {signal_data['sentiment_score']:+.1f}\n\n"
        
        text += "⚡ *Краткосрочные факторы (35%):*\n"
        text += f"├─ 📊 Short Trend ({self.SHORT_TREND_WEIGHT:.0%}): {signal_data['short_trend_score']:+.1f}\n"
        text += f"├─ 💱 Trades Flow ({self.TRADES_FLOW_WEIGHT:.0%}): {signal_data['trades_flow_score']:+.1f}\n"
        text += f"├─ ⚠️ Liquidations ({self.LIQUIDATIONS_WEIGHT:.0%}): {signal_data['liquidations_score']:+.1f}\n"
        text += f"├─ 📖 Orderbook Δ ({self.ORDERBOOK_DELTA_WEIGHT:.0%}): {signal_data['orderbook_delta_score']:+.1f}\n"
        text += f"└─ ⚡ Price Momentum ({self.PRICE_MOMENTUM_WEIGHT:.0%}): {signal_data['price_momentum_score']:+.1f}\n\n"
        
        text += "🆕 *Новые источники (30%):*\n"
        text += f"├─ 📊 OI Change ({self.COINGLASS_OI_WEIGHT:.0%}): {signal_data['coinglass_oi_score']:+.1f}\n"
        text += f"├─ 👥 Top Traders ({self.COINGLASS_TOP_TRADERS_WEIGHT:.0%}): {signal_data['coinglass_top_traders_score']:+.1f}\n"
        text += f"├─ 📰 News ({self.NEWS_SENTIMENT_WEIGHT:.0%}): {signal_data['news_sentiment_score']:+.1f}\n"
        text += f"├─ 📈 TradingView ({self.TRADINGVIEW_WEIGHT:.0%}): {signal_data['tradingview_score']:+.1f}\n"
        text += f"├─ 🐋 Whale Alert ({self.WHALE_ALERT_WEIGHT:.0%}): {signal_data['whale_alert_score']:+.1f}\n"
        text += f"└─ 🔥 Social ({self.SOCIAL_WEIGHT:.0%}): {signal_data['social_score']:+.1f}\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += f"*📊 ИТОГО: {signal_data['total_score']:+.1f} / 100 очков*\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # ИТОГ с вероятностями
        text += "🎯 *ИТОГ:*\n"
        if signal_data['probability_direction'] == "up":
            prob_up = signal_data['probability']
            prob_down = 100 - prob_up
        else:
            prob_down = signal_data['probability']
            prob_up = 100 - prob_down
        
        text += f"├─ Вероятность роста: {prob_up}%\n"
        text += f"├─ Вероятность падения: {prob_down}%\n"
        text += f"├─ Качество данных: {int(signal_data['data_quality'] * 100)}%\n"
        text += f"└─ Консенсус факторов: {signal_data.get('bullish_count', 0)}/{signal_data.get('bearish_count', 0)}/{signal_data.get('neutral_count', 0)} (↑/↓/→)\n\n"
        
        # Предупреждение
        text += "⚠️ _Не является финансовым советом.\n"
        text += "Проводите собственный анализ._\n\n"
        
        # Время обновления
        now = datetime.now()
        text += f"🕐 _Обновлено: {now.strftime('%H:%M:%S')}_"
        
        return text
    
    async def analyze_coin(self, symbol: str) -> str:
        """
        Полный анализ монеты и генерация сигнала с 10-факторной системой.
        
        Args:
            symbol: Символ монеты (BTC, ETH)
            
        Returns:
            Форматированное сообщение с AI сигналом
        """
        symbol = symbol.upper()
        
        # Сбрасываем кэш для получения свежих данных
        self.clear_cache()
        
        # Проверяем поддержку монеты
        if symbol not in self.blockchain_mapping:
            return (
                f"❌ *Ошибка*\n\n"
                f"Монета {symbol} пока не поддерживается.\n\n"
                f"Доступны: BTC, ETH"
            )
        
        try:
            bybit_symbol = self.bybit_mapping.get(symbol, f"{symbol}USDT")
            
            # Gather all data sources in parallel
            logger.info(f"Gathering all data sources for {symbol}...")
            
            whale_data_task = self.get_whale_data(symbol)
            market_data_task = self.get_market_data(symbol)
            fear_greed_task = self.get_fear_greed_index()
            funding_rate_task = self.get_funding_rate(symbol)
            
            # Gather external data sources
            external_data_task = self.data_source_manager.gather_all_data(
                self.whale_tracker, symbol, bybit_symbol
            )
            
            # Wait for all tasks
            whale_data, market_data, fear_greed, funding_rate, external_data = await asyncio.gather(
                whale_data_task,
                market_data_task,
                fear_greed_task,
                funding_rate_task,
                external_data_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(whale_data, Exception):
                logger.error(f"Error fetching whale data: {whale_data}")
                whale_data = None
            if isinstance(market_data, Exception):
                logger.error(f"Error fetching market data: {market_data}")
                market_data = None
            if isinstance(fear_greed, Exception):
                logger.error(f"Error fetching fear & greed: {fear_greed}")
                fear_greed = None
            if isinstance(funding_rate, Exception):
                logger.error(f"Error fetching funding rate: {funding_rate}")
                funding_rate = None
            if isinstance(external_data, Exception):
                logger.error(f"Error fetching external data: {external_data}")
                external_data = {}
            
            # Check essential data
            if market_data is None:
                return (
                    "❌ *Ошибка получения данных*\n\n"
                    "Не удалось загрузить рыночные данные.\n"
                    "Попробуйте позже."
                )
            
            # Default whale data if unavailable
            if whale_data is None:
                logger.warning(f"Whale data unavailable for {symbol}, using defaults")
                whale_data = {
                    "transaction_count": 0,
                    "total_volume_usd": 0,
                    "deposits": 0,
                    "withdrawals": 0,
                    "largest_transaction": 0,
                    "sentiment": "neutral"
                }
            
            # Extract external data
            ohlcv_data = external_data.get("ohlcv")
            order_book = external_data.get("order_book")
            trades = external_data.get("trades")
            futures_data = external_data.get("futures")
            onchain_data = external_data.get("onchain")
            exchange_flows = external_data.get("exchange_flows")
            
            # Calculate technical indicators with OHLCV data
            technical_data = await self.calculate_technical_indicators(symbol, ohlcv_data)
            
            # Gather SHORT-TERM data (NEW - not cached!)
            logger.info(f"Gathering short-term data for {symbol}...")
            short_term_ohlcv_5m_task = self.get_short_term_ohlcv(symbol, interval="5", limit=50)
            short_term_ohlcv_15m_task = self.get_short_term_ohlcv(symbol, interval="15", limit=50)
            trades_flow_task = self.get_recent_trades_flow(symbol)
            liquidations_task = self.get_liquidations(symbol)
            orderbook_delta_task = self.get_orderbook_delta(symbol)
            
            # Wait for short-term tasks
            short_term_ohlcv_5m, short_term_ohlcv_15m, trades_flow, liquidations, orderbook_delta = await asyncio.gather(
                short_term_ohlcv_5m_task,
                short_term_ohlcv_15m_task,
                trades_flow_task,
                liquidations_task,
                orderbook_delta_task,
                return_exceptions=True
            )
            
            # Handle exceptions for short-term data
            if isinstance(short_term_ohlcv_5m, Exception):
                logger.error(f"Error fetching 5m OHLCV: {short_term_ohlcv_5m}")
                short_term_ohlcv_5m = None
            if isinstance(short_term_ohlcv_15m, Exception):
                logger.error(f"Error fetching 15m OHLCV: {short_term_ohlcv_15m}")
                short_term_ohlcv_15m = None
            if isinstance(trades_flow, Exception):
                logger.error(f"Error fetching trades flow: {trades_flow}")
                trades_flow = None
            if isinstance(liquidations, Exception):
                logger.error(f"Error fetching liquidations: {liquidations}")
                liquidations = None
            if isinstance(orderbook_delta, Exception):
                logger.error(f"Error fetching orderbook delta: {orderbook_delta}")
                orderbook_delta = None
            
            # Calculate short-term indicators
            short_term_data = await self.calculate_short_term_indicators(symbol, short_term_ohlcv_5m, short_term_ohlcv_15m)
            
            # Gather NEW data sources (7 new sources)
            logger.info(f"Gathering new data sources for {symbol}...")
            coinglass_task = self.get_coinglass_data(symbol)
            news_task = self.get_crypto_news_sentiment(symbol)
            tradingview_task = self.get_tradingview_rating(symbol)
            whale_alert_task = self.get_whale_alert_transactions(symbol)
            social_task = self.get_lunarcrush_data(symbol)
            
            # Wait for new data sources
            coinglass_data, news_sentiment, tradingview_rating, whale_alert, social_data = await asyncio.gather(
                coinglass_task,
                news_task,
                tradingview_task,
                whale_alert_task,
                social_task,
                return_exceptions=True
            )
            
            # Handle exceptions for new data sources
            if isinstance(coinglass_data, Exception):
                logger.error(f"Error fetching Coinglass data: {coinglass_data}")
                coinglass_data = None
            if isinstance(news_sentiment, Exception):
                logger.error(f"Error fetching news sentiment: {news_sentiment}")
                news_sentiment = None
            if isinstance(tradingview_rating, Exception):
                logger.error(f"Error fetching TradingView rating: {tradingview_rating}")
                tradingview_rating = None
            if isinstance(whale_alert, Exception):
                logger.error(f"Error fetching Whale Alert: {whale_alert}")
                whale_alert = None
            if isinstance(social_data, Exception):
                logger.error(f"Error fetching social data: {social_data}")
                social_data = None
            
            # Log data availability (22 sources now)
            data_sources_available = {
                "whale_data": whale_data is not None and whale_data.get("transaction_count", 0) > 0,
                "market_data": market_data is not None,
                "technical_data": technical_data is not None,
                "fear_greed": fear_greed is not None,
                "funding_rate": funding_rate is not None,
                "order_book": order_book is not None,
                "trades": trades is not None,
                "futures_data": futures_data is not None,
                "onchain_data": onchain_data is not None,
                "exchange_flows": exchange_flows is not None,
                # Short-term
                "short_term_data": short_term_data is not None,
                "trades_flow": trades_flow is not None,
                "liquidations": liquidations is not None,
                "orderbook_delta": orderbook_delta is not None,
                # New sources
                "coinglass_data": coinglass_data is not None,
                "news_sentiment": news_sentiment is not None,
                "tradingview_rating": tradingview_rating is not None,
                "whale_alert": whale_alert is not None,
                "social_data": social_data is not None,
            }
            available_count = sum(1 for v in data_sources_available.values() if v)
            logger.info(f"Data sources available: {available_count}/22 for {symbol}")
            
            # Calculate signal with all available data (22-factor system)
            signal_data = self.calculate_signal(
                whale_data=whale_data,
                market_data=market_data,
                technical_data=technical_data,
                fear_greed=fear_greed,
                funding_rate=funding_rate,
                order_book=order_book,
                trades=trades,
                futures_data=futures_data,
                onchain_data=onchain_data,
                exchange_flows=exchange_flows,
                ohlcv_data=ohlcv_data,
                # Short-term data
                short_term_data=short_term_data,
                trades_flow=trades_flow,
                liquidations=liquidations,
                orderbook_delta=orderbook_delta,
                # New data sources
                coinglass_data=coinglass_data,
                news_sentiment=news_sentiment,
                tradingview_rating=tradingview_rating,
                whale_alert=whale_alert,
                social_data=social_data
            )
            
            # Format message with all data (including short-term)
            message = self.format_signal_message(
                symbol=symbol,
                signal_data=signal_data,
                whale_data=whale_data,
                market_data=market_data,
                technical_data=technical_data,
                fear_greed=fear_greed,
                funding_rate=funding_rate,
                order_book=order_book,
                futures_data=futures_data,
                onchain_data=onchain_data,
                exchange_flows=exchange_flows,
                # Short-term data
                short_term_data=short_term_data,
                trades_flow=trades_flow,
                liquidations=liquidations,
                orderbook_delta=orderbook_delta,
                # New data sources
                coinglass_data=coinglass_data,
                news_sentiment=news_sentiment,
                tradingview_rating=tradingview_rating,
                whale_alert=whale_alert,
                social_data=social_data
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return (
                "❌ *Ошибка анализа*\n\n"
                f"Произошла ошибка при анализе {symbol}.\n"
                "Попробуйте позже."
            )
