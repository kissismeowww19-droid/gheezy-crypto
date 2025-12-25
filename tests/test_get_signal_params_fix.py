"""
Test for get_signal_params fix - verifies that the method correctly calls data_source_manager.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestGetSignalParamsFix:
    """Test the fix for get_signal_params method."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    @pytest.mark.asyncio
    async def test_get_signal_params_calls_data_source_manager(self, analyzer):
        """Test that get_signal_params correctly calls data_source_manager.get_ohlcv_data."""
        
        # Mock market_data response
        mock_market_data = {
            'price_usd': 50000.0,
            'volume_24h': 1000000000,
            'change_24h': 5.0,
            'market_cap': 1000000000000
        }
        
        # Mock OHLCV data response
        mock_ohlcv_data = [
            {"open": 49000, "high": 50500, "low": 48500, "close": 50000, 
             "volumefrom": 1234, "volumeto": 120000000, "time": 1703520000}
        ]
        
        # Mock technical indicators response
        mock_technical_data = {
            'rsi': 55.0,
            'macd': 100,
            'signal': 90,
            'histogram': 10
        }
        
        # Mock signal data response
        mock_signal_data = {
            'direction': 'long',
            'probability': 65.0,
            'entry_price': 50000.0,
            'target1_price': 50750.0,
            'target2_price': 51000.0,
            'stop_loss_price': 49700.0
        }
        
        # Setup mocks
        with patch.object(analyzer, 'get_market_data', new_callable=AsyncMock) as mock_get_market:
            with patch.object(analyzer.data_source_manager, 'get_ohlcv_data', new_callable=AsyncMock) as mock_get_ohlcv:
                with patch.object(analyzer, 'calculate_technical_indicators', new_callable=AsyncMock) as mock_calc_tech:
                    with patch.object(analyzer, 'calculate_signal', return_value=mock_signal_data) as mock_calc_signal:
                        
                        mock_get_market.return_value = mock_market_data
                        mock_get_ohlcv.return_value = mock_ohlcv_data
                        mock_calc_tech.return_value = mock_technical_data
                        
                        # Call the method
                        result = await analyzer.get_signal_params("BTC")
                        
                        # Verify that data_source_manager.get_ohlcv_data was called correctly
                        mock_get_ohlcv.assert_called_once()
                        call_args = mock_get_ohlcv.call_args
                        
                        # Check that it was called with symbol and limit (no interval parameter)
                        assert call_args[0][0] == "BTC"  # First positional arg is symbol
                        assert call_args[1].get('limit') == 100  # limit keyword arg
                        
                        # Verify that calculate_technical_indicators was called with ohlcv_data
                        mock_calc_tech.assert_called_once_with("BTC", mock_ohlcv_data)
                        
                        # Verify result is returned
                        assert result is not None
                        assert 'direction' in result
    
    @pytest.mark.asyncio
    async def test_get_signal_params_handles_ohlcv_error(self, analyzer):
        """Test that get_signal_params handles errors when getting OHLCV data."""
        
        # Mock market_data response
        mock_market_data = {
            'price_usd': 50000.0,
            'volume_24h': 1000000000,
            'change_24h': 5.0,
            'market_cap': 1000000000000
        }
        
        # Mock technical indicators response (should work with None ohlcv_data)
        mock_technical_data = {
            'rsi': 55.0,
            'macd': 100,
            'signal': 90,
            'histogram': 10
        }
        
        # Setup mocks
        with patch.object(analyzer, 'get_market_data', new_callable=AsyncMock) as mock_get_market:
            with patch.object(analyzer.data_source_manager, 'get_ohlcv_data', new_callable=AsyncMock) as mock_get_ohlcv:
                with patch.object(analyzer, 'calculate_technical_indicators', new_callable=AsyncMock) as mock_calc_tech:
                    with patch.object(analyzer, 'calculate_signal', return_value={'direction': 'neutral'}) as mock_calc_signal:
                        
                        mock_get_market.return_value = mock_market_data
                        # Simulate an error when getting OHLCV data
                        mock_get_ohlcv.side_effect = Exception("API error")
                        mock_calc_tech.return_value = mock_technical_data
                        
                        # Call the method - should not raise an exception
                        result = await analyzer.get_signal_params("BTC")
                        
                        # Verify that calculate_technical_indicators was called with None for ohlcv_data
                        mock_calc_tech.assert_called_once_with("BTC", None)
                        
                        # Should still return a result
                        assert result is not None
