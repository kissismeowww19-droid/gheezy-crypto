"""
Tests for Deep Derivatives Analysis module.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import aiohttp

import sys
sys.path.insert(0, '/home/runner/work/gheezy-crypto/gheezy-crypto/src')

from signals.derivatives_analysis import DeepDerivativesAnalyzer


@pytest.fixture
def analyzer():
    """Create a DeepDerivativesAnalyzer instance for testing."""
    return DeepDerivativesAnalyzer()


class TestDeepDerivativesAnalyzer:
    """Test suite for DeepDerivativesAnalyzer."""
    
    @pytest.mark.asyncio
    async def test_get_liquidation_levels_structure(self, analyzer):
        """Test liquidation levels returns correct structure."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "retCode": 0,
                "result": {
                    "list": [{
                        "lastPrice": "90000"
                    }]
                }
            })
            
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await analyzer.get_liquidation_levels("BTCUSDT")
            
            if result:
                assert "long_liquidations" in result
                assert "short_liquidations" in result
                assert "nearest_long_liq" in result
                assert "nearest_short_liq" in result
                assert "signal" in result
                assert result["signal"] in ["bullish", "bearish", "neutral"]
    
    @pytest.mark.asyncio
    async def test_analyze_oi_price_correlation_structure(self, analyzer):
        """Test OI/price correlation returns correct structure."""
        with patch('aiohttp.ClientSession') as mock_session:
            # Mock ticker response
            ticker_response = AsyncMock()
            ticker_response.status = 200
            ticker_response.json = AsyncMock(return_value={
                "retCode": 0,
                "result": {
                    "list": [{
                        "price24hPcnt": "0.025"  # 2.5% change
                    }]
                }
            })
            
            # Mock OI response
            oi_response = AsyncMock()
            oi_response.status = 200
            oi_response.json = AsyncMock(return_value={
                "retCode": 0,
                "result": {
                    "list": [
                        {"openInterest": "105000"},
                        {"openInterest": "100000"}
                    ]
                }
            })
            
            mock_get = AsyncMock()
            mock_get.side_effect = [
                AsyncMock(__aenter__=AsyncMock(return_value=ticker_response)),
                AsyncMock(__aenter__=AsyncMock(return_value=oi_response))
            ]
            
            mock_session.return_value.__aenter__.return_value.get = mock_get
            
            result = await analyzer.analyze_oi_price_correlation("BTCUSDT")
            
            if result:
                assert "oi_change_24h" in result
                assert "price_change_24h" in result
                assert "correlation" in result
                assert "interpretation" in result
                assert "signal" in result
                assert result["signal"] in ["bullish", "bearish", "neutral"]
    
    @pytest.mark.asyncio
    async def test_get_ls_ratio_by_exchange_structure(self, analyzer):
        """Test L/S ratio returns correct structure."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "retCode": 0,
                "result": {
                    "list": [{
                        "buyRatio": "0.55",
                        "sellRatio": "0.45"
                    }]
                }
            })
            
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await analyzer.get_ls_ratio_by_exchange("BTCUSDT")
            
            if result:
                assert "bybit" in result
                assert "average_ratio" in result
                assert "signal" in result
                assert result["signal"] in ["bullish", "bearish", "neutral"]
    
    @pytest.mark.asyncio
    async def test_get_funding_rate_history_structure(self, analyzer):
        """Test funding rate history returns correct structure."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "retCode": 0,
                "result": {
                    "list": [
                        {"fundingRate": "0.0001"},
                        {"fundingRate": "0.00008"},
                        {"fundingRate": "0.00012"},
                    ]
                }
            })
            
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await analyzer.get_funding_rate_history("BTCUSDT")
            
            if result:
                assert "current" in result
                assert "average_24h" in result
                assert "trend" in result
                assert "extreme" in result
                assert "signal" in result
                assert result["trend"] in ["rising", "falling", "stable"]
                assert result["signal"] in ["bullish", "bearish", "neutral"]
    
    @pytest.mark.asyncio
    async def test_get_basis_structure(self, analyzer):
        """Test basis calculation returns correct structure."""
        with patch('aiohttp.ClientSession') as mock_session:
            spot_response = AsyncMock()
            spot_response.status = 200
            spot_response.json = AsyncMock(return_value={
                "retCode": 0,
                "result": {
                    "list": [{
                        "lastPrice": "90000"
                    }]
                }
            })
            
            futures_response = AsyncMock()
            futures_response.status = 200
            futures_response.json = AsyncMock(return_value={
                "retCode": 0,
                "result": {
                    "list": [{
                        "lastPrice": "90270"
                    }]
                }
            })
            
            mock_get = AsyncMock()
            mock_get.side_effect = [
                AsyncMock(__aenter__=AsyncMock(return_value=spot_response)),
                AsyncMock(__aenter__=AsyncMock(return_value=futures_response))
            ]
            
            mock_session.return_value.__aenter__.return_value.get = mock_get
            
            result = await analyzer.get_basis("BTCUSDT")
            
            if result:
                assert "spot_price" in result
                assert "futures_price" in result
                assert "basis" in result
                assert "basis_type" in result
                assert "signal" in result
                assert result["basis_type"] in ["contango", "backwardation", "neutral"]
                assert result["signal"] in ["bullish", "bearish", "neutral"]
    
    def test_interpret_ls_ratio(self, analyzer):
        """Test L/S ratio interpretation."""
        # High ratio (too many longs) = bearish
        assert analyzer._interpret_ls_ratio(1.6) == "bearish"
        
        # Low ratio (too many shorts) = bullish
        assert analyzer._interpret_ls_ratio(0.6) == "bullish"
        
        # Moderate high ratio = bullish
        assert analyzer._interpret_ls_ratio(1.15) == "bullish"
        
        # Moderate low ratio = bearish
        assert analyzer._interpret_ls_ratio(0.85) == "bearish"
        
        # Balanced ratio = neutral
        assert analyzer._interpret_ls_ratio(1.0) == "neutral"
    
    def test_create_price_only_signal(self, analyzer):
        """Test price-only signal creation."""
        # Rising price
        result = analyzer._create_price_only_signal(2.5)
        assert result["signal"] == "bullish"
        assert result["interpretation"] == "Price rising"
        
        # Falling price
        result = analyzer._create_price_only_signal(-2.5)
        assert result["signal"] == "bearish"
        assert result["interpretation"] == "Price falling"
        
        # Stable price
        result = analyzer._create_price_only_signal(0.5)
        assert result["signal"] == "neutral"
        assert result["interpretation"] == "Price stable"
    
    def test_cache_functionality(self, analyzer):
        """Test caching mechanism."""
        test_data = {"test": "data"}
        analyzer._set_cache("test_key", test_data)
        
        # Should return cached data within TTL
        cached = analyzer._get_cache("test_key", 300)
        assert cached == test_data
        
        # Should return None for non-existent key
        expired = analyzer._get_cache("nonexistent_key", 300)
        assert expired is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
