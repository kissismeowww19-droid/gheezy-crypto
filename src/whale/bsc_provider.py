"""
BSC RPC Provider with automatic rotation and health checking.

This module provides a resilient RPC provider for Binance Smart Chain that:
- Rotates through multiple free public RPC endpoints
- Performs health checks with timeout
- Automatically fails over to the next provider
- Caches the last working provider for efficiency
- Rate limits requests to prevent RPC overload
"""

import asyncio
import time
from typing import Optional

import aiohttp
import structlog

logger = structlog.get_logger()


class BSCRateLimiter:
    """
    Rate limiter for BSC RPC requests.
    
    Ensures a minimum delay between consecutive RPC calls to prevent
    overloading public RPC endpoints.
    """
    
    def __init__(self, delay: float = 0.5):
        """
        Initialize rate limiter.
        
        Args:
            delay: Minimum delay in seconds between calls (default: 0.5s = 2 req/sec)
        """
        self.delay = delay
        self.last_call = 0.0
    
    async def wait(self):
        """Wait if necessary to maintain rate limit."""
        now = time.time()
        wait_time = self.delay - (now - self.last_call)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self.last_call = time.time()


class BSCProvider:
    """
    BSC RPC Provider with automatic rotation and failover.
    
    Uses free public RPC endpoints with automatic health checking
    and failover to ensure reliable access to BSC blockchain data.
    """
    
    def __init__(self):
        """Initialize BSC provider with list of free public RPC endpoints."""
        self.providers = [
            # Official Binance (most reliable)
            "https://bsc-dataseed1.binance.org",
            "https://bsc-dataseed2.binance.org",
            "https://bsc-dataseed3.binance.org",
            "https://bsc-dataseed4.binance.org",
            
            # Community RPCs
            "https://bsc.publicnode.com",
            "https://binance.llamarpc.com",
            "https://bsc-dataseed1.defibit.io",
            "https://bsc-dataseed1.ninicoin.io",
            
            # Ankr (backup)
            "https://rpc.ankr.com/bsc",
        ]
        self.current_index = 0
        self.last_working_provider: Optional[str] = None
        self.last_check_time: float = 0
        self.cache_duration = 300  # Cache working provider for 5 minutes
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiter to prevent RPC overload (500ms delay = 2 req/sec max)
        self.rate_limiter = BSCRateLimiter(delay=0.5)
    
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
            # Apply rate limiting before each request
            await self.rate_limiter.wait()
            
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
    
    async def make_batch_request(
        self,
        requests: list[tuple[str, list]],
        timeout: int = 10,
        max_retries: int = 3,
    ) -> Optional[list]:
        """
        Make multiple RPC requests in a single batch.
        
        This is more efficient than individual requests as it reduces
        the number of HTTP connections and overall latency.
        
        Args:
            requests: List of (method, params) tuples
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        
        Returns:
            list: List of JSON-RPC responses, or None if all attempts fail
        """
        # Handle empty request list
        if not requests:
            logger.debug("BSC: Empty batch request, skipping")
            return []
        
        # Build batch request
        batch_request = [
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": i,
            }
            for i, (method, params) in enumerate(requests)
        ]
        
        for attempt in range(max_retries):
            # Apply rate limiting before each request
            await self.rate_limiter.wait()
            
            provider = await self.get_working_provider()
            
            if not provider:
                logger.warning(
                    "No working BSC provider available for batch",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                await asyncio.sleep(2 ** attempt)
                continue
            
            try:
                session = await self._get_session()
                client_timeout = aiohttp.ClientTimeout(total=timeout)
                
                async with session.post(
                    provider,
                    json=batch_request,
                    timeout=client_timeout,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Batch response should be a list
                        if isinstance(data, list):
                            return data
                        
                        logger.debug(
                            "BSC RPC batch error response",
                            provider=provider,
                            error=data.get("error") if isinstance(data, dict) else "Invalid response format",
                        )
                    else:
                        logger.debug(
                            "BSC RPC batch bad status",
                            provider=provider,
                            status=response.status,
                        )
            
            except asyncio.TimeoutError:
                logger.debug(
                    "BSC RPC batch timeout",
                    provider=provider,
                    timeout=timeout,
                )
            except aiohttp.ClientError as e:
                logger.debug(
                    "BSC RPC batch client error",
                    provider=provider,
                    error=str(e),
                )
            except Exception as e:
                logger.warning(
                    "Unexpected BSC RPC batch error",
                    provider=provider,
                    error=str(e),
                )
            
            # Mark provider as failed and try next one
            self.invalidate_cache()
            
            # Wait before retrying with exponential backoff
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        logger.warning(
            "All BSC RPC batch attempts failed",
            requests_count=len(requests),
            max_retries=max_retries,
        )
        return None
