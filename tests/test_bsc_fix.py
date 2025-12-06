"""
Test BSC fix - verify simple sequential RPC requests work.
"""

import sys
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import asyncio


@pytest.fixture
def bsc_tracker():
    """Create a BSCTracker instance."""
    from whale.bsc import BSCTracker
    return BSCTracker()


@pytest.mark.asyncio
async def test_bsc_rpc_rotation_structure(bsc_tracker):
    """Test that BSC RPC rotation method exists and has correct signature."""
    # Verify method exists
    assert hasattr(bsc_tracker, '_get_from_rpc_with_rotation')
    
    # Get the method
    method = getattr(bsc_tracker, '_get_from_rpc_with_rotation')
    
    # Verify it's async
    assert asyncio.iscoroutinefunction(method)
    
    # Verify it accepts the right parameters
    import inspect
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    assert 'min_value_bnb' in params
    assert 'limit' in params


@pytest.mark.asyncio
async def test_bsc_simple_request_logic(bsc_tracker):
    """Test that BSC uses simple sequential requests (not batch)."""
    with patch.object(bsc_tracker, '_get_session') as mock_session:
        # Setup mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock()
        
        # Mock block number response
        mock_response.json.side_effect = [
            {"result": "0x100"},  # Block number = 256
            {"result": {  # Block data
                "transactions": [
                    {
                        "hash": "0xtest1",
                        "from": "0xfrom1",
                        "to": "0xto1",
                        "value": "0xde0b6b3a7640000"  # 1 BNB
                    }
                ]
            }},
            {"result": {"transactions": []}},  # Empty block
            {"result": {"transactions": []}},  # Empty block
        ]
        
        session = AsyncMock()
        session.post = AsyncMock(return_value=mock_response)
        session.closed = False
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()
        mock_session.return_value = session
        
        # Set BNB price
        bsc_tracker._bnb_price = 300.0
        
        # Call the method
        result = await bsc_tracker._get_from_rpc_with_rotation(
            min_value_bnb=0.5,
            limit=10
        )
        
        # Verify session.post was called (simple POST requests)
        assert session.post.called
        
        # Verify we got transactions
        assert isinstance(result, list)


@pytest.mark.asyncio  
async def test_bsc_uses_multiple_rpc_endpoints(bsc_tracker):
    """Verify that BSC tries multiple RPC endpoints on failure."""
    with patch.object(bsc_tracker, '_get_session') as mock_session:
        # Setup mock session that fails for first endpoint
        session = AsyncMock()
        
        call_count = 0
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            mock_response = AsyncMock()
            if call_count <= 4:  # First 4 calls fail (1 endpoint = 4 calls)
                mock_response.status = 500
            else:  # Second endpoint succeeds
                mock_response.status = 200
                if "eth_blockNumber" in str(args):
                    mock_response.json = AsyncMock(return_value={"result": "0x100"})
                else:
                    mock_response.json = AsyncMock(return_value={"result": {"transactions": []}})
            return mock_response
        
        session.post = mock_post
        session.closed = False
        mock_session.return_value = session
        
        bsc_tracker._bnb_price = 300.0
        
        # Call the method
        result = await bsc_tracker._get_from_rpc_with_rotation(
            min_value_bnb=0.5,
            limit=10
        )
        
        # Verify multiple RPC endpoints were tried
        assert call_count > 4  # Should try second endpoint after first fails


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
