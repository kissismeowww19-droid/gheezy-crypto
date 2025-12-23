"""
Bybit Exchange Client - резервный источник данных #1.
"""

import logging
from typing import List, Dict, Optional
import aiohttp
import asyncio

from signals.rate_limiter import ExchangeRateLimiters

logger = logging.getLogger(__name__)


class BybitClient:
    """
    Bybit exchange client для получения данных о фьючерсах и спотовых рынках.
    """
    
    BASE_URL = "https://api.bybit.com/v5"
    
    def __init__(self):
        self.rate_limiter = ExchangeRateLimiters.get_limiter("bybit", requests_per_second=10)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a rate-limited request to Bybit API.
        
        Args:
            endpoint: API endpoint (e.g., "/market/kline")
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
                    data = await resp.json()
                    if data.get("retCode") == 0:
                        return data.get("result")
                    else:
                        logger.warning(f"Bybit API error: {data.get('retMsg')}")
                else:
                    logger.warning(f"Bybit HTTP error: {resp.status}")
        except asyncio.TimeoutError:
            logger.warning(f"Bybit request timeout: {endpoint}")
        except Exception as e:
            logger.error(f"Bybit request error: {e}", exc_info=True)
        
        return None
    
    async def get_ohlcv(self, symbol: str, timeframe: str = "60", limit: int = 100) -> List[Dict]:
        """
        Get OHLCV candlestick data.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            timeframe: Timeframe in minutes (e.g., "1", "60", "240")
            limit: Number of candles to fetch (max 200)
            
        Returns:
            List of OHLCV dicts with keys: timestamp, open, high, low, close, volume
        """
        # Convert timeframe to Bybit format (in minutes)
        tf_map = {
            "1m": "1", "5m": "5", "15m": "15", "30m": "30",
            "1H": "60", "4H": "240", "1D": "D"
        }
        interval = tf_map.get(timeframe, "60")
        
        data = await self._request(
            "/market/kline",
            params={
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": str(limit)
            }
        )
        
        if not data or not data.get("list"):
            return []
        
        # Convert Bybit format to standard format
        candles = []
        for item in data["list"]:
            try:
                candles.append({
                    "timestamp": int(item[0]),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                })
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse Bybit candle: {e}")
                continue
        
        return candles
    
    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Get current ticker data.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Dict with keys: last_price, bid, ask, volume_24h, change_24h
        """
        data = await self._request(
            "/market/tickers",
            params={"category": "linear", "symbol": symbol}
        )
        
        if not data or not data.get("list") or len(data["list"]) == 0:
            return None
        
        ticker = data["list"][0]
        try:
            last_price = float(ticker.get("lastPrice", 0))
            bid = float(ticker.get("bid1Price", 0))
            ask = float(ticker.get("ask1Price", 0))
            
            # Calculate spread percentage
            spread = 0
            if bid > 0 and ask > 0:
                spread = ((ask - bid) / bid) * 100
            
            return {
                "last_price": last_price,
                "bid": bid,
                "ask": ask,
                "volume_24h": float(ticker.get("volume24h", 0)),
                "change_24h": float(ticker.get("price24hPcnt", 0)) * 100,
                "spread_pct": spread,
            }
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse Bybit ticker: {e}")
            return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Get current funding rate for perpetual futures.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Current funding rate as float (e.g., 0.0001 = 0.01%)
        """
        data = await self._request(
            "/market/tickers",
            params={"category": "linear", "symbol": symbol}
        )
        
        if not data or not data.get("list") or len(data["list"]) == 0:
            return None
        
        try:
            return float(data["list"][0].get("fundingRate", 0))
        except (ValueError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse Bybit funding rate: {e}")
            return None
    
    async def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """
        Get open interest data.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Dict with keys: oi (open interest in contracts), oi_usd
        """
        data = await self._request(
            "/market/open-interest",
            params={
                "category": "linear",
                "symbol": symbol,
                "intervalTime": "5min"
            }
        )
        
        if not data or not data.get("list") or len(data["list"]) == 0:
            return None
        
        try:
            oi_data = data["list"][0]
            return {
                "oi": float(oi_data.get("openInterest", 0)),
                "oi_usd": float(oi_data.get("openInterest", 0)),  # Bybit gives contracts
            }
        except (ValueError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse Bybit open interest: {e}")
            return None
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Optional[Dict]:
        """
        Get orderbook data.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            depth: Orderbook depth (max 200)
            
        Returns:
            Dict with keys: bids (list of [price, size]), asks (list of [price, size])
        """
        data = await self._request(
            "/market/orderbook",
            params={
                "category": "linear",
                "symbol": symbol,
                "limit": str(min(depth, 200))
            }
        )
        
        if not data:
            return None
        
        try:
            return {
                "bids": [[float(b[0]), float(b[1])] for b in data.get("b", [])],
                "asks": [[float(a[0]), float(a[1])] for a in data.get("a", [])],
            }
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse Bybit orderbook: {e}")
            return None
    
    async def close(self):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
