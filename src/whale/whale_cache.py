"""
Gheezy Crypto - Whale Results Cache

Caches whale transaction results for 2 minutes to reduce API calls
and improve response times.

Features:
- Per-network caching (ETH, BTC, BSC, ARB, POLYGON, AVAX, TON)
- 2-minute TTL (Time To Live)
- Thread-safe for async usage
- Automatic expiration
"""

import time
from datetime import datetime, timedelta
from typing import Optional, Dict
import structlog

logger = structlog.get_logger()


class WhaleCache:
    """
    Cache for whale transaction results.
    
    Stores formatted whale messages per network with a 2-minute TTL.
    """
    
    def __init__(self, ttl_seconds: int = 120):
        """
        Initialize whale cache.
        
        Args:
            ttl_seconds: Time to live for cached data (default 120 seconds = 2 minutes)
        """
        self.cache: Dict[str, tuple[str, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self._hits = 0
        self._misses = 0
        
        logger.info(
            "Whale cache initialized",
            ttl_seconds=ttl_seconds,
        )
    
    def get(self, network: str) -> Optional[str]:
        """
        Get cached whale data for a network.
        
        Args:
            network: Network name (eth, btc, bsc, arb, polygon, avax, ton, or "all")
        
        Returns:
            Optional[str]: Cached whale message or None if not cached/expired
        """
        network_key = network.lower()
        
        if network_key in self.cache:
            data, timestamp = self.cache[network_key]
            age = datetime.now() - timestamp
            
            if age < self.ttl:
                self._hits += 1
                logger.debug(
                    "Cache hit",
                    network=network,
                    age_seconds=int(age.total_seconds()),
                )
                return data
            else:
                # Expired, remove from cache
                del self.cache[network_key]
                logger.debug(
                    "Cache expired",
                    network=network,
                    age_seconds=int(age.total_seconds()),
                )
        
        self._misses += 1
        logger.debug(
            "Cache miss",
            network=network,
        )
        return None
    
    def set(self, network: str, data: str) -> None:
        """
        Cache whale data for a network.
        
        Args:
            network: Network name (eth, btc, bsc, arb, polygon, avax, ton, or "all")
            data: Formatted whale message to cache
        """
        network_key = network.lower()
        self.cache[network_key] = (data, datetime.now())
        
        logger.debug(
            "Cache set",
            network=network,
            data_length=len(data),
        )
    
    def invalidate(self, network: Optional[str] = None) -> None:
        """
        Invalidate cache for a specific network or all networks.
        
        Args:
            network: Network name to invalidate, or None to clear all
        """
        if network is None:
            count = len(self.cache)
            self.cache.clear()
            logger.info(
                "Cache cleared",
                networks_cleared=count,
            )
        else:
            network_key = network.lower()
            if network_key in self.cache:
                del self.cache[network_key]
                logger.debug(
                    "Cache invalidated",
                    network=network,
                )
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            dict: Cache statistics (hits, misses, hit_rate, cached_networks)
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "cached_networks": len(self.cache),
            "networks": list(self.cache.keys()),
        }
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            int: Number of entries removed
        """
        now = datetime.now()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if now - timestamp >= self.ttl
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(
                "Expired cache entries removed",
                count=len(expired_keys),
                networks=expired_keys,
            )
        
        return len(expired_keys)


# Global whale cache instance
_whale_cache: Optional[WhaleCache] = None


def get_whale_cache() -> WhaleCache:
    """
    Get the global whale cache instance.
    
    Returns:
        WhaleCache: Global cache instance
    """
    global _whale_cache
    
    if _whale_cache is None:
        _whale_cache = WhaleCache(ttl_seconds=120)
    
    return _whale_cache


def reset_whale_cache() -> None:
    """
    Reset the global whale cache instance.
    
    Used for testing or re-initialization.
    """
    global _whale_cache
    _whale_cache = None
