"""
Tests for BSC RPC Provider.

Verifies that the BSCProvider properly:
- Rotates through RPC endpoints
- Performs health checks with timeout
- Handles failover between providers
- Caches working providers
"""

import sys
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import AsyncMock, Mock, patch
import asyncio


@pytest.fixture
def mock_aiohttp_session():
    """Create a mock aiohttp session."""
    session = AsyncMock()
    session.closed = False
    return session


@pytest.fixture
def bsc_provider():
    """Create a BSCProvider instance."""
    # Import here to avoid import errors before path setup
    from whale.bsc_provider import BSCProvider
    return BSCProvider()


@pytest.mark.asyncio
async def test_provider_initialization(bsc_provider):
    """Test that BSCProvider initializes with correct providers."""
    assert len(bsc_provider.providers) == 5
    assert "https://rpc.ankr.com/bsc" in bsc_provider.providers
    assert "https://bsc-dataseed1.binance.org" in bsc_provider.providers
    assert bsc_provider.current_index == 0
    assert bsc_provider.last_working_provider is None


@pytest.mark.asyncio
async def test_check_health_success(bsc_provider, mock_aiohttp_session):
    """Test health check with successful response."""
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "jsonrpc": "2.0",
        "id": 1,
        "result": "0x123456"  # Valid hex block number
    })
    mock_aiohttp_session.post = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    
    bsc_provider._session = mock_aiohttp_session
    
    result = await bsc_provider.check_health("https://rpc.ankr.com/bsc")
    assert result is True


@pytest.mark.asyncio
async def test_check_health_timeout(bsc_provider, mock_aiohttp_session):
    """Test health check with timeout."""
    # Mock timeout
    mock_aiohttp_session.post = AsyncMock(side_effect=asyncio.TimeoutError())
    bsc_provider._session = mock_aiohttp_session
    
    result = await bsc_provider.check_health("https://rpc.ankr.com/bsc", timeout=1)
    assert result is False


@pytest.mark.asyncio
async def test_check_health_bad_response(bsc_provider, mock_aiohttp_session):
    """Test health check with bad response."""
    # Mock bad response
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_aiohttp_session.post = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    
    bsc_provider._session = mock_aiohttp_session
    
    result = await bsc_provider.check_health("https://rpc.ankr.com/bsc")
    assert result is False


@pytest.mark.asyncio
async def test_check_health_invalid_result(bsc_provider, mock_aiohttp_session):
    """Test health check with invalid result format."""
    # Mock response with invalid result
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "jsonrpc": "2.0",
        "id": 1,
        "result": "not_a_hex_number"
    })
    mock_aiohttp_session.post = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    
    bsc_provider._session = mock_aiohttp_session
    
    result = await bsc_provider.check_health("https://rpc.ankr.com/bsc")
    assert result is False


@pytest.mark.asyncio
async def test_get_working_provider_cached(bsc_provider):
    """Test that cached provider is returned when valid."""
    # Set up cached provider
    bsc_provider.last_working_provider = "https://rpc.ankr.com/bsc"
    bsc_provider.last_check_time = 100.0
    
    with patch('time.time', return_value=150.0):  # Within cache duration
        provider = await bsc_provider.get_working_provider()
        assert provider == "https://rpc.ankr.com/bsc"


@pytest.mark.asyncio
async def test_get_working_provider_cache_expired(bsc_provider, mock_aiohttp_session):
    """Test that cache is refreshed when expired."""
    # Set up expired cached provider
    bsc_provider.last_working_provider = "https://rpc.ankr.com/bsc"
    bsc_provider.last_check_time = 0.0
    
    # Mock successful health check
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "jsonrpc": "2.0",
        "id": 1,
        "result": "0x123456"
    })
    mock_aiohttp_session.post = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    
    bsc_provider._session = mock_aiohttp_session
    
    with patch('time.time', return_value=400.0):  # Cache expired
        provider = await bsc_provider.get_working_provider()
        assert provider is not None
        assert provider in bsc_provider.providers


@pytest.mark.asyncio
async def test_get_working_provider_rotation(bsc_provider, mock_aiohttp_session):
    """Test that provider rotation works correctly."""
    # Mock first provider fails, second succeeds
    call_count = [0]
    
    async def mock_health_check(provider):
        call_count[0] += 1
        # First provider fails, second succeeds
        return call_count[0] > 1
    
    bsc_provider.check_health = mock_health_check
    
    provider = await bsc_provider.get_working_provider()
    assert provider is not None
    assert call_count[0] >= 2  # At least 2 providers checked


@pytest.mark.asyncio
async def test_make_request_success(bsc_provider, mock_aiohttp_session):
    """Test successful RPC request."""
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "jsonrpc": "2.0",
        "id": 1,
        "result": "0x123456"
    })
    mock_aiohttp_session.post = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    
    bsc_provider._session = mock_aiohttp_session
    bsc_provider.last_working_provider = "https://rpc.ankr.com/bsc"
    bsc_provider.last_check_time = 100.0
    
    with patch('time.time', return_value=150.0):
        result = await bsc_provider.make_request("eth_blockNumber", [])
        assert result is not None
        assert result["result"] == "0x123456"


@pytest.mark.asyncio
async def test_make_request_retry(bsc_provider, mock_aiohttp_session):
    """Test that make_request retries on failure."""
    call_count = [0]
    
    async def mock_get_provider():
        call_count[0] += 1
        if call_count[0] == 1:
            return None  # First call fails
        return "https://rpc.ankr.com/bsc"  # Second call succeeds
    
    bsc_provider.get_working_provider = mock_get_provider
    
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "jsonrpc": "2.0",
        "id": 1,
        "result": "0x123456"
    })
    mock_aiohttp_session.post = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    
    bsc_provider._session = mock_aiohttp_session
    
    result = await bsc_provider.make_request("eth_blockNumber", [], max_retries=2)
    assert result is not None
    assert call_count[0] == 2


@pytest.mark.asyncio
async def test_close_session(bsc_provider, mock_aiohttp_session):
    """Test that session is properly closed."""
    bsc_provider._session = mock_aiohttp_session
    await bsc_provider.close()
    mock_aiohttp_session.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
