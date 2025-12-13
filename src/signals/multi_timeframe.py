"""
Multi-Timeframe Analysis Module.

Fetches candles from multiple timeframes (15m, 1h, 4h) from Bybit API
and calculates consensus across timeframes.
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import aiohttp

from signals.indicators import calculate_rsi, calculate_macd

logger = logging.getLogger(__name__)


class MultiTimeframeAnalyzer:
    """Analyzer for multi-timeframe technical analysis."""
    
    # Bybit API endpoints
    BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"
    
    # Timeframe mapping to Bybit intervals
    TIMEFRAME_MAPPING = {
        "15m": "15",
        "1h": "60",
        "4h": "240"
    }
    
    # Cache TTL for candles
    CACHE_TTL_SECONDS = 300  # 5 minutes
    
    def __init__(self):
        """Initialize multi-timeframe analyzer."""
        self._cache = {}
        self._cache_timestamps = {}
    
    def _get_cache_key(self, symbol: str, timeframe: str) -> str:
        """Generate cache key."""
        return f"candles_{symbol}_{timeframe}"
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache is still valid."""
        if key not in self._cache:
            return False
        
        age = datetime.now() - self._cache_timestamps.get(key, datetime.min)
        return age.total_seconds() < self.CACHE_TTL_SECONDS
    
    async def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100
    ) -> Optional[List[Dict]]:
        """
        Fetch OHLCV candles from Bybit API.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            timeframe: Timeframe ("15m", "1h", "4h")
            limit: Number of candles to fetch
            
        Returns:
            List of candles or None if failed
            Each candle: {
                "timestamp": int,
                "open": float,
                "high": float,
                "low": float,
                "close": float,
                "volume": float
            }
        """
        cache_key = self._get_cache_key(symbol, timeframe)
        
        # Check cache
        if self._is_cache_valid(cache_key):
            logger.debug(f"Using cached candles for {symbol} {timeframe}")
            return self._cache[cache_key]
        
        # Validate timeframe
        if timeframe not in self.TIMEFRAME_MAPPING:
            logger.error(f"Invalid timeframe: {timeframe}")
            return None
        
        interval = self.TIMEFRAME_MAPPING[timeframe]
        
        try:
            params = {
                "category": "spot",
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BYBIT_KLINE_URL, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Bybit API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if data.get("retCode") != 0:
                        logger.error(f"Bybit API error: {data.get('retMsg')}")
                        return None
                    
                    # Parse candles
                    result = data.get("result", {})
                    raw_list = result.get("list", [])
                    
                    if not raw_list:
                        logger.warning(f"No candles returned for {symbol} {timeframe}")
                        return None
                    
                    candles = []
                    for item in raw_list:
                        # Bybit returns: [timestamp, open, high, low, close, volume, turnover]
                        try:
                            candle = {
                                "timestamp": int(item[0]),
                                "open": float(item[1]),
                                "high": float(item[2]),
                                "low": float(item[3]),
                                "close": float(item[4]),
                                "volume": float(item[5])
                            }
                            candles.append(candle)
                        except (IndexError, ValueError) as e:
                            logger.warning(f"Failed to parse candle: {e}")
                            continue
                    
                    # Bybit returns newest first, reverse to get chronological order
                    candles.reverse()
                    
                    # Cache the result
                    self._cache[cache_key] = candles
                    self._cache_timestamps[cache_key] = datetime.now()
                    
                    logger.info(f"Fetched {len(candles)} candles for {symbol} {timeframe}")
                    return candles
        
        except Exception as e:
            logger.error(f"Error fetching candles for {symbol} {timeframe}: {e}")
            return None
    
    def calculate_timeframe_indicators(
        self,
        candles: List[Dict]
    ) -> Optional[Dict]:
        """
        Calculate technical indicators for a timeframe.
        
        Args:
            candles: List of OHLCV candles
            
        Returns:
            Dict with indicators or None if failed
        """
        if not candles or len(candles) < 30:
            return None
        
        try:
            # Extract price arrays
            closes = [c["close"] for c in candles]
            highs = [c["high"] for c in candles]
            lows = [c["low"] for c in candles]
            
            # Calculate RSI
            rsi = calculate_rsi(closes, period=14)
            
            # Calculate MACD
            macd = calculate_macd(closes)
            
            # Calculate EMA crossover (12/26)
            ema_12 = self._calculate_ema(closes, 12)
            ema_26 = self._calculate_ema(closes, 26)
            
            # Determine direction based on indicators
            direction = self._determine_direction(rsi, macd, ema_12, ema_26)
            
            return {
                "rsi": rsi.value if rsi else None,
                "macd": {
                    "macd_line": macd.macd_line if macd else None,
                    "signal_line": macd.signal_line if macd else None,
                    "histogram": macd.histogram if macd else None
                } if macd else None,
                "ema_12": ema_12,
                "ema_26": ema_26,
                "direction": direction,
                "last_close": closes[-1]
            }
        
        except Exception as e:
            logger.error(f"Error calculating timeframe indicators: {e}")
            return None
    
    def _calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return None
        
        try:
            multiplier = 2 / (period + 1)
            ema = prices[0]
            
            for price in prices[1:]:
                ema = (price * multiplier) + (ema * (1 - multiplier))
            
            return ema
        except Exception:
            return None
    
    def _determine_direction(
        self,
        rsi,
        macd,
        ema_12: Optional[float],
        ema_26: Optional[float]
    ) -> str:
        """
        Determine direction based on indicators.
        
        Returns:
            "bullish", "bearish", or "neutral"
        """
        bullish_signals = 0
        bearish_signals = 0
        
        # RSI signals
        if rsi:
            if rsi.value < 30:
                bullish_signals += 1
            elif rsi.value > 70:
                bearish_signals += 1
            elif rsi.value > 50:
                bullish_signals += 0.5
            else:
                bearish_signals += 0.5
        
        # MACD signals
        if macd:
            if macd.histogram > 0:
                bullish_signals += 1
            else:
                bearish_signals += 1
        
        # EMA crossover signals
        if ema_12 is not None and ema_26 is not None:
            if ema_12 > ema_26:
                bullish_signals += 1
            else:
                bearish_signals += 1
        
        # Determine final direction
        if bullish_signals > bearish_signals + 0.5:
            return "bullish"
        elif bearish_signals > bullish_signals + 0.5:
            return "bearish"
        return "neutral"
    
    async def analyze_multi_timeframe(
        self,
        symbol: str
    ) -> Optional[Dict]:
        """
        Analyze multiple timeframes and determine consensus.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            
        Returns:
            Dict with multi-timeframe analysis results
        """
        timeframes = ["15m", "1h", "4h"]
        results = {}
        
        # Fetch and analyze each timeframe
        for tf in timeframes:
            candles = await self.fetch_candles(symbol, tf, limit=100)
            if candles:
                indicators = self.calculate_timeframe_indicators(candles)
                if indicators:
                    results[tf] = indicators
        
        if not results:
            logger.warning(f"No timeframe data available for {symbol}")
            return None
        
        # Calculate consensus
        directions = [results[tf]["direction"] for tf in results.keys()]
        
        bullish_count = directions.count("bullish")
        bearish_count = directions.count("bearish")
        neutral_count = directions.count("neutral")
        
        total_count = len(directions)
        
        # Determine consensus direction
        if bullish_count >= 2:
            consensus_direction = "bullish"
            consensus_strength = bullish_count / total_count
        elif bearish_count >= 2:
            consensus_direction = "bearish"
            consensus_strength = bearish_count / total_count
        else:
            consensus_direction = "neutral"
            consensus_strength = max(bullish_count, bearish_count, neutral_count) / total_count
        
        # Format consensus text
        if consensus_strength == 1.0:
            consensus_text = "3/3 согласие"
        elif consensus_strength >= 0.66:
            consensus_text = "2/3 согласие"
        else:
            consensus_text = "Нет согласия"
        
        return {
            "timeframes": results,
            "consensus": {
                "direction": consensus_direction,
                "strength": consensus_strength,
                "text": consensus_text,
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "neutral_count": neutral_count
            }
        }
