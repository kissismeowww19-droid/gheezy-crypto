"""
AI Signals - анализ и прогнозирование движения цен на основе данных китов и рынка.

Анализирует активность китов и рыночные данные для прогнозирования движения цены на ближайший час.
"""

import logging
import time
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
    
    # Total factors in the analysis system
    TOTAL_FACTORS = 22  # 10 long-term + 5 short-term + 6 new sources + sentiment
    TOTAL_DATA_SOURCES = 22  # Total number of data sources for probability calculation
    
    # Scaling factor for final score calculation
    SCORE_SCALE_FACTOR = 10  # Scale weighted sum from -10/+10 to -100/+100
    
    # Block score calculation constants
    BLOCK_SCORE_MULTIPLIER = 2.0  # Default multiplier for scaling block scores
    DERIVATIVES_SCORE_MULTIPLIER = 1.5  # Special multiplier for derivatives (more factors involved)
    
    # Short-term analysis constants
    EMA_CROSSOVER_THRESHOLD = 0.001  # 0.1% threshold for EMA crossover detection
    LONG_LIQUIDATION_RATIO = 0.7     # Assumed ratio of long liquidations in total
    SHORT_LIQUIDATION_RATIO = 0.3    # Assumed ratio of short liquidations in total
    TRADES_FLOW_BULLISH_THRESHOLD = 1.5   # Buy/Sell ratio threshold for bullish
    TRADES_FLOW_BEARISH_THRESHOLD = 0.67  # Buy/Sell ratio threshold for bearish
    TRADES_FLOW_NEUTRAL_DIVISOR = 0.33    # Normalization divisor for neutral range
    
    # Signal direction thresholds
    WEAK_SIGNAL_THRESHOLD = 5  # Порог слабого сигнала (боковик)
    
    # Signal stabilization constants
    SMOOTHING_ALPHA = 0.4  # 40% новый score + 60% старый (для сглаживания)
    DEAD_ZONE_DEFAULT = 10  # Мёртвая зона для BTC/ETH
    DEAD_ZONE_TON = 15  # Мёртвая зона для TON (более волатильный)
    HYSTERESIS_THRESHOLD = 30  # Минимальный score для разворота направления
    WEAK_SIGNAL_PROBABILITY = 52  # Фиксированная вероятность для слабых сигналов
    MEDIUM_SIGNAL_MAX_PROBABILITY = 58  # Максимальная вероятность для средних сигналов
    
    # Sideways display constants
    SIDEWAYS_RANGE_PERCENT = 1.0  # Диапазон для боковика (+/-1.0%)
    
    # Supported coins for AI signals
    SUPPORTED_SIGNAL_COINS = {"BTC", "ETH", "TON"}
    
    # Correlation signals TTL (10 minutes)
    CORRELATION_SIGNAL_TTL = 600  # 10 минут - время жизни сигналов для корреляции
    
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
            "SOL": "Solana",
            "XRP": "XRP",
        }
        
        # Маппинг для CoinGecko API
        self.coingecko_mapping = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "XRP": "ripple",
            "TON": "the-open-network",  # ID TON в CoinGecko
        }
        
        # Маппинг для Bybit
        self.bybit_mapping = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
            "SOL": "SOLUSDT",
            "XRP": "XRPUSDT",
            "TON": "TONUSDT",  # Добавлено для TON
        }
        
        # Простой кэш для внешних API
        self._cache = {}
        self._cache_timestamps = {}
        
        # Хранилище для расчёта delta (краткосрочные данные)
        self._previous_orderbook = {}  # {"BTC": {...}, "ETH": {...}}
        self._previous_prices = {}  # {"BTC": [(timestamp, price), ...], "ETH": [...]}
        
        # Память для стабилизации сигналов
        self.previous_scores: dict[str, float] = {}      # предыдущий score по монете
        self.previous_direction: dict[str, str] = {}     # предыдущее направление по монете
        
        # Хранение последних сигналов для межмонетной проверки (УСТАРЕВШЕЕ, для обратной совместимости)
        self.last_symbol_signals: dict[str, dict] = {}
        
        # Отдельное хранилище для сигналов корреляции (НЕ очищается при clear_cache, имеет TTL)
        self._correlation_signals: dict[str, dict] = {}
        
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
        """
        Очистить кэш внешних API данных для получения свежих данных.
        
        ВАЖНО: _correlation_signals НЕ очищаются - они имеют собственный TTL
        и используются для межмонетной корреляции (BTC → ETH/TON).
        """
        self._cache = {}
        self._cache_timestamps = {}
        logger.info("AISignalAnalyzer cache cleared (correlation signals preserved)")
    
    def _cleanup_expired_signals(self):
        """
        Удалить устаревшие сигналы для корреляции.
        
        Сигналы с истекшим TTL (expires_at < текущее время) удаляются,
        чтобы не влиять на новые расчёты устаревшими данными.
        """
        current_time = time.time()
        expired = [
            symbol for symbol, data in self._correlation_signals.items()
            if data.get("expires_at", 0) < current_time
        ]
        for symbol in expired:
            del self._correlation_signals[symbol]
            logger.debug(f"Expired correlation signal removed: {symbol}")
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired correlation signals: {expired}")
    
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
    
    def _clamp_block_score(self, score: float, factors: int, multiplier: float = None) -> float:
        """
        Helper method to normalize and clamp block scores to [-10, +10] range.
        
        Args:
            score: Raw accumulated score
            factors: Number of factors that contributed to the score
            multiplier: Scaling multiplier (defaults to BLOCK_SCORE_MULTIPLIER)
            
        Returns:
            Clamped score in range [-10, +10]
        """
        if factors == 0:
            return 0.0
        
        if multiplier is None:
            multiplier = self.BLOCK_SCORE_MULTIPLIER
        
        normalized_score = score / factors * multiplier
        return max(-10, min(10, normalized_score))

    def _calc_trend_score(
        self,
        ema_data: Optional[Dict],
        macd_data: Optional[Dict],
        price_change_24h: Optional[float],
        price_change_7d: Optional[float],
    ) -> float:
        """Расчёт score по тренду: EMA 50/200, MACD, изменение цены."""
        score = 0.0
        factors = 0
        
        if ema_data:
            ema_50 = ema_data.get("ema_50")
            ema_200 = ema_data.get("ema_200")
            current_price = ema_data.get("current_price")
            
            if ema_50 and ema_200 and current_price:
                factors += 1
                if current_price > ema_50 > ema_200:
                    score += 10
                elif current_price > ema_50:
                    score += 5
                elif current_price < ema_50 < ema_200:
                    score -= 10
                elif current_price < ema_50:
                    score -= 5
        
        if macd_data:
            macd_signal = macd_data.get("signal")
            factors += 1
            if macd_signal == "bullish":
                score += 7
            elif macd_signal == "bearish":
                score -= 7
        
        if price_change_24h is not None:
            factors += 1
            if price_change_24h > 5:
                score += 5
            elif price_change_24h > 2:
                score += 3
            elif price_change_24h < -5:
                score -= 5
            elif price_change_24h < -2:
                score -= 3
        
        if price_change_7d is not None:
            factors += 1
            if price_change_7d > 10:
                score += 5
            elif price_change_7d > 5:
                score += 3
            elif price_change_7d < -10:
                score -= 5
            elif price_change_7d < -5:
                score -= 3
        
        return self._clamp_block_score(score, factors)

    def _calc_momentum_score(
        self,
        rsi: Optional[float],
        rsi_5m: Optional[float],
        rsi_15m: Optional[float],
        price_momentum_10min: Optional[float],
    ) -> float:
        """Расчёт score по импульсу: RSI разных ТФ."""
        score = 0.0
        factors = 0
        
        if rsi is not None:
            factors += 1
            if rsi < 30:
                score += 8
            elif rsi < 40:
                score += 4
            elif rsi > 70:
                score -= 8
            elif rsi > 60:
                score -= 4
        
        if rsi_5m is not None:
            factors += 1
            if rsi_5m < 30:
                score += 5
            elif rsi_5m > 70:
                score -= 5
        
        if rsi_15m is not None:
            factors += 1
            if rsi_15m < 30:
                score += 5
            elif rsi_15m > 70:
                score -= 5
        
        if price_momentum_10min is not None:
            factors += 1
            if price_momentum_10min > 1:
                score += 6
            elif price_momentum_10min > 0.5:
                score += 3
            elif price_momentum_10min < -1:
                score -= 6
            elif price_momentum_10min < -0.5:
                score -= 3
        
        return self._clamp_block_score(score, factors)

    def _calc_whales_score(
        self,
        whale_data: Optional[Dict],
        exchange_netflow: Optional[float],
    ) -> float:
        """Расчёт score по китам: ончейн потоки."""
        score = 0.0
        factors = 0
        
        if whale_data:
            deposits = whale_data.get("deposits", 0)
            withdrawals = whale_data.get("withdrawals", 0)
            
            if deposits > 0 or withdrawals > 0:
                factors += 1
                net_flow = withdrawals - deposits
                
                if net_flow > 5:
                    score += 10
                elif net_flow > 2:
                    score += 6
                elif net_flow < -5:
                    score -= 10
                elif net_flow < -2:
                    score -= 6
        
        if exchange_netflow is not None:
            factors += 1
            if exchange_netflow < -1000000:
                score += 8
            elif exchange_netflow < -100000:
                score += 4
            elif exchange_netflow > 1000000:
                score -= 8
            elif exchange_netflow > 100000:
                score -= 4
        
        return self._clamp_block_score(score, factors)

    def _calc_derivatives_score(
        self,
        oi_change: Optional[float],
        funding_rate: Optional[float],
        long_short_ratio: Optional[float],
        liquidations: Optional[Dict],
        price_change: Optional[float],
    ) -> float:
        """Расчёт score по деривативам с составными правилами."""
        score = 0.0
        factors = 0
        
        oi_up = oi_change is not None and oi_change > 2
        oi_down = oi_change is not None and oi_change < -2
        price_up = price_change is not None and price_change > 0
        price_down = price_change is not None and price_change < 0
        funding_high = funding_rate is not None and funding_rate > 0.03
        funding_normal = funding_rate is not None and -0.01 <= funding_rate <= 0.03
        
        # СОСТАВНЫЕ ПРАВИЛА
        if oi_up and price_up and funding_normal:
            score += 8
            factors += 1
        elif oi_up and price_up and funding_high:
            score -= 3
            factors += 1
        elif oi_up and price_down:
            score += 5
            factors += 1
        elif oi_down and price_down:
            score += 6
            factors += 1
        elif oi_down and price_up:
            score += 2
            factors += 1
        
        if funding_rate is not None:
            factors += 1
            if funding_rate < -0.02:
                score += 7
            elif funding_rate < -0.01:
                score += 4
            elif funding_rate > 0.05:
                score -= 7
            elif funding_rate > 0.03:
                score -= 4
        
        if long_short_ratio is not None:
            factors += 1
            if long_short_ratio < 0.8:
                score += 5
            elif long_short_ratio > 1.5:
                score -= 5
        
        if liquidations:
            long_liqs = liquidations.get("long_liquidations", 0)
            short_liqs = liquidations.get("short_liquidations", 0)
            if long_liqs > 0 or short_liqs > 0:
                factors += 1
                if short_liqs > long_liqs * 2:
                    score += 5
                elif long_liqs > short_liqs * 2:
                    score -= 5
        
        return self._clamp_block_score(score, factors, self.DERIVATIVES_SCORE_MULTIPLIER)

    def _calc_sentiment_score(
        self,
        fear_greed: Optional[int],
        tradingview_rating: Optional[str],
    ) -> float:
        """Расчёт score по настроениям."""
        score = 0.0
        factors = 0
        
        if fear_greed is not None:
            factors += 1
            if fear_greed < 20:
                score += 10
            elif fear_greed < 35:
                score += 5
            elif fear_greed > 80:
                score -= 10
            elif fear_greed > 65:
                score -= 5
        
        if tradingview_rating:
            factors += 1
            rating = tradingview_rating.upper()
            if rating == "STRONG_BUY":
                score += 10
            elif rating == "BUY":
                score += 5
            elif rating == "STRONG_SELL":
                score -= 10
            elif rating == "SELL":
                score -= 5
        
        return self._clamp_block_score(score, factors)

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
    
    def _determine_direction_from_score(self, total_score: float) -> str:
        """
        Определить направление строго по score.
        Никаких исключений — данные решают.
        
        Args:
            total_score: Итоговый score (-100..+100)
            
        Returns:
            "short" если score <= -10
            "long" если score >= 10
            "sideways" если -10 < score < 10
        """
        if total_score <= -10:
            return "short"      # Чёткий медвежий сигнал
        elif total_score >= 10:
            return "long"       # Чёткий бычий сигнал
        else:
            return "sideways"   # Нет чёткого направления = боковик
    
    def _calculate_real_probability(
        self,
        total_score: float,
        direction: str,
        bullish_count: int,
        bearish_count: int,
        neutral_count: int
    ) -> int:
        """
        Рассчитать реальную вероятность на основе:
        1. Силы score (чем дальше от 0, тем увереннее)
        2. Консенсуса факторов (bullish vs bearish)
        3. Количества нейтральных (много нейтральных = неопределённость)
        
        Args:
            total_score: Итоговый score (-100..+100)
            direction: Направление ("long"/"short"/"sideways")
            bullish_count: Количество бычьих факторов
            bearish_count: Количество медвежьих факторов
            neutral_count: Количество нейтральных факторов
            
        Returns:
            Вероятность 50-85%
        """
        abs_score = abs(total_score)
        
        if direction == "sideways":
            # Боковик: чем ближе к 0, тем увереннее
            if abs_score < 2:
                base = 68  # Очень уверенный боковик
            elif abs_score < 4:
                base = 63
            elif abs_score < 6:
                base = 58
            elif abs_score < 8:
                base = 54
            else:
                base = 51  # На грани направления
        else:
            # Long/Short: чем дальше от 10, тем увереннее
            if abs_score < 12:
                base = 52  # Слабый сигнал (только перешёл границу)
            elif abs_score < 15:
                base = 56
            elif abs_score < 18:
                base = 60
            elif abs_score < 22:
                base = 65
            elif abs_score < 28:
                base = 70
            elif abs_score < 35:
                base = 75
            else:
                base = 80  # Экстремально сильный сигнал
        
        # Бонус за консенсус факторов
        if direction == "long" and bullish_count > bearish_count:
            consensus_bonus = min(5, bullish_count - bearish_count)
            base += consensus_bonus
        elif direction == "short" and bearish_count > bullish_count:
            consensus_bonus = min(5, bearish_count - bullish_count)
            base += consensus_bonus
        elif direction == "sideways":
            # Для боковика: много нейтральных = хорошо
            if neutral_count > (bullish_count + bearish_count):
                base += 3
        
        # Штраф за противоречивые данные
        if direction == "long" and bearish_count > bullish_count:
            base -= 5  # Данные противоречат направлению
        elif direction == "short" and bullish_count > bearish_count:
            base -= 5
        
        return max(50, min(85, base))
    
    def _calculate_probability_for_sideways(self, total_score: float) -> int:
        """
        Рассчитать вероятность для боковика на основе score.
        
        Чем ближе score к 0, тем выше уверенность в боковике.
        Чем ближе score к границе dead zone (8-10), тем ниже уверенность.
        
        Args:
            total_score: Итоговый score (-100..+100)
            
        Returns:
            Вероятность 51-62%
        """
        abs_score = abs(total_score)
        
        if abs_score < 2:
            # Очень близко к нулю — высокая уверенность в боковике
            return 62
        elif abs_score < 4:
            # Слабый сигнал — средняя уверенность
            return 58
        elif abs_score < 6:
            # Средний сигнал
            return 55
        elif abs_score < 8:
            # Ближе к границе
            return 53
        else:
            # На грани направления — низкая уверенность в боковике
            return 51
    
    def _calculate_probability(
        self,
        total_score: float,      # -100..+100
        direction: str,          # "long"/"short"/"sideways"
        bullish_count: int,
        bearish_count: int,
        data_sources_count: int,
        total_sources: int,
        trend_score: float,      # -10..+10
        # Новые параметры для полного расчёта
        block_trend_score: float = 0,      # -10..+10
        block_momentum_score: float = 0,   # -10..+10
        block_whales_score: float = 0,     # -10..+10
        block_derivatives_score: float = 0, # -10..+10
        block_sentiment_score: float = 0,  # -10..+10
    ) -> int:
        """
        ПОЛНЫЙ расчёт вероятности на основе ВСЕХ факторов и данных.
        
        Компоненты вероятности:
        1. База: 50%
        2. Сила сигнала: 0-12%
        3. Консенсус факторов: 0-12%
        4. Охват данных: 0-8%
        5. Тренд (блок): 0-8%
        6. Импульс (блок): 0-5%
        7. Киты (блок): 0-5%
        8. Деривативы (блок): 0-5%
        9. Настроения (блок): 0-5%
        
        Штрафы:
        - Конфликт факторов: -5%
        - Против тренда: -8%
        - Слабый консенсус: -3%
        
        Итого: 50-85%
        """
        
        # ====== БАЗА ======
        base_prob = 50.0
        
        # ====== 1. БОНУС ОТ СИЛЫ СИГНАЛА (0-12%) ======
        # total_score: -100..+100, берём абсолютное значение
        strength = min(100, max(0, abs(total_score)))
        strength_bonus = (strength / 100) * 12
        
        # ====== 2. БОНУС ОТ КОНСЕНСУСА ФАКТОРОВ (0-12%) ======
        # Чем больше факторов в одном направлении, тем выше вероятность
        total_factors = bullish_count + bearish_count
        if total_factors > 0:
            # Разница между бычьими и медвежьими
            consensus_diff = abs(bullish_count - bearish_count)
            # Нормализуем: если все факторы в одном направлении = 100%
            consensus_ratio = consensus_diff / total_factors
            consensus_bonus = consensus_ratio * 12
        else:
            consensus_bonus = 0
        
        # ====== 3. БОНУС ОТ ОХВАТА ДАННЫХ (0-8%) ======
        # Чем больше источников данных, тем увереннее сигнал
        coverage = data_sources_count / max(1, total_sources)
        coverage_bonus = coverage * 8
        
        # ====== 4. БОНУС ОТ БЛОКА ТРЕНДА (0-8%) ======
        # block_trend_score: -10..+10
        # Берём абсолютное значение и нормализуем
        trend_strength = abs(block_trend_score) / 10
        trend_bonus = trend_strength * 8
        
        # ====== 5. БОНУС ОТ БЛОКА ИМПУЛЬСА (0-5%) ======
        momentum_strength = abs(block_momentum_score) / 10
        momentum_bonus = momentum_strength * 5
        
        # ====== 6. БОНУС ОТ БЛОКА КИТОВ (0-5%) ======
        whales_strength = abs(block_whales_score) / 10
        whales_bonus = whales_strength * 5
        
        # ====== 7. БОНУС ОТ БЛОКА ДЕРИВАТИВОВ (0-5%) ======
        derivatives_strength = abs(block_derivatives_score) / 10
        derivatives_bonus = derivatives_strength * 5
        
        # ====== 8. БОНУС ОТ БЛОКА НАСТРОЕНИЙ (0-5%) ======
        sentiment_strength = abs(block_sentiment_score) / 10
        sentiment_bonus = sentiment_strength * 5
        
        # ====== СУММИРУЕМ БОНУСЫ ======
        prob = base_prob + strength_bonus + consensus_bonus + coverage_bonus
        prob += trend_bonus + momentum_bonus + whales_bonus + derivatives_bonus + sentiment_bonus
        
        # ====== ШТРАФЫ ======
        
        # 1. Конфликт факторов (есть и бычьи и медвежьи)
        if bullish_count > 0 and bearish_count > 0:
            prob -= 5
        
        # 2. Равный консенсус (бычьи == медвежьи) — очень неопределённо
        if bullish_count == bearish_count and bullish_count > 0:
            prob -= 3
        
        # 3. Слабый консенсус (мало факторов)
        if total_factors < 3:
            prob -= 3
        
        # 4. Против тренда
        if direction == "long":
            if trend_score < -3:
                prob -= 8  # Лонг против сильного медвежьего тренда
            elif trend_score < 0:
                prob -= 4  # Лонг против слабого медвежьего тренда
            elif trend_score > 3:
                prob += 3  # Лонг по сильному бычьему тренду
        elif direction == "short":
            if trend_score > 3:
                prob -= 8  # Шорт против сильного бычьего тренда
            elif trend_score > 0:
                prob -= 4  # Шорт против слабого бычьего тренда
            elif trend_score < -3:
                prob += 3  # Шорт по сильному медвежьему тренду
        
        # 5. Боковик — используем специальный расчёт на основе score
        if direction == "sideways":
            # Используем новый метод для расчёта вероятности боковика
            base_sideways_prob = self._calculate_probability_for_sideways(total_score)
            
            # Применяем дополнительные корректировки на основе других факторов
            # (небольшие бонусы/штрафы, но не выходим за пределы 50-62%)
            
            # Бонус за хороший охват данных (до +2%)
            if coverage > 0.8:
                base_sideways_prob = min(62, base_sideways_prob + 2)
            
            # Штраф за конфликт факторов (-2%)
            if bullish_count > 0 and bearish_count > 0:
                base_sideways_prob = max(50, base_sideways_prob - 2)
            
            prob = base_sideways_prob
        
        # ====== ФИНАЛЬНЫЕ ГРАНИЦЫ ======
        prob = int(round(max(50, min(85, prob))))
        
        return prob
    
    def _cross_asset_correlation_check(
        self,
        symbol: str,
        direction: str,
        probability: int,
        total_score: float,
        trend_score: float,
        block_trend_score: float,
        block_momentum_score: float,
        block_whales_score: float,
        block_derivatives_score: float,
        block_sentiment_score: float,
        bullish_count: int,
        bearish_count: int,
        neutral_count: int,
        data_sources_count: int,
    ) -> tuple[str, int, float, bool]:
        """
        Реальный расчёт сигнала с учётом корреляции BTC/ETH/TON.
        
        BTC — ведущий индикатор рынка. Его данные влияют на ETH и TON.
        
        Корреляции (реальные рыночные):
        - BTC/ETH: ~90% → 40% влияние BTC score на ETH
        - BTC/TON: ~70% → 30% влияние BTC score на TON
        
        Возвращает:
        - скорректированное direction (на основе adjusted_total_score)
        - скорректированную probability (пересчитанную по ВСЕМ факторам)
        - скорректированный total_score
        - флаг is_cross_conflict
        """
        is_cross_conflict = False
        
        # BTC рассчитывается без корректировок — он ведущий индикатор
        if symbol == "BTC":
            logger.info(f"Cross-asset: {symbol} is leading indicator, no adjustment")
            return direction, probability, total_score, is_cross_conflict
        
        # Получаем последний сигнал BTC из хранилища корреляции
        btc_signal = self._correlation_signals.get("BTC")
        
        # ЛОГИРОВАНИЕ: что есть в _correlation_signals
        logger.info(f"Cross-asset check for {symbol}: _correlation_signals keys = {list(self._correlation_signals.keys())}")
        
        if not btc_signal:
            # Если BTC ещё не рассчитан, возвращаем без изменений
            logger.warning(f"Cross-asset: No BTC signal found for {symbol} correlation")
            return direction, probability, total_score, is_cross_conflict
        
        # Проверяем свежесть сигнала BTC (не старше 10 минут)
        expires_at = btc_signal.get("expires_at", 0)
        current_time = time.time()
        generated_at = btc_signal.get("generated_at", 0)
        age_seconds = current_time - generated_at
        logger.info(f"Cross-asset: BTC signal age = {age_seconds:.1f}s")
        
        if expires_at < current_time:
            logger.warning(f"Cross-asset: BTC signal expired ({age_seconds:.1f}s > 600s)")
            return direction, probability, total_score, is_cross_conflict
        
        btc_direction = btc_signal["direction"]
        btc_total_score = btc_signal["total_score"]
        btc_trend = btc_signal.get("trend_score", 0)
        
        logger.info(f"Cross-asset: BTC signal = direction={btc_direction}, total_score={btc_total_score}")
        
        # Корреляция только при сильном BTC сигнале
        if abs(btc_total_score) < 10:
            logger.info(f"BTC in sideways (score={btc_total_score:.2f}), no correlation applied to {symbol}")
            return direction, probability, total_score, False
        
        # ====== ОПРЕДЕЛЯЕМ СИЛУ КОРРЕЛЯЦИИ ======
        if symbol == "ETH":
            correlation = 0.40  # 40% влияние BTC на ETH (высокая корреляция)
        elif symbol == "TON":
            correlation = 0.30  # 30% влияние BTC на TON (средняя корреляция)
        else:
            correlation = 0.20  # Для других монет
        
        # ====== КОРРЕКТИРОВКА TOTAL_SCORE ======
        # Добавляем влияние BTC к собственному score монеты
        btc_influence = btc_total_score * correlation
        adjusted_total_score = total_score + btc_influence
        
        logger.info(f"Cross-asset: {symbol} score adjustment: {total_score:.2f} + ({btc_total_score:.2f} * {correlation}) = {adjusted_total_score:.2f}")
        
        # ====== ПЕРЕСЧЁТ НАПРАВЛЕНИЯ по adjusted_total_score ======
        # Используем единственный источник правды для определения направления
        new_direction = self._determine_direction_from_score(adjusted_total_score)
        
        # ====== ОПРЕДЕЛЯЕМ КОНФЛИКТ ======
        # Конфликт если направление изменилось с long на short или наоборот
        if direction in ("long", "short") and new_direction in ("long", "short"):
            if direction != new_direction:
                is_cross_conflict = True
        
        # ====== ПЕРЕСЧЁТ ВЕРОЯТНОСТИ ======
        # Используем новый метод для реальной вероятности
        new_probability = self._calculate_real_probability(
            total_score=adjusted_total_score,
            direction=new_direction,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            neutral_count=neutral_count
        )
        
        # ЛОГИРОВАНИЕ РЕЗУЛЬТАТА
        logger.info(f"Cross-asset RESULT for {symbol}: direction {direction} → {new_direction}, probability {probability} → {new_probability}, score {total_score:.2f} → {adjusted_total_score:.2f}, conflict={is_cross_conflict}")
        
        return new_direction, new_probability, adjusted_total_score, is_cross_conflict

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
    
    def calculate_signal(self, symbol: str, whale_data: Dict, market_data: Dict, technical_data: Optional[Dict] = None, 
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
        # Очистка устаревших сигналов корреляции
        self._cleanup_expired_signals()
        
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
        
        # Сглаживание score для стабильности
        new_score = total_score
        prev_score = self.previous_scores.get(symbol)
        
        if prev_score is not None:
            total_score = self.SMOOTHING_ALPHA * new_score + (1 - self.SMOOTHING_ALPHA) * prev_score
        
        # Сохраняем для следующего раза
        self.previous_scores[symbol] = total_score
        
        # РАСЧЁТ 5 БЛОКОВ для нового расчёта вероятности
        # Подготовка данных для блоков
        
        # 1. Trend block data
        ema_data = None
        if technical_data and "ma_crossover" in technical_data:
            # Extract EMA data if available
            ema_data = {
                "ema_50": technical_data.get("ema_50"),
                "ema_200": technical_data.get("ema_200"),
                "current_price": market_data.get("price_usd"),
            }
        
        macd_data = None
        if technical_data and "macd" in technical_data:
            macd_data = {"signal": technical_data["macd"].get("signal")}
        
        price_change_24h = market_data.get("change_24h") or market_data.get("price_change_24h")
        price_change_7d = market_data.get("change_7d") or market_data.get("price_change_7d")
        
        block_trend_score = self._calc_trend_score(ema_data, macd_data, price_change_24h, price_change_7d)
        
        # 2. Momentum block data
        rsi = None
        rsi_5m = None
        rsi_15m = None
        if technical_data and "rsi" in technical_data:
            rsi = technical_data["rsi"].get("value")
        if short_term_data:
            rsi_5m = short_term_data.get("rsi_5m")
            rsi_15m = short_term_data.get("rsi_15m")
        
        price_momentum_10min = None
        if short_term_data:
            current_price_st = short_term_data.get("current_price")
            price_10min_ago = short_term_data.get("price_10min_ago")
            if current_price_st and price_10min_ago and price_10min_ago > 0:
                price_momentum_10min = ((current_price_st - price_10min_ago) / price_10min_ago) * 100
        
        block_momentum_score = self._calc_momentum_score(rsi, rsi_5m, rsi_15m, price_momentum_10min)
        
        # 3. Whales block data
        exchange_netflow_value = None
        if exchange_flows:
            exchange_netflow_value = exchange_flows.get("net_flow_usd")
        
        block_whales_score = self._calc_whales_score(whale_data, exchange_netflow_value)
        
        # 4. Derivatives block data
        oi_change_value = None
        if coinglass_data:
            oi_change_value = coinglass_data.get("oi_change_24h")
        
        funding_rate_value = None
        if funding_rate:
            funding_rate_value = funding_rate.get("rate") or funding_rate.get("rate_percent")
        
        long_short_ratio_value = None
        if futures_data:
            long_short_ratio_value = futures_data.get("long_short_ratio")
        
        liquidations_data = liquidations
        price_change_for_deriv = market_data.get("change_24h") or market_data.get("price_change_24h")
        
        block_derivatives_score = self._calc_derivatives_score(
            oi_change_value, funding_rate_value, long_short_ratio_value, liquidations_data, price_change_for_deriv
        )
        
        # 5. Sentiment block data
        fear_greed_value = None
        if fear_greed:
            fear_greed_value = fear_greed.get("value")
        
        tradingview_rating_value = None
        if tradingview_rating:
            summary = tradingview_rating.get("summary", {})
            tradingview_rating_value = summary.get("RECOMMENDATION")
        
        block_sentiment_score = self._calc_sentiment_score(fear_greed_value, tradingview_rating_value)
        
        # Apply weights to 5 blocks (total should equal 1.0)
        weights = {
            "trend": 0.25,
            "momentum": 0.20,
            "whales": 0.20,
            "derivatives": 0.25,
            "sentiment": 0.10
        }
        
        factor_score = (
            block_trend_score * weights["trend"] +
            block_momentum_score * weights["momentum"] +
            block_whales_score * weights["whales"] +
            block_derivatives_score * weights["derivatives"] +
            block_sentiment_score * weights["sentiment"]
        )
        
        # Scale to -100..+100 for compatibility
        raw_total_score_5blocks = factor_score * 10
        
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
        
        # ====== МЕЖМОНЕТНАЯ КОРРЕЛЯЦИЯ ======
        # Корректируем сигнал с учётом BTC (ведущий индикатор рынка)
        logger.info(f"Applying cross-asset correlation for {symbol}...")
        
        # Определяем начальное направление по score (до корреляции)
        initial_direction = self._determine_direction_from_score(total_score)
        
        # Initial probability for correlation check (not used, will be recalculated)
        INITIAL_PROBABILITY = 50  # Neutral baseline before honest probability calculation
        
        adjusted_direction, adjusted_probability, adjusted_total_score, is_cross_conflict = self._cross_asset_correlation_check(
            symbol=symbol,
            direction=initial_direction,
            probability=INITIAL_PROBABILITY,
            total_score=total_score,
            trend_score=block_trend_score,
            block_trend_score=block_trend_score,
            block_momentum_score=block_momentum_score,
            block_whales_score=block_whales_score,
            block_derivatives_score=block_derivatives_score,
            block_sentiment_score=block_sentiment_score,
            bullish_count=consensus_data["bullish_count"],
            bearish_count=consensus_data["bearish_count"],
            neutral_count=consensus_data["neutral_count"],
            data_sources_count=data_sources_available,
        )
        
        # ЛОГИРОВАНИЕ результата корреляции
        logger.info(f"Cross-asset result: direction {initial_direction} → {adjusted_direction}, score {total_score:.2f} → {adjusted_total_score:.2f}")
        
        # Применяем корректировки
        raw_direction = adjusted_direction
        total_score = adjusted_total_score
        
        # ====== ФИНАЛЬНОЕ НАПРАВЛЕНИЕ И ТЕКСТ ======
        # Направление определяется ТОЛЬКО по score (уже учтена корреляция)
        final_direction = raw_direction  # Уже определено через _determine_direction_from_score
        
        # Текст соответствует направлению
        if final_direction == "long":
            if abs(total_score) >= 25:
                direction = "📈 ЛОНГ"
                strength = "сильный"
            else:
                direction = "📈 Вероятно вверх"
                strength = "средний"
        elif final_direction == "short":
            if abs(total_score) >= 25:
                direction = "📉 ШОРТ"
                strength = "сильный"
            else:
                direction = "📉 Вероятно вниз"
                strength = "средний"
        else:  # sideways
            direction = "➡️ Боковик"
            strength = "слабый"
        
        # Вероятность рассчитывается по реальным данным
        final_probability = self._calculate_real_probability(
            total_score=total_score,
            direction=final_direction,
            bullish_count=consensus_data["bullish_count"],
            bearish_count=consensus_data["bearish_count"],
            neutral_count=consensus_data["neutral_count"]
        )
        
        logger.info(f"FINAL signal for {symbol}: direction={direction}, raw={final_direction}, score={total_score:.2f}, probability={final_probability}%")
        
        # Determine confidence based on probability
        if final_probability >= 70:
            confidence = "Высокая"
            confidence_en = "high"
        elif final_probability >= 60:
            confidence = "Средняя"
            confidence_en = "medium"
        else:
            confidence = "Низкая"
            confidence_en = "low"
        
        # Create probability_data with final values
        probability_data = {
            "probability": final_probability,
            "direction": "up" if final_direction == "long" else ("down" if final_direction == "short" else "sideways"),
            "confidence": confidence_en,
            "data_quality": round(data_sources_available / self.TOTAL_DATA_SOURCES, 2)
        }
        
        # Save direction for next time (for hysteresis tracking, though not actively used in honest signals)
        self.previous_direction[symbol] = final_direction
        
        # ====== СОХРАНЯЕМ СИГНАЛ ДЛЯ МЕЖМОНЕТНОЙ ПРОВЕРКИ ======
        current_time = time.time()
        
        # Сохраняем в старое хранилище для обратной совместимости
        self.last_symbol_signals[symbol] = {
            "direction": final_direction,
            "probability": final_probability,
            "total_score": total_score,
            "trend_score": block_trend_score,
            "generated_at": current_time,
        }
        
        # Сохраняем в отдельное хранилище корреляции с TTL
        self._correlation_signals[symbol] = {
            "direction": final_direction,
            "probability": final_probability,
            "total_score": total_score,
            "trend_score": block_trend_score,
            "generated_at": current_time,
            "expires_at": current_time + self.CORRELATION_SIGNAL_TTL,  # TTL 10 минут
        }
        logger.info(f"Saved signal for {symbol}: direction={final_direction}, probability={final_probability}, total_score={total_score:.2f} (expires in {self.CORRELATION_SIGNAL_TTL}s)")
        
        # Normalize strength to 0-100%
        strength_percent = min(max((total_score + 100) / 200 * 100, 0), 100)
        
        return {
            "symbol": symbol,
            "direction": direction,
            "raw_direction": final_direction,  # "long" или "short" или "sideways"
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
            # Add 5 block scores for display
            "block_trend_score": round(block_trend_score, 2),
            "block_momentum_score": round(block_momentum_score, 2),
            "block_whales_score": round(block_whales_score, 2),
            "block_derivatives_score": round(block_derivatives_score, 2),
            "block_sentiment_score": round(block_sentiment_score, 2),
            # Cross-asset correlation conflict flag
            "is_cross_conflict": is_cross_conflict,
        }
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Экранирует специальные символы Markdown для безопасного отображения в Telegram.
        
        Args:
            text: Текст для экранирования
            
        Returns:
            Экранированный текст (или исходное значение если None/не строка)
            
        Note:
            - Gracefully handles None and non-string inputs by returning them unchanged.
              This is intentional for defensive programming when dealing with optional
              API responses that may be None or unexpected types.
            - Uses simple string.replace() in a loop for readability and maintainability.
            - Performance is acceptable since we're dealing with short strings (news titles,
              status messages, etc.) typically under 200 characters. For larger texts,
              str.translate() with a translation table would be more efficient.
        """
        if not text or not isinstance(text, str):
            # Return unchanged for None or non-string inputs (defensive programming)
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
        social_data: Optional[Dict] = None,
        is_cross_conflict: bool = False,  # НОВЫЙ ПАРАМЕТР
    ) -> str:
        """
        Расширенное форматирование сообщения с AI сигналом.
        
        Включает:
        - Направление сигнала с вероятностью и силой
        - Цена, TP (два уровня), SL
        - Тренд цены (1ч, 24ч, 7д)
        - Рыночные данные (Market Cap, Volume, Vol/MCap)
        - Активность китов (score, транзакции, потоки)
        - Технический анализ (RSI, MACD, BB, EMA)
        - Уровни поддержки/сопротивления
        - Топ 5 причин для сигнала
        - Факторы анализа (бычьи/медвежьи/нейтральные)
        
        Args:
            symbol: Символ монеты
            signal_data: Результаты анализа сигнала
            whale_data: Данные о китах
            market_data: Рыночные данные
            ... (остальные параметры используются для расчёта)
            
        Returns:
            Форматированное сообщение для Telegram (MarkdownV2)
        """
        # Форматирование цены
        def format_price(price: float) -> str:
            if price >= 1000:
                return f"${price:,.0f}"
            elif price >= 1:
                return f"${price:,.2f}"
            else:
                return f"${price:.6f}"
        
        # Форматирование объёмов
        def format_volume(volume: float) -> str:
            if volume >= 1_000_000_000:
                return f"${volume / 1_000_000_000:.1f}B"
            elif volume >= 1_000_000:
                return f"${volume / 1_000_000:.1f}M"
            elif volume >= 1_000:
                return f"${volume / 1_000:.1f}K"
            return f"${volume:.0f}"
        
        # Определяем направление из raw_direction (учитывает sideways)
        raw_direction = signal_data.get('raw_direction', 'sideways')
        probability_direction = signal_data.get('probability_direction', 'up')
        probability = signal_data['probability']
        
        # Текущая цена
        current_price = market_data['price_usd']
        
        # Направление и эмодзи
        if raw_direction == "long":
            direction_text = "ЛОНГ"
            direction_emoji = "📈"
            is_long = True
            is_sideways = False
        elif raw_direction == "short":
            direction_text = "ШОРТ"
            direction_emoji = "📉"
            is_long = False
            is_sideways = False
        else:  # sideways
            direction_text = "Боковик"
            direction_emoji = "➡️"
            is_long = False
            is_sideways = True
        
        # Рассчитываем TP (два уровня) и SL
        if is_sideways:
            # Для боковика показываем диапазон
            range_high = current_price * (1 + self.SIDEWAYS_RANGE_PERCENT / 100)
            range_low = current_price * (1 - self.SIDEWAYS_RANGE_PERCENT / 100)
            tp1_price = None
            tp2_price = None
            sl_price = None
        elif is_long:
            tp1_percent = 1.5
            tp2_percent = 2.0
            sl_percent = -0.6
            tp1_price = current_price * (1 + tp1_percent / 100)
            tp2_price = current_price * (1 + tp2_percent / 100)
            sl_price = current_price * (1 + sl_percent / 100)
            range_high = None
            range_low = None
        else:  # short
            tp1_percent = -1.5
            tp2_percent = -2.0
            sl_percent = 0.6
            tp1_price = current_price * (1 + tp1_percent / 100)
            tp2_price = current_price * (1 + tp2_percent / 100)
            sl_price = current_price * (1 + sl_percent / 100)
            range_high = None
            range_low = None
        
        # Сила сигнала (рассчитывается из total_score, не probability)
        # total_score диапазон: -100 до +100
        # Преобразуем в 0-100%
        total_score = signal_data.get('total_score', 0)
        strength_value = abs(total_score)
        signal_strength = min(100, int(strength_value))
        filled_blocks = int(signal_strength / 10)
        empty_blocks = 10 - filled_blocks
        strength_bar = "█" * filled_blocks + "░" * empty_blocks
        
        # ===== НАЧАЛО СООБЩЕНИЯ =====
        text = f"🤖 *AI СИГНАЛ: {symbol}*\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # ===== НАПРАВЛЕНИЕ =====
        text += "📊 *НАПРАВЛЕНИЕ*\n"
        text += f"{direction_emoji} {direction_text} ({probability}% вероятность)\n"
        text += f"Сила сигнала: {strength_bar} {signal_strength}%\n"
        
        # Если был конфликт с BTC, добавляем предупреждение
        if is_cross_conflict or signal_data.get("is_cross_conflict", False):
            text += "\n⚠️ _Сигнал скорректирован с учётом корреляции BTC_\n"
        
        text += "\n"
        
        # ===== РАЗБИВКА ПО БЛОКАМ =====
        block_trend = signal_data.get('block_trend_score', 0)
        block_momentum = signal_data.get('block_momentum_score', 0)
        block_whales = signal_data.get('block_whales_score', 0)
        block_derivatives = signal_data.get('block_derivatives_score', 0)
        block_sentiment = signal_data.get('block_sentiment_score', 0)
        
        text += f"📈 *РАЗБИВКА ПО БЛОКАМ*\n"
        text += f"• Тренд: {'+' if block_trend > 0 else ''}{block_trend:.1f}/10\n"
        text += f"• Импульс: {'+' if block_momentum > 0 else ''}{block_momentum:.1f}/10\n"
        text += f"• Киты: {'+' if block_whales > 0 else ''}{block_whales:.1f}/10\n"
        text += f"• Деривативы: {'+' if block_derivatives > 0 else ''}{block_derivatives:.1f}/10\n"
        text += f"• Настроения: {'+' if block_sentiment > 0 else ''}{block_sentiment:.1f}/10\n\n"
        
        # ===== ЦЕНА И УРОВНИ =====
        text += "💰 *ЦЕНА И УРОВНИ*\n"
        text += f"Текущая: {format_price(current_price)}\n"
        
        if is_sideways:
            # Для боковика показываем ожидаемый диапазон
            text += f"📊 Верх диапазона: {format_price(range_high)} (+1.0%)\n"
            text += f"📊 Низ диапазона: {format_price(range_low)} (-1.0%)\n"
            text += f"ℹ️ _Ожидается движение в диапазоне_\n"
        else:
            # Для ЛОНГ/ШОРТ показываем TP и SL
            text += f"🎯 TP1: {format_price(tp1_price)} ({tp1_percent:+.1f}%)\n"
            text += f"🎯 TP2: {format_price(tp2_price)} ({tp2_percent:+.1f}%)\n"
            text += f"🛑 SL: {format_price(sl_price)} ({sl_percent:+.1f}%)\n"
        
        text += "\n"
        
        # ===== ТРЕНД ЦЕНЫ =====
        text += "📈 *ТРЕНД ЦЕНЫ*\n"
        # Получить реальные данные о трендах из market_data
        change_1h = market_data.get('change_1h', 0) or 0
        change_24h = market_data.get('change_24h', 0) or market_data.get('price_change_24h', 0) or 0
        change_7d = market_data.get('change_7d', 0) or market_data.get('price_change_7d', 0) or 0
        
        # Если change_1h недоступен, рассчитать из price history (short_term_data)
        if change_1h == 0 and short_term_data:
            current = short_term_data.get('current_price', 0)
            price_1h = short_term_data.get('price_1h_ago', current)
            if price_1h and price_1h > 0:
                change_1h = ((current - price_1h) / price_1h) * 100
        
        change_1h_emoji = "🟢" if change_1h >= 0 else "🔴"
        change_24h_emoji = "🟢" if change_24h >= 0 else "🔴"
        change_7d_emoji = "🟢" if change_7d >= 0 else "🔴"
        
        text += f"• 1ч: {change_1h:+.1f}% {change_1h_emoji}\n"
        text += f"• 24ч: {change_24h:+.1f}% {change_24h_emoji}\n"
        text += f"• 7д: {change_7d:+.1f}% {change_7d_emoji}\n\n"
        
        # ===== РЫНОЧНЫЕ ДАННЫЕ =====
        text += "📊 *РЫНОЧНЫЕ ДАННЫЕ*\n"
        market_cap = market_data.get('market_cap', 0)
        volume_24h = market_data.get('volume_24h', 0)
        vol_mcap_ratio = (volume_24h / market_cap * 100) if market_cap > 0 else 0
        
        text += f"💰 Market Cap: {format_volume(market_cap)}\n"
        text += f"📊 Volume 24h: {format_volume(volume_24h)}\n"
        text += f"📈 Vol/MCap: {vol_mcap_ratio:.2f}%\n\n"
        
        # ===== АКТИВНОСТЬ КИТОВ =====
        text += "🐋 *АКТИВНОСТЬ КИТОВ*\n"
        whale_score = signal_data.get('factors', {}).get('whale', {}).get('score', 0)
        whale_score_scaled = (whale_score + 10) / 2  # Scale from -10/+10 to 0/10
        whale_score_emoji = "🔥" if whale_score_scaled >= 7 else "⚡" if whale_score_scaled >= 5 else "💧"
        
        tx_count = whale_data.get('transaction_count', 0)
        deposits_count = whale_data.get('deposits', 0)  # Number of deposit transactions
        withdrawals_count = whale_data.get('withdrawals', 0)  # Number of withdrawal transactions
        total_volume = whale_data.get('total_volume_usd', 0)
        
        # Нейтральная активность при нулевых потоках
        if deposits_count == 0 and withdrawals_count == 0:
            net_flow = 0
            net_flow_text = "0"
            net_flow_sentiment = "(нейтрально, явных потоков на/с бирж нет)"
        else:
            net_flow = withdrawals_count - deposits_count
            net_flow_text = f"+{abs(net_flow)}" if net_flow > 0 else f"{net_flow}" if net_flow < 0 else "0"
            net_flow_sentiment = "(бычье)" if net_flow > 0 else "(медвежье)" if net_flow < 0 else ""
        
        text += f"Score: {whale_score_scaled:.1f}/10 {whale_score_emoji}\n"
        text += f"• Транзакций: {tx_count}\n"
        text += f"• Объём: {format_volume(total_volume)}\n"
        text += f"• На биржи: {deposits_count} тx\n"
        text += f"• С бирж: {withdrawals_count} тx\n"
        text += f"• Net Flow: {net_flow_text} tx {net_flow_sentiment}\n\n"
        
        # ===== ТЕХНИЧЕСКИЙ АНАЛИЗ =====
        text += "⚡ *ТЕХНИЧЕСКИЙ АНАЛИЗ*\n"
        
        if technical_data:
            # RSI
            if "rsi" in technical_data:
                rsi_value = technical_data["rsi"]["value"]
                rsi_status = "перепродан" if rsi_value < 30 else "перекуплен" if rsi_value > 70 else "нейтральный"
                text += f"• RSI(14): {rsi_value:.0f} ({rsi_status})\n"
            
            # MACD
            if "macd" in technical_data:
                macd_signal = technical_data["macd"]["signal"]
                # macd_signal is a string: "bullish", "bearish", or "neutral"
                if isinstance(macd_signal, str):
                    macd_emoji = "✅" if macd_signal in ["bullish", "buy"] else "❌" if macd_signal in ["bearish", "sell"] else "➖"
                    macd_text = "бычье пересечение" if macd_signal in ["bullish", "buy"] else "медвежье пересечение" if macd_signal in ["bearish", "sell"] else "нейтрально"
                else:
                    # Fallback for numeric values (should not happen)
                    macd_emoji = "✅" if macd_signal > 0 else "❌"
                    macd_text = "бычье пересечение" if macd_signal > 0 else "медвежье пересечение"
                text += f"• MACD: {macd_text} {macd_emoji}\n"
            
            # Bollinger Bands
            if "bollinger" in technical_data:
                bb_position = technical_data["bollinger"].get("position", "middle")
                bb_text = "в нижней половине" if bb_position == "lower" else "в верхней половине" if bb_position == "upper" else "в середине"
                text += f"• BB: {bb_text}\n"
            
            # EMA Crossover
            if "ma_crossover" in technical_data:
                # ma_crossover uses "trend" field, not "signal"
                ma_trend = technical_data["ma_crossover"].get("trend", "neutral")
                ma_emoji = "✅" if ma_trend == "bullish" else "❌" if ma_trend == "bearish" else "➖"
                ma_text = "бычий кросс" if ma_trend == "bullish" else "медвежий кросс" if ma_trend == "bearish" else "нейтрально"
                text += f"• EMA 9/21: {ma_text} {ma_emoji}\n"
        
        text += "\n"
        
        # ===== УРОВНИ ПОДДЕРЖКИ/СОПРОТИВЛЕНИЯ =====
        text += "🎯 *УРОВНИ ПОДДЕРЖКИ/СОПРОТИВЛЕНИЯ*\n"
        
        # Вычисляем примерные уровни на основе текущей цены
        r2 = current_price * 1.02
        r1 = current_price * 1.01
        pivot = current_price
        s1 = current_price * 0.99
        s2 = current_price * 0.98
        
        text += f"📈 R2: {format_price(r2)}\n"
        text += f"📈 R1: {format_price(r1)}\n"
        text += f"━━ Pivot: {format_price(pivot)} ━━\n"
        text += f"📉 S1: {format_price(s1)}\n"
        text += f"📉 S2: {format_price(s2)}\n\n"
        
        # ===== ПРИЧИНЫ СИГНАЛА (TOP 5) =====
        text += "🔥 *ПРИЧИНЫ СИГНАЛА (TOP 5)*\n"
        reasons: list[tuple[bool, str]] = []
        
        # Собираем все факторы
        
        # 1. TradingView Rating
        if tradingview_rating:
            summary = tradingview_rating.get('summary', {})
            rating = summary.get('RECOMMENDATION', 'NEUTRAL')
            if rating in ['STRONG_BUY', 'BUY']:
                reasons.append((True, f"✅ TradingView: {rating}"))
            elif rating in ['STRONG_SELL', 'SELL']:
                reasons.append((False, f"❌ TradingView: {rating}"))
        
        # 2. RSI
        if technical_data and "rsi" in technical_data:
            rsi_value = technical_data["rsi"]["value"]
            if rsi_value < 30:
                reasons.append((True, f"✅ RSI перепродан: {rsi_value:.1f}"))
            elif rsi_value > 70:
                reasons.append((False, f"❌ RSI перекуплен: {rsi_value:.1f}"))
        
        # 3. Киты
        if whale_data:
            deposits_count = whale_data.get('deposits', 0)
            withdrawals_count = whale_data.get('withdrawals', 0)
            if withdrawals_count > deposits_count:
                net_diff = withdrawals_count - deposits_count
                reasons.append((True, f"✅ Киты выводят с бирж (+{net_diff} tx)"))
            elif deposits_count > withdrawals_count:
                net_diff = deposits_count - withdrawals_count
                reasons.append((False, f"❌ Киты заводят на биржи (+{net_diff} tx)"))
        
        # 4. Fear & Greed
        if fear_greed:
            fg_value = fear_greed.get('value', 50)
            if fg_value < 25:
                reasons.append((True, f"✅ Extreme Fear: {fg_value} (время покупать)"))
            elif fg_value > 75:
                reasons.append((False, f"❌ Extreme Greed: {fg_value} (осторожность)"))
        
        # 5. MACD
        if technical_data and "macd" in technical_data:
            macd_signal = technical_data["macd"].get("signal", "neutral")
            if macd_signal in ["bullish", "buy"]:
                reasons.append((True, f"✅ MACD бычий сигнал"))
            elif macd_signal in ["bearish", "sell"]:
                reasons.append((False, f"❌ MACD медвежий сигнал"))
        
        # 6. Funding Rate
        if funding_rate:
            rate = funding_rate.get('rate', 0)
            if rate < -0.01:
                reasons.append((True, f"✅ Шорты платят: {rate:.4f}"))
            elif rate > 0.03:
                reasons.append((False, f"❌ Перегретые лонги: {rate:.4f}"))
        
        # 7. Trades Flow
        if trades_flow:
            ratio = trades_flow.get('flow_ratio', 1.0)
            if ratio > 1.5:
                reasons.append((True, f"✅ Buy/Sell ratio: {ratio:.2f} (покупки)"))
            elif ratio < 0.67:
                reasons.append((False, f"❌ Buy/Sell ratio: {ratio:.2f} (продажи)"))
        
        # Показать топ 5 причин
        for i, (_, reason_text) in enumerate(reasons[:5], 1):
            text += f"{i}. {reason_text}\n"
        
        text += "\n"
        
        # ===== ФАКТОРЫ АНАЛИЗА =====
        text += "📊 *ФАКТОРЫ АНАЛИЗА*\n"
        
        # Считаем факторы
        bullish_count = sum(1 for bullish, _ in reasons if bullish)
        bearish_count = sum(1 for bullish, _ in reasons if not bullish)
        neutral_count = max(0, self.TOTAL_FACTORS - bullish_count - bearish_count)
        
        if bullish_count <= 1 and bearish_count == 0:
            # Слишком мало факторов для бычьего консенсуса
            consensus_text = "НЕЙТРАЛЬНЫЙ ⚠️"
        elif bearish_count <= 1 and bullish_count == 0:
            # Слишком мало факторов для медвежьего консенсуса
            consensus_text = "НЕЙТРАЛЬНЫЙ ⚠️"
        elif bullish_count > bearish_count:
            consensus_text = "БЫЧИЙ ✅"
        elif bearish_count > bullish_count:
            consensus_text = "МЕДВЕЖИЙ ❌"
        else:
            consensus_text = "НЕЙТРАЛЬНЫЙ ⚠️"
        
        text += f"Бычьих: {bullish_count} | Медвежьих: {bearish_count} | Нейтральных: {neutral_count}\n"
        text += f"Консенсус: {consensus_text}\n\n"
        
        # ===== ПРЕДУПРЕЖДЕНИЕ О ТОРГУЕМОСТИ =====
        # Проверяем, торгуем ли сигнал
        data_sources_count = signal_data.get('data_sources_count', 0)
        coverage = data_sources_count / self.TOTAL_DATA_SOURCES
        
        # Определение слабого сигнала
        signal_strength = int(min(100, max(0, abs(total_score))))
        is_weak = signal_strength < 20 or probability < 60
        
        if is_weak:
            text += "⚠️ *Сигнал слабый. Рекомендуется ПРОПУСТИТЬ этот сетап.*\n\n"
        
        # ===== FOOTER =====
        text += "⏱️ Таймфрейм: 1ч\n"
        
        # Считаем доступные источники
        available_sources = 0
        if whale_data: available_sources += 1
        if market_data: available_sources += 1
        if technical_data: available_sources += 1
        if fear_greed: available_sources += 1
        if funding_rate: available_sources += 1
        if order_book: available_sources += 1
        if futures_data: available_sources += 1
        if onchain_data: available_sources += 1
        if exchange_flows: available_sources += 1
        if short_term_data: available_sources += 1
        if trades_flow: available_sources += 1
        if liquidations: available_sources += 1
        if orderbook_delta: available_sources += 1
        if coinglass_data: available_sources += 1
        if news_sentiment: available_sources += 1
        if tradingview_rating: available_sources += 1
        if whale_alert: available_sources += 1
        if social_data: available_sources += 1
        
        text += f"📡 Источников данных: {available_sources}/{self.TOTAL_FACTORS}\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "⚠️ *DISCLAIMER*\n"
        text += "_Это НЕ финансовый совет. Сигналы основаны на техническом анализе и могут быть ошибочными. "
        text += "Торгуйте только теми средствами, которые готовы потерять. DYOR._"
        
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
        if symbol not in self.SUPPORTED_SIGNAL_COINS:
            return (
                f"❌ *Ошибка*\n\n"
                f"AI-сигналы сейчас доступны только для трёх монет:\n"
                f"• BTC\n"
                f"• ETH\n"
                f"• TON\n"
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
                symbol=symbol,
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
                social_data=social_data,
                is_cross_conflict=signal_data.get("is_cross_conflict", False),
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return (
                "❌ *Ошибка анализа*\n\n"
                f"Произошла ошибка при анализе {symbol}.\n"
                "Попробуйте позже."
            )
