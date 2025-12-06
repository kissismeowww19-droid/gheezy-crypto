"""
BSC RPC Provider with automatic rotation and health checking.

This module provides a resilient RPC provider for Binance Smart Chain that:
- Rotates through multiple free public RPC endpoints
- Performs health checks with timeout
- Automatically fails over to the next provider
- Caches the last working provider for efficiency
"""

import asyncio
import time
from typing import Optional

import aiohttp
import structlog

logger = structlog.get_logger()


class BSCProvider:
    """
    BSC RPC Provider with automatic rotation and failover.
    
    Uses free public RPC endpoints with automatic health checking
    and failover to ensure reliable access to BSC blockchain data.
    """
    
    def __init__(self):
        """Initialize BSC provider with list of free public RPC endpoints."""
        self.providers = [
            "https://rpc.ankr.com/bsc",           # Best - no rate limit, 150k/month
            "https://bsc-dataseed1.binance.org",  # Official Binance
            "https://bsc-dataseed2.defibit.io",   # Fast
            "https://bscrpc.com",                 # New, fast
            "https://bsc.publicnode.com",         # Reliable
        ]
        self.current_index = 0
        self.last_working_provider: Optional[str] = None
        self.last_check_time: float = 0
        self.cache_duration = 300  # Cache working provider for 5 minutes
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def invalidate_cache(self) -> None:
        """Invalidate the cached working provider."""
        self.last_working_provider = None
        self.last_check_time = 0
    
    async def get_working_provider(self) -> Optional[str]:
        """
        Get a working RPC provider.
        
        Tries providers in order until one responds successfully.
        Caches the last working provider to reduce health checks.
        
        Returns:
            str: URL of working provider, or None if all fail
        """
        current_time = time.time()
        
        # Return cached provider if still valid
        if (self.last_working_provider and 
            current_time - self.last_check_time < self.cache_duration):
            logger.debug(
                "Using cached BSC provider",
                provider=self.last_working_provider,
                cache_age=int(current_time - self.last_check_time),
            )
            return self.last_working_provider
        
        # Try each provider until one works
        for i in range(len(self.providers)):
            provider = self.providers[(self.current_index + i) % len(self.providers)]
            
            if await self.check_health(provider):
                self.current_index = (self.current_index + i) % len(self.providers)
                self.last_working_provider = provider
                self.last_check_time = current_time
                
                logger.info(
                    "BSC provider selected",
                    provider=provider,
                    index=self.current_index,
                )
                return provider
            
            logger.debug(
                "BSC provider unhealthy",
                provider=provider,
            )
        
        # All providers failed
        logger.warning("All BSC providers are unavailable")
        self.last_working_provider = None
        return None
    
    async def check_health(self, provider: str, timeout: int = 3) -> bool:
        """
        Check if provider is healthy and responding.
        
        Args:
            provider: RPC provider URL to check
            timeout: Timeout in seconds (default: 3)
        
        Returns:
            bool: True if provider is healthy, False otherwise
        """
        try:
            session = await self._get_session()
            
            # Simple health check: get latest block number
            request_data = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1,
            }
            
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            
            async with session.post(
                provider,
                json=request_data,
                timeout=client_timeout,
            ) as response:
                if response.status != 200:
                    return False
                
                data = await response.json()
                
                # Check for valid response
                if "result" not in data:
                    return False
                
                # Verify result is a valid hex block number
                result = data["result"]
                if not isinstance(result, str) or not result.startswith("0x"):
                    return False
                
                # Try to parse as int to verify it's a valid block number
                int(result, 16)
                return True
                
        except asyncio.TimeoutError:
            logger.debug(
                "BSC provider timeout",
                provider=provider,
                timeout=timeout,
            )
            return False
        except (aiohttp.ClientError, ValueError, KeyError) as e:
            logger.debug(
                "BSC provider error",
                provider=provider,
                error=str(e),
            )
            return False
        except Exception as e:
            logger.warning(
                "Unexpected error checking BSC provider",
                provider=provider,
                error=str(e),
            )
            return False
    
    async def make_request(
        self,
        method: str,
        params: list,
        timeout: int = 5,
        max_retries: int = 3,
    ) -> Optional[dict]:
        """
        Make an RPC request with automatic provider rotation.
        
        Args:
            method: JSON-RPC method name
            params: Method parameters
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        
        Returns:
            dict: JSON-RPC response, or None if all attempts fail
        """
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        
        for attempt in range(max_retries):
            provider = await self.get_working_provider()
            
            if not provider:
                logger.warning(
                    "No working BSC provider available",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                # Wait before retrying
                await asyncio.sleep(2 ** attempt)
                continue
            
            try:
                session = await self._get_session()
                client_timeout = aiohttp.ClientTimeout(total=timeout)
                
                async with session.post(
                    provider,
                    json=request_data,
                    timeout=client_timeout,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "result" in data:
                            return data
                        
                        logger.debug(
                            "BSC RPC error response",
                            provider=provider,
                            error=data.get("error"),
                        )
                    else:
                        logger.debug(
                            "BSC RPC bad status",
                            provider=provider,
                            status=response.status,
                        )
            
            except asyncio.TimeoutError:
                logger.debug(
                    "BSC RPC timeout",
                    provider=provider,
                    timeout=timeout,
                )
            except aiohttp.ClientError as e:
                logger.debug(
                    "BSC RPC client error",
                    provider=provider,
                    error=str(e),
                )
            except Exception as e:
                logger.warning(
                    "Unexpected BSC RPC error",
                    provider=provider,
                    error=str(e),
                )
            
            # Mark provider as failed and try next one
            self.invalidate_cache()
            
            # Wait before retrying with exponential backoff
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        logger.warning(
            "All BSC RPC attempts failed",
            method=method,
            max_retries=max_retries,
        )
        return None
