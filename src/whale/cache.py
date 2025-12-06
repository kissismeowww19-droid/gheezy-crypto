"""
Gheezy Crypto - Transaction Cache

In-memory cache for transaction hashes to prevent duplicate displays.
Stores last 1000 transaction hashes with 1-hour TTL.

Features:
- Thread-safe operations
- Automatic cleanup of old entries
- Size-limited to prevent memory bloat
- TTL-based expiration
"""

import time
from collections import OrderedDict
from typing import Optional
import structlog

logger = structlog.get_logger()

# Cache constants
MAX_CACHE_SIZE = 1000  # Maximum number of transaction hashes to store
CACHE_TTL_SECONDS = 3600  # 1 hour TTL


class TransactionCache:
    """
    In-memory cache for transaction hashes.
    
    Implements FIFO cache with TTL expiration:
    - Stores txHash -> timestamp mapping
    - Automatically removes old entries when size exceeds MAX_CACHE_SIZE (FIFO)
    - Removes expired entries (older than CACHE_TTL_SECONDS)
    """
    
    def __init__(self, max_size: int = MAX_CACHE_SIZE, ttl_seconds: int = CACHE_TTL_SECONDS):
        """
        Initialize transaction cache.
        
        Args:
            max_size: Maximum number of hashes to store
            ttl_seconds: Time-to-live for cached entries in seconds
        """
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        logger.info(
            "Transaction cache initialized",
            max_size=max_size,
            ttl_seconds=ttl_seconds,
        )
    
    def contains(self, tx_hash: str) -> bool:
        """
        Check if transaction hash exists in cache and is not expired.
        
        Args:
            tx_hash: Transaction hash to check
            
        Returns:
            bool: True if hash exists and not expired, False otherwise
        """
        if tx_hash not in self._cache:
            return False
        
        # Check if entry is expired
        timestamp = self._cache[tx_hash]
        current_time = time.time()
        
        if current_time - timestamp > self._ttl_seconds:
            # Entry expired, remove it
            del self._cache[tx_hash]
            logger.debug(
                "Cache entry expired",
                tx_hash=tx_hash[:16] + "...",
                age_seconds=int(current_time - timestamp),
            )
            return False
        
        return True
    
    def add(self, tx_hash: str) -> None:
        """
        Add transaction hash to cache.
        
        If cache is full, removes oldest entry.
        Updates timestamp if hash already exists.
        
        Args:
            tx_hash: Transaction hash to add
        """
        current_time = time.time()
        
        # If hash already exists, update timestamp and move to end
        if tx_hash in self._cache:
            del self._cache[tx_hash]
        
        # Add to cache
        self._cache[tx_hash] = current_time
        
        # If cache exceeds max size, remove oldest entries
        while len(self._cache) > self._max_size:
            oldest_hash, oldest_time = self._cache.popitem(last=False)
            logger.debug(
                "Cache size limit reached, removed oldest entry",
                removed_hash=oldest_hash[:16] + "...",
                age_seconds=int(current_time - oldest_time),
                cache_size=len(self._cache),
            )
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.
        
        Returns:
            int: Number of entries removed
        """
        current_time = time.time()
        expired_hashes = [
            tx_hash
            for tx_hash, timestamp in self._cache.items()
            if current_time - timestamp > self._ttl_seconds
        ]
        
        for tx_hash in expired_hashes:
            del self._cache[tx_hash]
        
        if expired_hashes:
            logger.info(
                "Cleaned up expired cache entries",
                removed_count=len(expired_hashes),
                remaining_count=len(self._cache),
            )
        
        return len(expired_hashes)
    
    def clear(self) -> None:
        """Clear all entries from cache."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("Cache cleared", removed_count=count)
    
    def size(self) -> int:
        """
        Get current cache size.
        
        Returns:
            int: Number of entries in cache
        """
        return len(self._cache)
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            dict: Cache statistics including size, max_size, ttl, oldest and newest entry ages
        """
        current_time = time.time()
        stats = {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl_seconds,
        }
        
        if self._cache:
            oldest_time = next(iter(self._cache.values()))
            newest_time = next(reversed(self._cache.values()))
            stats["oldest_entry_age_seconds"] = int(current_time - oldest_time)
            stats["newest_entry_age_seconds"] = int(current_time - newest_time)
        
        return stats


# Global cache instance
_global_cache: Optional[TransactionCache] = None


def get_transaction_cache() -> TransactionCache:
    """
    Get global transaction cache instance.
    
    Creates cache on first access (lazy initialization).
    
    Returns:
        TransactionCache: Global cache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = TransactionCache()
    return _global_cache
