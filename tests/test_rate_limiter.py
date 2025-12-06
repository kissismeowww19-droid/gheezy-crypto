"""
Tests for Etherscan Rate Limiter.
"""

import pytest
import asyncio
import time


# Inline the rate limiter class for testing
class EtherscanRateLimiter:
    """Rate limiter для Etherscan API (max 3 req/sec)."""
    
    def __init__(self, calls_per_second: float = 2.5):
        """
        Initialize rate limiter.
        
        Args:
            calls_per_second: Maximum calls per second (default 2.5 for safety margin)
        """
        self.min_interval = 1.0 / calls_per_second  # 400ms между запросами
        self.last_call = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire rate limit token, waiting if necessary."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_call = time.time()


class TestEtherscanRateLimiter:
    """Tests for EtherscanRateLimiter class."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes with correct values."""
        limiter = EtherscanRateLimiter(calls_per_second=2.5)
        
        assert limiter.min_interval == 1.0 / 2.5
        assert limiter.min_interval == 0.4
        assert limiter.last_call == 0
        assert limiter._lock is not None
    
    @pytest.mark.asyncio
    async def test_rate_limiter_single_call(self):
        """Test single call goes through immediately."""
        limiter = EtherscanRateLimiter(calls_per_second=2.5)
        
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        
        # First call should be instant (< 10ms)
        assert elapsed < 0.01
    
    @pytest.mark.asyncio
    async def test_rate_limiter_multiple_calls(self):
        """Test multiple calls are rate limited."""
        limiter = EtherscanRateLimiter(calls_per_second=2.5)
        
        # First call
        await limiter.acquire()
        
        # Second call should wait
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        
        # Should wait at least min_interval (0.4s)
        assert elapsed >= 0.35  # Allow small margin
        assert elapsed < 0.5  # Should not wait too long
    
    @pytest.mark.asyncio
    async def test_rate_limiter_sequential_calls(self):
        """Test sequential calls maintain rate limit."""
        limiter = EtherscanRateLimiter(calls_per_second=2.5)
        
        start = time.time()
        for _ in range(3):
            await limiter.acquire()
        elapsed = time.time() - start
        
        # 3 calls should take at least 2 * min_interval (0.8s)
        assert elapsed >= 0.75
        assert elapsed < 1.0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent_calls(self):
        """Test concurrent calls are properly serialized."""
        limiter = EtherscanRateLimiter(calls_per_second=2.5)
        
        async def make_call():
            await limiter.acquire()
        
        start = time.time()
        # Launch 3 concurrent calls
        await asyncio.gather(
            make_call(),
            make_call(),
            make_call()
        )
        elapsed = time.time() - start
        
        # 3 calls should take at least 2 * min_interval (0.8s)
        assert elapsed >= 0.75
        assert elapsed < 1.0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_with_delay(self):
        """Test that natural delay between calls is respected."""
        limiter = EtherscanRateLimiter(calls_per_second=2.5)
        
        # First call
        await limiter.acquire()
        
        # Wait longer than min_interval
        await asyncio.sleep(0.5)
        
        # Second call should not wait
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        
        # Should be instant since we already waited
        assert elapsed < 0.01
    
    @pytest.mark.asyncio
    async def test_rate_limiter_custom_rate(self):
        """Test rate limiter with custom rate."""
        limiter = EtherscanRateLimiter(calls_per_second=5.0)
        
        assert limiter.min_interval == 0.2
        
        # Make two calls
        await limiter.acquire()
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        
        # Should wait ~0.2s
        assert elapsed >= 0.18
        assert elapsed < 0.25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
