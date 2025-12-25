"""
Tests for CoinGecko API pagination functionality.
"""

import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from contextlib import asynccontextmanager
import aiohttp

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.smart_signals import SmartSignalAnalyzer


class TestCoinGeckoPagination:
    """Test CoinGecko API pagination for 500 coins."""
    
    @pytest.mark.asyncio
    async def test_scan_all_coins_with_pagination_free_api(self):
        """Test that free API properly paginates to fetch 500 coins."""
        analyzer = SmartSignalAnalyzer()
        
        # Create mock responses for two pages
        page1_coins = [{"id": f"coin{i}", "symbol": f"SYM{i}", "current_price": 100 + i} for i in range(250)]
        page2_coins = [{"id": f"coin{i}", "symbol": f"SYM{i}", "current_price": 100 + i} for i in range(250, 500)]
        
        call_count = [0]
        
        @asynccontextmanager
        async def mock_get(*args, **kwargs):
            call_count[0] += 1
            mock_resp = AsyncMock()
            if call_count[0] == 1:
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=page1_coins)
            else:
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=page2_coins)
            yield mock_resp
        
        # Create mock session
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = mock_get
        
        # Set the session directly
        analyzer.session = mock_session
        
        # Mock settings without API key (free API)
        with patch('signals.smart_signals.settings') as mock_settings:
            mock_settings.coingecko_api_key = ""
            mock_settings.smart_signals_scan_limit = 500
            
            # Mock asyncio.sleep to avoid delays
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # Execute the scan
                coins = await analyzer.scan_all_coins()
            
            # Verify we got all 500 coins
            assert len(coins) == 500
            assert coins[0]["id"] == "coin0"
            assert coins[249]["id"] == "coin249"
            assert coins[250]["id"] == "coin250"
            assert coins[499]["id"] == "coin499"
    
    @pytest.mark.asyncio
    async def test_scan_all_coins_with_demo_api(self):
        """Test that Demo API key also uses pagination with 250 per_page (2 requests for 500 coins)."""
        analyzer = SmartSignalAnalyzer()
        
        # Create mock responses for two pages (Demo API also has 250 per_page limit)
        page1_coins = [{"id": f"coin{i}", "symbol": f"SYM{i}", "current_price": 100 + i} for i in range(250)]
        page2_coins = [{"id": f"coin{i}", "symbol": f"SYM{i}", "current_price": 100 + i} for i in range(250, 500)]
        
        call_count = [0]
        
        @asynccontextmanager
        async def mock_get(*args, **kwargs):
            call_count[0] += 1
            mock_resp = AsyncMock()
            if call_count[0] == 1:
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=page1_coins)
            else:
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=page2_coins)
            yield mock_resp
        
        # Create mock session
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = mock_get
        
        # Set the session directly
        analyzer.session = mock_session
        
        # Mock settings with API key (Demo API)
        with patch('signals.smart_signals.settings') as mock_settings:
            mock_settings.coingecko_api_key = "test_demo_api_key"
            mock_settings.smart_signals_scan_limit = 500
            
            # Mock asyncio.sleep to avoid delays
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # Execute the scan
                coins = await analyzer.scan_all_coins()
            
            # Verify we got all 500 coins
            assert len(coins) == 500
            assert coins[0]["id"] == "coin0"
            assert coins[499]["id"] == "coin499"
            
            # Verify get was called twice (Demo API also uses pagination)
            assert call_count[0] == 2
    
    @pytest.mark.asyncio
    async def test_scan_all_coins_handles_api_error(self):
        """Test that API errors are handled gracefully."""
        analyzer = SmartSignalAnalyzer()
        
        # Create mock responses - first page succeeds, second fails
        page1_coins = [{"id": f"coin{i}", "symbol": f"SYM{i}", "current_price": 100 + i} for i in range(250)]
        
        call_count = [0]
        
        @asynccontextmanager
        async def mock_get(*args, **kwargs):
            call_count[0] += 1
            mock_resp = AsyncMock()
            if call_count[0] == 1:
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=page1_coins)
            else:
                mock_resp.status = 400  # API error
            yield mock_resp
        
        # Create mock session
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = mock_get
        
        # Set the session directly
        analyzer.session = mock_session
        
        # Mock settings without API key
        with patch('signals.smart_signals.settings') as mock_settings:
            mock_settings.coingecko_api_key = ""
            mock_settings.smart_signals_scan_limit = 500
            
            # Mock asyncio.sleep to avoid delays
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # Execute the scan
                coins = await analyzer.scan_all_coins()
            
            # Should return partial results from successful first page
            assert len(coins) == 250
            assert coins[0]["id"] == "coin0"
            assert coins[249]["id"] == "coin249"
    
    @pytest.mark.asyncio
    async def test_scan_all_coins_handles_rate_limit(self):
        """Test that rate limits are handled with retry."""
        analyzer = SmartSignalAnalyzer()
        
        # Create mock responses
        page1_coins = [{"id": f"coin{i}", "symbol": f"SYM{i}", "current_price": 100 + i} for i in range(250)]
        
        call_count = [0]
        
        @asynccontextmanager
        async def mock_get(*args, **kwargs):
            call_count[0] += 1
            mock_resp = AsyncMock()
            if call_count[0] == 1:
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=page1_coins)
            elif call_count[0] == 2:
                mock_resp.status = 429  # Rate limit
            else:
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=page1_coins)
            yield mock_resp
        
        # Create mock session
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = mock_get
        
        # Set the session directly
        analyzer.session = mock_session
        
        # Mock settings without API key
        with patch('signals.smart_signals.settings') as mock_settings:
            mock_settings.coingecko_api_key = ""
            mock_settings.smart_signals_scan_limit = 500
            
            # Mock asyncio.sleep to avoid actual delays in tests
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # Execute the scan
                coins = await analyzer.scan_all_coins()
                
                # Should eventually get results after rate limit retry
                assert len(coins) >= 250
    
    @pytest.mark.asyncio
    async def test_scan_all_coins_handles_partial_page(self):
        """Test that scanning stops when receiving less coins than requested."""
        analyzer = SmartSignalAnalyzer()
        
        # Create mock responses - second page has fewer coins than requested
        page1_coins = [{"id": f"coin{i}", "symbol": f"SYM{i}", "current_price": 100 + i} for i in range(250)]
        page2_coins = [{"id": f"coin{i}", "symbol": f"SYM{i}", "current_price": 100 + i} for i in range(250, 300)]  # Only 50 coins
        
        call_count = [0]
        
        @asynccontextmanager
        async def mock_get(*args, **kwargs):
            call_count[0] += 1
            mock_resp = AsyncMock()
            if call_count[0] == 1:
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=page1_coins)
            else:
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=page2_coins)
            yield mock_resp
        
        # Create mock session
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = mock_get
        
        # Set the session directly
        analyzer.session = mock_session
        
        # Mock settings without API key
        with patch('signals.smart_signals.settings') as mock_settings:
            mock_settings.coingecko_api_key = ""
            mock_settings.smart_signals_scan_limit = 500
            
            # Mock asyncio.sleep to avoid delays
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # Execute the scan
                coins = await analyzer.scan_all_coins()
            
            # Should return 300 coins (250 + 50) and stop
            assert len(coins) == 300
            assert coins[0]["id"] == "coin0"
            assert coins[299]["id"] == "coin299"
