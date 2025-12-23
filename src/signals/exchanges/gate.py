"""
Gate.io Exchange Client - резервный источник данных #2.
"""

import logging
from typing import List, Dict, Optional
import aiohttp
import asyncio

from signals.rate_limiter import ExchangeRateLimiters

logger = logging.getLogger(__name__)


class GateClient:
    """
    Gate.io exchange client для получения данных о фьючерсах и спотовых рынках.
    """
    
    BASE_URL = "https://api.gateio.ws/api/v4"
    
    def __init__(self):
        self.rate_limiter = ExchangeRateLimiters.get_limiter("gate", requests_per_second=10)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a rate-limited request to Gate.io API.
        
        Args:
            endpoint: API endpoint (e.g., "/spot/candlesticks")
            params: Query parameters
            
        Returns:
            JSON response or None on error
        """
        await self.rate_limiter.acquire()
        await self._ensure_session()
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(f"Gate HTTP error: {resp.status}")
        except asyncio.TimeoutError:
            logger.warning(f"Gate request timeout: {endpoint}")
        except Exception as e:
            logger.error(f"Gate request error: {e}", exc_info=True)
        
        return None
    
    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List[Dict]:
        """
        Get OHLCV candlestick data.
        
        Args:
            symbol: Trading pair (e.g., "BTC_USDT")
            timeframe: Timeframe (e.g., "1m", "1h", "4h", "1d")
            limit: Number of candles to fetch (max 1000)
            
        Returns:
            List of OHLCV dicts with keys: timestamp, open, high, low, close, volume
        """
        # Convert timeframe to Gate format
        tf_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1H": "1h", "4H": "4h", "1D": "1d"
        }
        interval = tf_map.get(timeframe, "1h")
        
        data = await self._request(
            "/spot/candlesticks",
            params={
                "currency_pair": symbol,
                "interval": interval,
                "limit": str(limit)
            }
        )
        
        if not data or not isinstance(data, list):
            return []
        
        # Convert Gate format to standard format
        candles = []
        for item in data:
            try:
                candles.append({
                    "timestamp": int(item[0]) * 1000,  # Gate uses seconds
                    "open": float(item[5]),
                    "high": float(item[3]),
                    "low": float(item[4]),
                    "close": float(item[2]),
                    "volume": float(item[1]),
                })
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse Gate candle: {e}")
                continue
        
        return candles
    
    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Get current ticker data.
        
        Args:
            symbol: Trading pair (e.g., "BTC_USDT")
            
        Returns:
            Dict with keys: last_price, bid, ask, volume_24h, change_24h
        """
        data = await self._request(
            "/spot/tickers",
            params={"currency_pair": symbol}
        )
        
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        
        ticker = data[0]
        try:
            last_price = float(ticker.get("last", 0))
            bid = float(ticker.get("highest_bid", 0))
            ask = float(ticker.get("lowest_ask", 0))
            
            # Calculate spread percentage
            spread = 0
            if bid > 0 and ask > 0:
                spread = ((ask - bid) / bid) * 100
            
            return {
                "last_price": last_price,
                "bid": bid,
                "ask": ask,
                "volume_24h": float(ticker.get("base_volume", 0)),
                "change_24h": float(ticker.get("change_percentage", 0)),
                "spread_pct": spread,
            }
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse Gate ticker: {e}")
            return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Get current funding rate for perpetual futures.
        
        Args:
            symbol: Trading pair for futures (e.g., "BTC_USDT")
            
        Returns:
            Current funding rate as float (e.g., 0.0001 = 0.01%)
        """
        data = await self._request(
            "/futures/usdt/contracts/" + symbol
        )
        
        if not data:
            return None
        
        try:
            return float(data.get("funding_rate", 0))
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse Gate funding rate: {e}")
            return None
    
    async def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """
        Get open interest data.
        
        Args:
            symbol: Trading pair for futures (e.g., "BTC_USDT")
            
        Returns:
            Dict with keys: oi (open interest in contracts), oi_usd
        """
        data = await self._request(
            "/futures/usdt/contracts/" + symbol
        )
        
        if not data:
            return None
        
        try:
            # Gate doesn't provide direct OI in API response, need separate endpoint
            # For now, return placeholder
            return {
                "oi": 0,
                "oi_usd": 0,
            }
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse Gate open interest: {e}")
            return None
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Optional[Dict]:
        """
        Get orderbook data.
        
        Args:
            symbol: Trading pair (e.g., "BTC_USDT")
            depth: Orderbook depth (max 100)
            
        Returns:
            Dict with keys: bids (list of [price, size]), asks (list of [price, size])
        """
        data = await self._request(
            "/spot/order_book",
            params={
                "currency_pair": symbol,
                "limit": str(min(depth, 100))
            }
        )
        
        if not data:
            return None
        
        try:
            return {
                "bids": [[float(b[0]), float(b[1])] for b in data.get("bids", [])],
                "asks": [[float(a[0]), float(a[1])] for a in data.get("asks", [])],
            }
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse Gate orderbook: {e}")
            return None
    
    async def close(self):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
