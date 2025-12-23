"""
Rate Limiter - Token Bucket Algorithm для контроля частоты запросов к биржам.
"""

import time
import asyncio
from typing import Dict


class RateLimiter:
    """
    Rate limiter using token bucket algorithm.
    
    Args:
        requests_per_second: Maximum number of requests per second
    """
    
    def __init__(self, requests_per_second: int):
        self.rate = requests_per_second
        self.tokens = float(requests_per_second)
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            # Wait if no tokens available
            if self.tokens < 1:
                sleep_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(sleep_time)
                self.tokens = 1
                self.last_update = time.time()
            
            # Consume a token
            self.tokens -= 1


class ExchangeRateLimiters:
    """Manages rate limiters for all exchanges."""
    
    _limiters: Dict[str, RateLimiter] = {}
    
    @classmethod
    def get_limiter(cls, exchange: str, requests_per_second: int = 10) -> RateLimiter:
        """
        Get or create a rate limiter for an exchange.
        
        Args:
            exchange: Exchange name (okx, bybit, gate)
            requests_per_second: Maximum requests per second for this exchange
            
        Returns:
            RateLimiter instance for the exchange
        """
        if exchange not in cls._limiters:
            cls._limiters[exchange] = RateLimiter(requests_per_second)
        return cls._limiters[exchange]
