"""
Deep Derivatives Analysis Module

Provides comprehensive derivatives market analysis including:
- Liquidation level clustering
- OI/Price correlation analysis
- Multi-exchange Long/Short ratios
- Funding rate trend analysis
- Basis (futures/spot spread) analysis
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class DeepDerivativesAnalyzer:
    """Deep derivatives analysis with multi-exchange data and advanced metrics."""
    
    def __init__(self):
        self._cache = {}
        self._cache_timestamps = {}
        
    def _get_cache(self, key: str, ttl_seconds: int) -> Optional[Dict]:
        """Get data from cache if still valid."""
        if key not in self._cache:
            return None
        
        age = datetime.now() - self._cache_timestamps.get(key, datetime.min)
        if age > timedelta(seconds=ttl_seconds):
            return None
        
        return self._cache[key]
    
    def _set_cache(self, key: str, value: Dict):
        """Set data in cache."""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()
    
    async def get_liquidation_levels(self, symbol: str) -> Optional[Dict]:
        """
        Get liquidation level clustering data from Bybit.
        
        Shows where liquidations are concentrated to identify potential
        price magnets or reversal zones.
        
        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            
        Returns:
            Dict:
            {
                "long_liquidations": [
                    {"price": 88000, "volume": 50000000},
                    {"price": 85000, "volume": 100000000},
                ],
                "short_liquidations": [
                    {"price": 92000, "volume": 75000000},
                    {"price": 95000, "volume": 120000000},
                ],
                "nearest_long_liq": 88000,
                "nearest_short_liq": 92000,
                "signal": "bullish" | "bearish" | "neutral"
            }
        """
        cache_key = f"liquidation_levels_{symbol}"
        cached = self._get_cache(cache_key, 300)  # 5 min cache
        if cached:
            return cached
        
        try:
            # Note: Bybit doesn't provide liquidation heatmap via public API
            # This would require scraping or premium data sources
            # For now, we'll estimate based on current price and typical leverage levels
            
            # Get current price from Bybit
            async with aiohttp.ClientSession() as session:
                url = "https://api.bybit.com/v5/market/tickers"
                params = {"category": "linear", "symbol": symbol}
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to get price for {symbol}")
                        return None
                    
                    data = await response.json()
                    if data.get("retCode") != 0:
                        logger.warning(f"Bybit API error: {data.get('retMsg')}")
                        return None
                    
                    tickers = data.get("result", {}).get("list", [])
                    if not tickers:
                        return None
                    
                    current_price = float(tickers[0].get("lastPrice", 0))
            
            if current_price == 0:
                return None
            
            # Estimate liquidation zones based on typical leverage levels
            # Adjust percentages based on coin price for better differentiation
            # For low-priced coins (< $10), use larger percentages for visibility
            if current_price < 10:
                # For altcoins, use larger percentage moves
                long_liq_multipliers = [0.75, 0.85, 0.92]    # 25%, 15%, 8% drops
                short_liq_multipliers = [1.25, 1.15, 1.08]   # 25%, 15%, 8% rises
            else:
                # For higher-priced coins, use standard percentages
                long_liq_multipliers = [0.80, 0.90, 0.95]    # 20%, 10%, 5% drops
                short_liq_multipliers = [1.20, 1.10, 1.05]   # 20%, 10%, 5% rises
            
            # Long liquidations occur below current price (5x, 10x, 20x leverage)
            long_liq_5x = current_price * long_liq_multipliers[0]
            long_liq_10x = current_price * long_liq_multipliers[1]
            long_liq_20x = current_price * long_liq_multipliers[2]
            
            # Short liquidations occur above current price
            short_liq_5x = current_price * short_liq_multipliers[0]
            short_liq_10x = current_price * short_liq_multipliers[1]
            short_liq_20x = current_price * short_liq_multipliers[2]
            
            # Estimate volumes (higher volume at safer leverage levels)
            long_liquidations = [
                {"price": round(long_liq_20x, 2), "volume": 50_000_000},
                {"price": round(long_liq_10x, 2), "volume": 100_000_000},
                {"price": round(long_liq_5x, 2), "volume": 150_000_000},
            ]
            
            short_liquidations = [
                {"price": round(short_liq_20x, 2), "volume": 50_000_000},
                {"price": round(short_liq_10x, 2), "volume": 100_000_000},
                {"price": round(short_liq_5x, 2), "volume": 150_000_000},
            ]
            
            # Determine signal based on nearest liquidation zones
            # If price is closer to short liquidations = bullish (shorts at risk)
            # If price is closer to long liquidations = bearish (longs at risk)
            distance_to_short = short_liq_20x - current_price
            distance_to_long = current_price - long_liq_20x
            
            if distance_to_short < distance_to_long * 0.5:
                signal = "bullish"  # Close to hunting shorts
            elif distance_to_long < distance_to_short * 0.5:
                signal = "bearish"  # Close to hunting longs
            else:
                signal = "neutral"
            
            result = {
                "long_liquidations": long_liquidations,
                "short_liquidations": short_liquidations,
                "nearest_long_liq": round(long_liq_20x, 2),
                "nearest_short_liq": round(short_liq_20x, 2),
                "current_price": round(current_price, 2),
                "signal": signal
            }
            
            self._set_cache(cache_key, result)
            logger.info(f"Analyzed liquidation levels for {symbol}: {signal}")
            return result
            
        except Exception as e:
            logger.error(f"Error in get_liquidation_levels for {symbol}: {e}")
            return None
    
    async def analyze_oi_price_correlation(self, symbol: str) -> Optional[Dict]:
        """
        Analyze correlation between Open Interest and Price changes.
        
        - OI up + Price up = New longs = Bullish
        - OI up + Price down = New shorts = Bearish
        - OI down + Price up = Shorts closing = Bullish
        - OI down + Price down = Longs closing = Bearish
        
        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            
        Returns:
            Dict:
            {
                "oi_change_24h": 5.2,
                "price_change_24h": 2.1,
                "correlation": "bullish",
                "interpretation": "New longs opening",
                "signal": "bullish"
            }
        """
        cache_key = f"oi_price_correlation_{symbol}"
        cached = self._get_cache(cache_key, 300)  # 5 min cache
        if cached:
            return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get current ticker data
                url = "https://api.bybit.com/v5/market/tickers"
                params = {"category": "linear", "symbol": symbol}
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to get ticker for {symbol}")
                        return None
                    
                    data = await response.json()
                    if data.get("retCode") != 0:
                        return None
                    
                    tickers = data.get("result", {}).get("list", [])
                    if not tickers:
                        return None
                    
                    ticker = tickers[0]
                    price_change_24h = float(ticker.get("price24hPcnt", 0)) * 100
                
                # Get Open Interest data
                url_oi = "https://api.bybit.com/v5/market/open-interest"
                params_oi = {
                    "category": "linear",
                    "symbol": symbol,
                    "intervalTime": "1d"
                }
                
                async with session.get(url_oi, params=params_oi) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to get OI for {symbol}")
                        # Use fallback with price-only signal
                        return self._create_price_only_signal(price_change_24h)
                    
                    data = await response.json()
                    if data.get("retCode") != 0:
                        return self._create_price_only_signal(price_change_24h)
                    
                    oi_list = data.get("result", {}).get("list", [])
                    if len(oi_list) < 2:
                        return self._create_price_only_signal(price_change_24h)
                    
                    # Calculate OI change
                    current_oi = float(oi_list[0].get("openInterest", 0))
                    prev_oi = float(oi_list[1].get("openInterest", 0))
                    
                    if prev_oi == 0:
                        return self._create_price_only_signal(price_change_24h)
                    
                    oi_change_24h = ((current_oi - prev_oi) / prev_oi) * 100
            
            # Analyze correlation
            oi_up = oi_change_24h > 1.0  # OI increased by >1%
            oi_down = oi_change_24h < -1.0  # OI decreased by >1%
            price_up = price_change_24h > 0.5  # Price increased by >0.5%
            price_down = price_change_24h < -0.5  # Price decreased by >0.5%
            
            if oi_up and price_up:
                correlation = "bullish"
                interpretation = "New longs opening"
                signal = "bullish"
            elif oi_up and price_down:
                correlation = "bearish"
                interpretation = "New shorts opening"
                signal = "bearish"
            elif oi_down and price_up:
                correlation = "bullish"
                interpretation = "Shorts closing"
                signal = "bullish"
            elif oi_down and price_down:
                correlation = "bearish"
                interpretation = "Longs closing"
                signal = "bearish"
            else:
                correlation = "neutral"
                interpretation = "Mixed signals"
                signal = "neutral"
            
            result = {
                "oi_change_24h": round(oi_change_24h, 2),
                "price_change_24h": round(price_change_24h, 2),
                "correlation": correlation,
                "interpretation": interpretation,
                "signal": signal
            }
            
            self._set_cache(cache_key, result)
            logger.info(f"Analyzed OI/Price correlation for {symbol}: {signal}")
            return result
            
        except Exception as e:
            logger.error(f"Error in analyze_oi_price_correlation for {symbol}: {e}")
            return None
    
    def _create_price_only_signal(self, price_change_24h: float) -> Dict:
        """Create a simplified signal when OI data is unavailable."""
        if price_change_24h > 1.0:
            signal = "bullish"
            interpretation = "Price rising"
        elif price_change_24h < -1.0:
            signal = "bearish"
            interpretation = "Price falling"
        else:
            signal = "neutral"
            interpretation = "Price stable"
        
        return {
            "oi_change_24h": 0.0,
            "price_change_24h": round(price_change_24h, 2),
            "correlation": "neutral",
            "interpretation": interpretation,
            "signal": signal
        }
    
    async def get_ls_ratio_by_exchange(self, symbol: str) -> Optional[Dict]:
        """
        Get Long/Short ratio from multiple exchanges.
        
        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            
        Returns:
            Dict:
            {
                "bybit": {"long": 55, "short": 45, "ratio": 1.22},
                "binance": {"long": 52, "short": 48, "ratio": 1.08},
                "okx": {"long": 58, "short": 42, "ratio": 1.38},
                "average_ratio": 1.23,
                "signal": "bullish" | "bearish" | "neutral"
            }
        """
        cache_key = f"ls_ratio_multi_{symbol}"
        cached = self._get_cache(cache_key, 300)  # 5 min cache
        if cached:
            return cached
        
        try:
            # Get data from Bybit (other exchanges require API keys or are not publicly available)
            bybit_data = await self._get_bybit_ls_ratio(symbol)
            
            if not bybit_data:
                return None
            
            # For now, we only have Bybit data
            # In production, you would add Binance and OKX if their APIs are accessible
            result = {
                "bybit": bybit_data,
                "binance": None,  # Not available without API key
                "okx": None,  # Not available without API key
                "average_ratio": bybit_data["ratio"],
                "signal": self._interpret_ls_ratio(bybit_data["ratio"])
            }
            
            self._set_cache(cache_key, result)
            logger.info(f"Analyzed L/S ratios for {symbol}: {result['signal']}")
            return result
            
        except Exception as e:
            logger.error(f"Error in get_ls_ratio_by_exchange for {symbol}: {e}")
            return None
    
    async def _get_bybit_ls_ratio(self, symbol: str) -> Optional[Dict]:
        """Get Long/Short ratio from Bybit."""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.bybit.com/v5/market/account-ratio"
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "period": "5min"
                }
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to get L/S ratio from Bybit for {symbol}")
                        return None
                    
                    data = await response.json()
                    if data.get("retCode") != 0:
                        logger.warning(f"Bybit L/S API error: {data.get('retMsg')}")
                        return None
                    
                    ratio_list = data.get("result", {}).get("list", [])
                    if not ratio_list:
                        return None
                    
                    # Get most recent data
                    latest = ratio_list[0]
                    buy_ratio = float(latest.get("buyRatio", 0.5))
                    sell_ratio = float(latest.get("sellRatio", 0.5))
                    
                    # Convert to percentages
                    long_pct = round(buy_ratio * 100, 0)
                    short_pct = round(sell_ratio * 100, 0)
                    
                    # Calculate ratio
                    if sell_ratio > 0:
                        ratio = buy_ratio / sell_ratio
                    else:
                        ratio = 2.0  # Default if no shorts
                    
                    return {
                        "long": int(long_pct),
                        "short": int(short_pct),
                        "ratio": round(ratio, 2)
                    }
                    
        except Exception as e:
            logger.error(f"Error getting Bybit L/S ratio: {e}")
            return None
    
    def _interpret_ls_ratio(self, ratio: float) -> str:
        """Interpret Long/Short ratio signal."""
        if ratio > 1.5:
            return "bearish"  # Too many longs, potential reversal
        elif ratio < 0.7:
            return "bullish"  # Too many shorts, potential reversal
        elif ratio > 1.1:
            return "bullish"  # Moderately bullish
        elif ratio < 0.9:
            return "bearish"  # Moderately bearish
        else:
            return "neutral"
    
    async def get_funding_rate_history(self, symbol: str, periods: int = 24) -> Optional[Dict]:
        """
        Get funding rate history and trend analysis.
        
        - Rising trend = Many longs = Potential reversal
        - Falling trend = Many shorts = Potential reversal
        - Neutral = Healthy market
        
        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            periods: Number of 8-hour periods to analyze
            
        Returns:
            Dict:
            {
                "current": 0.01,
                "average_24h": 0.008,
                "trend": "rising" | "falling" | "stable",
                "extreme": False,
                "signal": "bullish" | "bearish" | "neutral"
            }
        """
        cache_key = f"funding_rate_history_{symbol}"
        cached = self._get_cache(cache_key, 300)  # 5 min cache
        if cached:
            return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.bybit.com/v5/market/funding/history"
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "limit": min(periods, 200)
                }
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to get funding rate for {symbol}")
                        return None
                    
                    data = await response.json()
                    if data.get("retCode") != 0:
                        logger.warning(f"Bybit funding rate API error: {data.get('retMsg')}")
                        return None
                    
                    history = data.get("result", {}).get("list", [])
                    if not history:
                        return None
                    
                    # Extract rates
                    rates = [float(item.get("fundingRate", 0)) for item in history]
                    
                    if not rates:
                        return None
                    
                    current_rate = rates[0] * 100  # Convert to percentage
                    avg_rate = sum(rates) / len(rates) * 100
                    
                    # Determine trend (compare first half vs second half)
                    mid = len(rates) // 2
                    recent_avg = sum(rates[:mid]) / mid if mid > 0 else current_rate / 100
                    older_avg = sum(rates[mid:]) / (len(rates) - mid) if len(rates) > mid else current_rate / 100
                    
                    if recent_avg > older_avg * 1.2:
                        trend = "rising"
                    elif recent_avg < older_avg * 0.8:
                        trend = "falling"
                    else:
                        trend = "stable"
                    
                    # Check for extreme rates
                    extreme = abs(current_rate) > 0.1  # >0.1% is extreme
                    
                    # Determine signal
                    # Positive funding = Longs pay shorts = Bullish sentiment
                    # Negative funding = Shorts pay longs = Bearish sentiment
                    # Extreme positive = Too bullish = Reversal risk = Bearish signal
                    # Extreme negative = Too bearish = Reversal risk = Bullish signal
                    if extreme:
                        if current_rate > 0.1:
                            signal = "bearish"  # Too many longs
                        else:
                            signal = "bullish"  # Too many shorts
                    else:
                        if trend == "rising" and current_rate > 0.03:
                            signal = "bearish"  # Increasing bullish sentiment = reversal risk
                        elif trend == "falling" and current_rate < -0.03:
                            signal = "bullish"  # Increasing bearish sentiment = reversal risk
                        else:
                            signal = "neutral"
                    
                    result = {
                        "current": round(current_rate, 4),
                        "average_24h": round(avg_rate, 4),
                        "trend": trend,
                        "extreme": extreme,
                        "signal": signal
                    }
                    
                    self._set_cache(cache_key, result)
                    logger.info(f"Analyzed funding rate for {symbol}: {signal}")
                    return result
                    
        except Exception as e:
            logger.error(f"Error in get_funding_rate_history for {symbol}: {e}")
            return None
    
    async def get_basis(self, symbol: str) -> Optional[Dict]:
        """
        Calculate basis (futures-spot spread).
        
        - Contango (futures > spot) = Bullish sentiment
        - Backwardation (futures < spot) = Bearish sentiment
        
        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            
        Returns:
            Dict:
            {
                "spot_price": 90000,
                "futures_price": 90270,
                "basis": 0.3,
                "basis_type": "contango" | "backwardation",
                "signal": "bullish" | "bearish" | "neutral"
            }
        """
        cache_key = f"basis_{symbol}"
        cached = self._get_cache(cache_key, 300)  # 5 min cache
        if cached:
            return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get spot price
                url_spot = "https://api.bybit.com/v5/market/tickers"
                params_spot = {"category": "spot", "symbol": symbol}
                
                # Get futures price
                url_futures = "https://api.bybit.com/v5/market/tickers"
                params_futures = {"category": "linear", "symbol": symbol}
                
                # Fetch both in parallel
                async with session.get(url_spot, params=params_spot) as resp_spot, \
                           session.get(url_futures, params=params_futures) as resp_futures:
                    
                    if resp_spot.status != 200 or resp_futures.status != 200:
                        logger.warning(f"Failed to get prices for basis calculation: {symbol}")
                        return None
                    
                    data_spot = await resp_spot.json()
                    data_futures = await resp_futures.json()
                    
                    if data_spot.get("retCode") != 0 or data_futures.get("retCode") != 0:
                        logger.warning(f"Bybit API error in basis calculation")
                        return None
                    
                    # Extract prices
                    spot_tickers = data_spot.get("result", {}).get("list", [])
                    futures_tickers = data_futures.get("result", {}).get("list", [])
                    
                    if not spot_tickers or not futures_tickers:
                        logger.warning(f"No ticker data for basis calculation: {symbol}")
                        return None
                    
                    spot_price = float(spot_tickers[0].get("lastPrice", 0))
                    futures_price = float(futures_tickers[0].get("lastPrice", 0))
                    
                    if spot_price == 0:
                        return None
                    
                    # Calculate basis
                    basis_value = ((futures_price - spot_price) / spot_price) * 100
                    
                    # Determine type and signal
                    if basis_value > 0.1:
                        basis_type = "contango"
                        signal = "bullish"
                    elif basis_value < -0.1:
                        basis_type = "backwardation"
                        signal = "bearish"
                    else:
                        basis_type = "neutral"
                        signal = "neutral"
                    
                    result = {
                        "spot_price": round(spot_price, 2),
                        "futures_price": round(futures_price, 2),
                        "basis": round(basis_value, 3),
                        "basis_type": basis_type,
                        "signal": signal
                    }
                    
                    self._set_cache(cache_key, result)
                    logger.info(f"Analyzed basis for {symbol}: {signal}")
                    return result
                    
        except Exception as e:
            logger.error(f"Error in get_basis for {symbol}: {e}")
            return None
