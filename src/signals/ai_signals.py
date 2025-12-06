"""
AI Signals - анализ и прогнозирование движения цен на основе данных китов и рынка.

Анализирует активность китов и рыночные данные для прогнозирования движения цены на ближайший час.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import aiohttp
import asyncio

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
    
    # Веса для 10-факторной системы (100% total)
    WHALE_WEIGHT = 0.12      # 12%
    TREND_WEIGHT = 0.15      # 15%
    MOMENTUM_WEIGHT = 0.12   # 12%
    VOLATILITY_WEIGHT = 0.08 # 8%
    VOLUME_WEIGHT = 0.10     # 10%
    MARKET_WEIGHT = 0.08     # 8%
    ORDERBOOK_WEIGHT = 0.10  # 10%
    DERIVATIVES_WEIGHT = 0.10 # 10%
    ONCHAIN_WEIGHT = 0.08    # 8%
    SENTIMENT_WEIGHT = 0.07  # 7%
    
    # Scaling factor for final score calculation
    SCORE_SCALE_FACTOR = 10  # Scale weighted sum from -10/+10 to -100/+100
    
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
        
        logger.info("AISignalAnalyzer initialized with 10-factor system")
    
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
    
    async def get_price_history(self, symbol: str, days: int = 1) -> Optional[List[float]]:
        """
        Получение исторических цен для расчёта индикаторов.
        Использует CoinGecko API: /coins/{id}/market_chart
        
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
                            logger.info(f"Fetched {len(prices)} price points for {symbol}")
                            return prices
                    elif response.status == 429:
                        logger.warning(f"CoinGecko rate limit reached for {symbol}")
                        return None
                    else:
                        logger.warning(f"Failed to fetch price history for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting price history for {symbol}: {e}")
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
        2. Score adjustment = total_score * 0.3 (макс ±30%)
        3. Data quality bonus = (sources/10) * 10% (макс +10%)
        4. Consensus bonus = (consensus/10) * 10% (макс +10%)
        
        Max probability = 50 + 30 + 10 + 10 = 100%
        Min probability = 50 - 30 = 20%
        """
        # Base probability
        base = 50.0
        
        # Score adjustment (±30%)
        score_adj = (total_score / 100) * 30
        
        # Data quality (0-10%)
        data_quality = data_sources_count / 10
        data_bonus = data_quality * 10
        
        # Consensus bonus (0-10%)
        consensus_ratio = consensus_count / total_factors
        consensus_bonus = consensus_ratio * 10
        
        # Direction
        if total_score > 0:
            direction = "up"
            probability = base + score_adj + data_bonus + consensus_bonus
        else:
            direction = "down"
            probability = base - score_adj + data_bonus + consensus_bonus
        
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
                        exchange_flows: Optional[Dict] = None, ohlcv_data: Optional[List] = None) -> Dict:
        """
        10-факторная система расчёта сигнала.
        
        Веса факторов (100% total):
        - Whale Score (12%): Whale transactions + Exchange flows
        - Trend Score (15%): RSI + MACD + MA Crossover
        - Momentum Score (12%): Stoch RSI + MFI + ROC + Williams %R
        - Volatility Score (8%): Bollinger Bands + ATR + Keltner
        - Volume Score (10%): OBV + VWAP + Volume SMA
        - Market Score (8%): Price change + Volume
        - Order Book Score (10%): Bid/Ask imbalance + Spread
        - Derivatives Score (10%): OI + Long/Short + Funding
        - On-Chain Score (8%): Mempool + Hashrate
        - Sentiment Score (7%): Fear & Greed Index
        
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
            ohlcv_data: OHLCV candles (optional)
            
        Returns:
            Dict with analysis results
        """
        # Calculate 10 factor scores
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
        
        # Calculate weighted total score
        total_score = (
            whale_score * self.WHALE_WEIGHT +
            trend_score * self.TREND_WEIGHT +
            momentum_score * self.MOMENTUM_WEIGHT +
            volatility_score * self.VOLATILITY_WEIGHT +
            volume_score * self.VOLUME_WEIGHT +
            market_score * self.MARKET_WEIGHT +
            orderbook_score * self.ORDERBOOK_WEIGHT +
            derivatives_score * self.DERIVATIVES_WEIGHT +
            onchain_score * self.ONCHAIN_WEIGHT +
            sentiment_score * self.SENTIMENT_WEIGHT
        ) * self.SCORE_SCALE_FACTOR  # Scale to -100 to +100
        
        # Count consensus
        all_scores = {
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
        }
        consensus_data = self.count_consensus(all_scores)
        
        # Count available data sources
        data_sources_available = sum([
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
        ])
        
        # Calculate probability
        probability_data = self.calculate_probability(
            total_score=total_score,
            data_sources_count=data_sources_available,
            consensus_count=consensus_data["bullish_count"] if total_score > 0 else consensus_data["bearish_count"],
            total_factors=10
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
        exchange_flows: Optional[Dict] = None
    ) -> str:
        """
        Форматирование сообщения с AI сигналом (10-факторная система).
        
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
        text += f"✅ Консенсус: {consensus_count}/10 факторов {consensus_text}\n"
        text += f"📡 Данные: {signal_data.get('data_sources_count', 0)}/10 источников\n\n"
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
            fg_class = fear_greed["classification"]
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
                mempool_status = onchain_data.get("mempool_status", "unknown")
                mempool_size = onchain_data.get("mempool_size", 0)
                text += f"• Mempool: {mempool_status.capitalize()} ({mempool_size:,} tx)\n"
            
            text += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Breakdown сигнала (10-факторная система)
        text += "🎯 *Breakdown сигнала (10 факторов):*\n\n"
        text += "📊 *Основные факторы:*\n"
        text += f"├─ 🐋 Whale Score ({self.WHALE_WEIGHT:.0%}): {signal_data['whale_score']:+.1f}\n"
        text += f"├─ 📈 Trend Score ({self.TREND_WEIGHT:.0%}): {signal_data['trend_score']:+.1f}\n"
        text += f"├─ 💪 Momentum Score ({self.MOMENTUM_WEIGHT:.0%}): {signal_data['momentum_score']:+.1f}\n"
        text += f"└─ 📉 Volatility Score ({self.VOLATILITY_WEIGHT:.0%}): {signal_data['volatility_score']:+.1f}\n\n"
        
        text += "📊 *Объём & Рынок:*\n"
        text += f"├─ 📊 Volume Score ({self.VOLUME_WEIGHT:.0%}): {signal_data['volume_score']:+.1f}\n"
        text += f"└─ 💹 Market Score ({self.MARKET_WEIGHT:.0%}): {signal_data['market_score']:+.1f}\n\n"
        
        text += "📊 *Деривативы & Настроения:*\n"
        text += f"├─ 📖 Order Book ({self.ORDERBOOK_WEIGHT:.0%}): {signal_data['orderbook_score']:+.1f}\n"
        text += f"├─ 🔮 Derivatives ({self.DERIVATIVES_WEIGHT:.0%}): {signal_data['derivatives_score']:+.1f}\n"
        text += f"├─ ⛓️ On-Chain ({self.ONCHAIN_WEIGHT:.0%}): {signal_data['onchain_score']:+.1f}\n"
        text += f"└─ 😱 Sentiment ({self.SENTIMENT_WEIGHT:.0%}): {signal_data['sentiment_score']:+.1f}\n\n"
        
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
            
            # Log data availability
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
            }
            available_count = sum(1 for v in data_sources_available.values() if v)
            logger.info(f"Data sources available: {available_count}/10 for {symbol}")
            
            # Calculate signal with all available data
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
                ohlcv_data=ohlcv_data
            )
            
            # Format message with all data
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
                exchange_flows=exchange_flows
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return (
                "❌ *Ошибка анализа*\n\n"
                f"Произошла ошибка при анализе {symbol}.\n"
                "Попробуйте позже."
            )
