"""
OKX Exchange Client - основной источник данных для Smart Signals.
"""

import logging
from typing import List, Dict, Optional
import aiohttp
import asyncio

from signals.rate_limiter import ExchangeRateLimiters

logger = logging.getLogger(__name__)


class OKXClient:
    """
    OKX exchange client для получения данных о фьючерсах и спотовых рынках.
    """
    
    BASE_URL = "https://www.okx.com/api/v5"
    
    def __init__(self):
        self.rate_limiter = ExchangeRateLimiters.get_limiter("okx", requests_per_second=10)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a rate-limited request to OKX API.
        
        Args:
            endpoint: API endpoint (e.g., "/market/candles")
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
                    if data.get("code") == "0":
                        return data.get("data")
                    else:
                        logger.warning(f"OKX API error: {data.get('msg')}")
                else:
                    logger.warning(f"OKX HTTP error: {resp.status}")
        except asyncio.TimeoutError:
            logger.warning(f"OKX request timeout: {endpoint}")
        except Exception as e:
            logger.error(f"OKX request error: {e}", exc_info=True)
        
        return None
    
    async def get_ohlcv(self, symbol: str, timeframe: str = "1H", limit: int = 100) -> List[Dict]:
        """
        Get OHLCV candlestick data.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            timeframe: Timeframe (e.g., "1H", "4H", "1D")
            limit: Number of candles to fetch (max 100)
            
        Returns:
            List of OHLCV dicts with keys: timestamp, open, high, low, close, volume
        """
        # Convert timeframe to OKX format
        tf_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1H": "1H", "4H": "4H", "1D": "1D"
        }
        bar = tf_map.get(timeframe, "1H")
        
        data = await self._request(
            "/market/candles",
            params={"instId": symbol, "bar": bar, "limit": str(limit)}
        )
        
        if not data:
            return []
        
        # Convert OKX format to standard format
        candles = []
        for item in data:
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
                logger.warning(f"Failed to parse OKX candle: {e}")
                continue
        
        return candles
    
    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Get current ticker data.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            
        Returns:
            Dict with keys: last_price, bid, ask, volume_24h, change_24h
        """
        data = await self._request("/market/ticker", params={"instId": symbol})
        
        if not data or len(data) == 0:
            return None
        
        ticker = data[0]
        try:
            last_price = float(ticker.get("last", 0))
            bid = float(ticker.get("bidPx", 0))
            ask = float(ticker.get("askPx", 0))
            
            # Calculate spread percentage
            spread = 0
            if bid > 0 and ask > 0:
                spread = ((ask - bid) / bid) * 100
            
            return {
                "last_price": last_price,
                "bid": bid,
                "ask": ask,
                "volume_24h": float(ticker.get("vol24h", 0)),
                "change_24h": float(ticker.get("changeUtc8h", 0)),
                "spread_pct": spread,
            }
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse OKX ticker: {e}")
            return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Get current funding rate for perpetual futures.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT-SWAP")
            
        Returns:
            Current funding rate as float (e.g., 0.0001 = 0.01%)
        """
        # Ensure symbol is in SWAP format
        if not symbol.endswith("-SWAP"):
            symbol = f"{symbol}-SWAP"
        
        data = await self._request("/public/funding-rate", params={"instId": symbol})
        
        if not data or len(data) == 0:
            return None
        
        try:
            return float(data[0].get("fundingRate", 0))
        except (ValueError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse OKX funding rate: {e}")
            return None
    
    async def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """
        Get open interest data.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT-SWAP")
            
        Returns:
            Dict with keys: oi (open interest in contracts), oi_usd
        """
        # Ensure symbol is in SWAP format
        if not symbol.endswith("-SWAP"):
            symbol = f"{symbol}-SWAP"
        
        data = await self._request("/public/open-interest", params={"instId": symbol})
        
        if not data or len(data) == 0:
            return None
        
        try:
            return {
                "oi": float(data[0].get("oi", 0)),
                "oi_usd": float(data[0].get("oiCcy", 0)),
            }
        except (ValueError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse OKX open interest: {e}")
            return None
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Optional[Dict]:
        """
        Get orderbook data.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            depth: Orderbook depth (max 400)
            
        Returns:
            Dict with keys: bids (list of [price, size]), asks (list of [price, size])
        """
        data = await self._request(
            "/market/books",
            params={"instId": symbol, "sz": str(depth)}
        )
        
        if not data or len(data) == 0:
            return None
        
        try:
            book = data[0]
            return {
                "bids": [[float(b[0]), float(b[1])] for b in book.get("bids", [])],
                "asks": [[float(a[0]), float(a[1])] for a in book.get("asks", [])],
            }
        except (ValueError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse OKX orderbook: {e}")
            return None
    
    async def close(self):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
