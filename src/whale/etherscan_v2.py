"""
Gheezy Crypto - Etherscan V2 API Client

Etherscan V2 uses ONE API key for multiple EVM chains.
Supported chains: ETH, Polygon, Arbitrum, Base
Note: BSC (chainid=56) requires paid plan - NOT included.

API endpoint format:
https://api.etherscan.io/v2/api?chainid={CHAIN_ID}&module=...
"""

import os
import random
from typing import Optional

import structlog

logger = structlog.get_logger()

# Etherscan V2 Base URL
ETHERSCAN_V2_BASE = "https://api.etherscan.io/v2/api"

# Chain IDs for Etherscan V2
# Note: BSC (56) requires paid plan - NOT included
CHAIN_IDS = {
    "eth": 1,
    "polygon": 137,
    "arbitrum": 42161,
    "base": 8453,
}


def get_etherscan_key() -> Optional[str]:
    """
    Rotate between available Etherscan API keys.

    Supports up to 3 API keys for rate limit management:
    - ETHERSCAN_API_KEY (primary)
    - ETHERSCAN_API_KEY_2 (optional)
    - ETHERSCAN_API_KEY_3 (optional)

    Returns:
        str: Random available API key or None if no keys configured
    """
    keys = [
        os.getenv("ETHERSCAN_API_KEY"),
        os.getenv("ETHERSCAN_API_KEY_2"),
        os.getenv("ETHERSCAN_API_KEY_3"),
    ]
    available_keys = [k for k in keys if k]
    return random.choice(available_keys) if available_keys else None


def get_etherscan_v2_url(chain: str) -> Optional[str]:
    """
    Get Etherscan V2 API URL with chainid parameter.

    Args:
        chain: Chain identifier (eth, polygon, arbitrum, base)

    Returns:
        str: Full API URL with chainid or None if chain not supported
    """
    chain_id = CHAIN_IDS.get(chain.lower())
    if not chain_id:
        logger.warning(
            "Chain not supported by Etherscan V2",
            chain=chain,
            supported=list(CHAIN_IDS.keys()),
        )
        return None
    return f"{ETHERSCAN_V2_BASE}?chainid={chain_id}"


def get_chain_id(chain: str) -> Optional[int]:
    """
    Get chain ID for Etherscan V2 API.

    Args:
        chain: Chain identifier (eth, polygon, arbitrum, base)

    Returns:
        int: Chain ID or None if chain not supported
    """
    return CHAIN_IDS.get(chain.lower())


def is_chain_supported(chain: str) -> bool:
    """
    Check if chain is supported by Etherscan V2.

    Args:
        chain: Chain identifier

    Returns:
        bool: True if chain is supported
    """
    return chain.lower() in CHAIN_IDS
