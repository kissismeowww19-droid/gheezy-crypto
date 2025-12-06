"""
Gheezy Crypto - API Key Rotation

Round-robin rotation for Etherscan V2 API keys to increase rate limits.
Supports up to 3 API keys, providing 9 req/sec (3 keys × 3 req/sec each).

Features:
- Round-robin key rotation (not thread-safe, use in async context)
- Automatic fallback to single key if only one configured
- Integration with rate limit handling
- Retry logic for rate limit errors

Note: This module uses global state and is designed for single-threaded
async applications. For multi-threaded use, add locking mechanisms.
"""

import asyncio
import itertools
from typing import Optional
import structlog

from config import settings

logger = structlog.get_logger()

# API key rotation state
_api_keys: list[str] = []
_key_cycle: Optional[itertools.cycle] = None
_initialized = False


def init_api_keys() -> None:
    """
    Initialize API key rotation from settings configuration.
    
    Reads up to 3 API keys from settings (loaded from .env via Pydantic):
    - ETHERSCAN_API_KEY (primary)
    - ETHERSCAN_API_KEY_2 (optional)
    - ETHERSCAN_API_KEY_3 (optional)
    
    If multiple keys are configured, enables round-robin rotation.
    """
    global _api_keys, _key_cycle, _initialized
    
    if _initialized:
        return
    
    keys = [
        settings.etherscan_api_key,
        settings.etherscan_api_key_2,
        settings.etherscan_api_key_3,
    ]
    
    # Filter out None and empty strings
    _api_keys = [k for k in keys if k and k.strip()]
    
    if _api_keys:
        _key_cycle = itertools.cycle(_api_keys)
        logger.info(
            "API key rotation initialized",
            key_count=len(_api_keys),
            max_req_per_sec=len(_api_keys) * 3,
        )
    else:
        _key_cycle = None
        logger.warning("No Etherscan API keys configured")
    
    _initialized = True


def get_next_api_key() -> Optional[str]:
    """
    Get next API key in rotation (round-robin).
    
    If only one key is configured, always returns that key.
    If multiple keys are configured, rotates through them.
    
    Returns:
        Optional[str]: Next API key or None if no keys configured
    """
    global _key_cycle
    
    if not _initialized:
        init_api_keys()
    
    if _key_cycle is None:
        return None
    
    return next(_key_cycle)


def get_api_key_count() -> int:
    """
    Get number of configured API keys.
    
    Returns:
        int: Number of API keys available
    """
    if not _initialized:
        init_api_keys()
    
    return len(_api_keys)


async def make_request_with_rate_limit(
    request_func,
    delay_seconds: float = 0.35,
    max_retries: int = 3,
    retry_delay_seconds: float = 1.0,
):
    """
    Make API request with rate limit handling.
    
    Features:
    - Adds delay before request to respect rate limits
    - Retries on rate limit errors (HTTP 429 or "Max calls per sec" message)
    - Uses exponential backoff for retries
    
    Args:
        request_func: Async function that makes the API request
        delay_seconds: Delay before making request (default 0.35s for 3 req/sec)
        max_retries: Maximum number of retry attempts (default 3)
        retry_delay_seconds: Initial retry delay in seconds (default 1.0s)
        
    Returns:
        Response from request_func or None if all retries failed
    """
    # Add delay before request to respect rate limits
    await asyncio.sleep(delay_seconds)
    
    for attempt in range(max_retries):
        try:
            result = await request_func()
            
            # Check if result indicates rate limit error
            if result and isinstance(result, dict):
                status = result.get("status")
                message = result.get("message", "")
                result_str = str(result.get("result", ""))
                
                # Check for rate limit indicators
                is_rate_limit = (
                    status == "0" and (
                        "rate limit" in message.lower() or
                        "rate limit" in result_str.lower() or
                        "max calls per sec" in message.lower() or
                        "max calls per sec" in result_str.lower()
                    )
                )
                
                if is_rate_limit and attempt < max_retries - 1:
                    # Rate limit hit, retry with delay
                    retry_wait = retry_delay_seconds * (attempt + 1)
                    logger.warning(
                        "Rate limit hit, retrying",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        retry_delay=retry_wait,
                    )
                    await asyncio.sleep(retry_wait)
                    continue
            
            # Request successful or non-rate-limit error
            return result
            
        except Exception as e:
            if attempt < max_retries - 1:
                retry_wait = retry_delay_seconds * (attempt + 1)
                logger.warning(
                    "Request failed, retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    retry_delay=retry_wait,
                )
                await asyncio.sleep(retry_wait)
                continue
            else:
                logger.error(
                    "Request failed after all retries",
                    error=str(e),
                    attempts=max_retries,
                )
                raise
    
    return None


def reset_api_keys() -> None:
    """
    Reset API key rotation state.
    
    Used for testing or re-initialization.
    """
    global _api_keys, _key_cycle, _initialized
    _api_keys = []
    _key_cycle = None
    _initialized = False
