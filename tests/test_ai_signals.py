"""
Tests for AI Signals module.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestAISignalAnalyzer:
    """Tests for AISignalAnalyzer class."""
    
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
    
    def test_initialization(self, analyzer):
        """Test that analyzer initializes correctly."""
        assert analyzer.whale_tracker is not None
        assert "BTC" in analyzer.blockchain_mapping
        assert "ETH" in analyzer.blockchain_mapping
        assert "BTC" in analyzer.coingecko_mapping
        assert "ETH" in analyzer.coingecko_mapping
        assert "BTC" in analyzer.binance_mapping
        assert "ETH" in analyzer.binance_mapping
        assert analyzer._cache == {}
        assert analyzer._cache_timestamps == {}
    
    @pytest.mark.asyncio
    async def test_get_whale_data_no_transactions(self, analyzer, mock_whale_tracker):
        """Test getting whale data when there are no transactions."""
        mock_whale_tracker.get_transactions_by_blockchain.return_value = []
        
        result = await analyzer.get_whale_data("BTC")
        
        assert result is not None
        assert result["transaction_count"] == 0
        assert result["total_volume_usd"] == 0
        assert result["deposits"] == 0
        assert result["withdrawals"] == 0
        assert result["sentiment"] == "neutral"
    
    @pytest.mark.asyncio
    async def test_get_whale_data_with_transactions(self, analyzer, mock_whale_tracker):
        """Test getting whale data with mock transactions."""
        # Create mock transactions
        mock_tx1 = Mock()
        mock_tx1.is_exchange_deposit = True
        mock_tx1.is_exchange_withdrawal = False
        mock_tx1.amount_usd = 1_000_000
        
        mock_tx2 = Mock()
        mock_tx2.is_exchange_deposit = False
        mock_tx2.is_exchange_withdrawal = True
        mock_tx2.amount_usd = 2_000_000
        
        mock_whale_tracker.get_transactions_by_blockchain.return_value = [mock_tx1, mock_tx2]
        
        result = await analyzer.get_whale_data("BTC")
        
        assert result is not None
        assert result["transaction_count"] == 2
        assert result["total_volume_usd"] == 3_000_000
        assert result["deposits"] == 1
        assert result["withdrawals"] == 1
        assert result["largest_transaction"] == 2_000_000
    
    def test_calculate_signal_bullish(self, analyzer):
        """Test signal calculation for bullish scenario."""
        whale_data = {
            "transaction_count": 10,
            "total_volume_usd": 50_000_000,
            "deposits": 2,
            "withdrawals": 8,
            "largest_transaction": 10_000_000,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": 5.0,
            "volume_24h": 20_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal(whale_data, market_data)
        
        assert result["total_score"] > 0
        assert "📈" in result["direction"]
        assert result["strength_percent"] > 50
    
    def test_calculate_signal_bearish(self, analyzer):
        """Test signal calculation for bearish scenario."""
        whale_data = {
            "transaction_count": 10,
            "total_volume_usd": 50_000_000,
            "deposits": 8,
            "withdrawals": 2,
            "largest_transaction": 10_000_000,
            "sentiment": "bearish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": -5.0,
            "volume_24h": 5_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal(whale_data, market_data)
        
        assert result["total_score"] < 0
        assert "📉" in result["direction"]
        assert result["strength_percent"] < 50
    
    def test_calculate_signal_neutral(self, analyzer):
        """Test signal calculation for neutral scenario."""
        whale_data = {
            "transaction_count": 10,
            "total_volume_usd": 50_000_000,
            "deposits": 5,
            "withdrawals": 5,
            "largest_transaction": 10_000_000,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": 0.5,
            "volume_24h": 8_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal(whale_data, market_data)
        
        # Score should be in neutral range (between -20 and 20)
        assert -20 <= result["total_score"] <= 20
        # Should show sideways/neutral direction
        assert "➡️" in result["direction"] or "📈" in result["direction"] or "📉" in result["direction"]
    
    def test_format_signal_message(self, analyzer):
        """Test message formatting."""
        signal_data = {
            "direction": "📈 ВВЕРХ",
            "strength": "сильный",
            "strength_percent": 75,
            "confidence": "Высокая",
            "total_score": 35.0,
            "whale_score": 20.0,
            "market_score": 10.0,
            "technical_score": 0,
            "rsi_score": 0,
            "macd_score": 0,
            "bb_score": 0,
            "fg_score": 0,
            "fr_score": 0
        }
        
        whale_data = {
            "transaction_count": 15,
            "total_volume_usd": 45_200_000,
            "deposits": 5,
            "withdrawals": 10,
            "largest_transaction": 10_000_000,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 98450,
            "change_24h": 2.3,
            "volume_24h": 28_500_000_000,
            "market_cap": 1_900_000_000_000
        }
        
        message = analyzer.format_signal_message("BTC", signal_data, whale_data, market_data)
        
        assert "🤖 *AI СИГНАЛ: BTC*" in message
        assert "📈 ВВЕРХ" in message
        assert "75%" in message
        assert "Высокая" in message
        assert "15" in message  # transaction count
        assert "🐋 *Анализ китов" in message
        assert "📊 *Рыночные данные" in message
        assert "Бычье" in message
        assert "⚠️" in message
        assert "🕐" in message
    
    @pytest.mark.asyncio
    async def test_analyze_coin_unsupported(self, analyzer):
        """Test analyzing unsupported coin."""
        result = await analyzer.analyze_coin("SOL")
        
        assert "❌ *Ошибка*" in result
        assert "не поддерживается" in result
    
    @pytest.mark.asyncio
    async def test_analyze_coin_market_data_error(self, analyzer, mock_whale_tracker):
        """Test analyzing when market data is unavailable."""
        mock_whale_tracker.get_transactions_by_blockchain.return_value = []
        
        with patch('signals.ai_signals.get_coin_price', new_callable=AsyncMock) as mock_get_price:
            mock_get_price.return_value = {"success": False}
            
            result = await analyzer.analyze_coin("BTC")
            
            assert "❌ *Ошибка получения данных*" in result
    
    @pytest.mark.asyncio
    async def test_get_price_history(self, analyzer):
        """Test fetching historical price data."""
        mock_response = {
            "prices": [
                [1638316800000, 50000],
                [1638320400000, 50100],
                [1638324000000, 50200]
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            
            result = await analyzer.get_price_history("BTC", days=1)
            
            assert result is not None
            assert len(result) == 3
            assert result[0] == 50000
            assert result[1] == 50100
            assert result[2] == 50200
    
    @pytest.mark.asyncio
    async def test_get_price_history_rate_limit(self, analyzer):
        """Test price history with rate limit."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 429
            
            result = await analyzer.get_price_history("BTC", days=1)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_price_history_caching(self, analyzer):
        """Test price history caching."""
        mock_response = {
            "prices": [[1638316800000, 50000], [1638320400000, 50100]]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            
            # First call
            result1 = await analyzer.get_price_history("BTC", days=1)
            assert result1 is not None
            
            # Second call should use cache
            result2 = await analyzer.get_price_history("BTC", days=1)
            assert result2 == result1
            
            # Should only call API once
            assert mock_get.call_count == 1
    
    @pytest.mark.asyncio
    async def test_calculate_technical_indicators(self, analyzer):
        """Test technical indicators calculation."""
        # Mock price history with enough data points
        mock_prices = [50000 + i * 100 for i in range(100)]
        
        with patch.object(analyzer, 'get_price_history', new_callable=AsyncMock) as mock_history:
            mock_history.return_value = mock_prices
            
            result = await analyzer.calculate_technical_indicators("BTC")
            
            assert result is not None
            assert "rsi" in result
            assert "macd" in result
            assert "bollinger_bands" in result
            
            # Check RSI structure
            assert "value" in result["rsi"]
            assert "signal" in result["rsi"]
            
            # Check MACD structure
            assert "macd_line" in result["macd"]
            assert "signal_line" in result["macd"]
            assert "histogram" in result["macd"]
            
            # Check BB structure
            assert "upper" in result["bollinger_bands"]
            assert "middle" in result["bollinger_bands"]
            assert "lower" in result["bollinger_bands"]
    
    @pytest.mark.asyncio
    async def test_calculate_technical_indicators_insufficient_data(self, analyzer):
        """Test technical indicators with insufficient data."""
        mock_prices = [50000, 50100]  # Only 2 points
        
        with patch.object(analyzer, 'get_price_history', new_callable=AsyncMock) as mock_history:
            mock_history.return_value = mock_prices
            
            result = await analyzer.calculate_technical_indicators("BTC")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_fear_greed_index(self, analyzer):
        """Test Fear & Greed Index fetching."""
        mock_response = {
            "data": [{
                "value": "75",
                "value_classification": "Greed"
            }]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            
            result = await analyzer.get_fear_greed_index()
            
            assert result is not None
            assert result["value"] == 75
            assert result["classification"] == "Greed"
    
    @pytest.mark.asyncio
    async def test_get_fear_greed_index_caching(self, analyzer):
        """Test Fear & Greed Index caching."""
        mock_response = {
            "data": [{
                "value": "75",
                "value_classification": "Greed"
            }]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            
            # First call
            result1 = await analyzer.get_fear_greed_index()
            assert result1 is not None
            
            # Second call should use cache
            result2 = await analyzer.get_fear_greed_index()
            assert result2 == result1
            
            # Should only call API once
            assert mock_get.call_count == 1
    
    @pytest.mark.asyncio
    async def test_get_funding_rate(self, analyzer):
        """Test Funding Rate fetching."""
        mock_response = [{
            "fundingRate": "0.0001"
        }]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            
            result = await analyzer.get_funding_rate("BTC")
            
            assert result is not None
            assert "rate" in result
            assert "rate_percent" in result
            assert result["rate"] == 0.0001
            assert result["rate_percent"] == 0.01
    
    @pytest.mark.asyncio
    async def test_get_funding_rate_caching(self, analyzer):
        """Test Funding Rate caching."""
        mock_response = [{
            "fundingRate": "0.0001"
        }]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.status = 200
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            
            # First call
            result1 = await analyzer.get_funding_rate("BTC")
            assert result1 is not None
            
            # Second call should use cache
            result2 = await analyzer.get_funding_rate("BTC")
            assert result2 == result1
            
            # Should only call API once
            assert mock_get.call_count == 1
    
    def test_calculate_signal_with_all_factors(self, analyzer):
        """Test signal calculation with all factors."""
        whale_data = {
            "transaction_count": 10,
            "total_volume_usd": 50_000_000,
            "deposits": 2,
            "withdrawals": 8,
            "largest_transaction": 10_000_000,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": 5.0,
            "volume_24h": 20_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        technical_data = {
            "rsi": {"value": 35, "signal": "neutral"},
            "macd": {"macd_line": 100, "signal_line": 90, "histogram": 10, "signal": "bullish"},
            "bollinger_bands": {
                "upper": 52000, "middle": 50000, "lower": 48000,
                "current_price": 48500, "position": "lower_half",
                "bandwidth": 4.0, "percent_b": 0.125
            }
        }
        
        fear_greed = {"value": 30, "classification": "Fear"}
        funding_rate = {"rate": 0.0001, "rate_percent": 0.01}
        
        result = analyzer.calculate_signal(
            whale_data, market_data, technical_data, fear_greed, funding_rate
        )
        
        assert result is not None
        assert "total_score" in result
        assert "whale_score" in result
        assert "market_score" in result
        assert "technical_score" in result
        assert "fg_score" in result
        assert "fr_score" in result
        assert "direction" in result
        assert "strength_percent" in result
        assert "confidence" in result
    
    def test_calculate_signal_without_optional_factors(self, analyzer):
        """Test signal calculation without optional factors."""
        whale_data = {
            "transaction_count": 10,
            "total_volume_usd": 50_000_000,
            "deposits": 5,
            "withdrawals": 5,
            "largest_transaction": 10_000_000,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": 1.0,
            "volume_24h": 8_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal(whale_data, market_data)
        
        assert result is not None
        assert result["technical_score"] == 0
        assert result["fg_score"] == 0
        assert result["fr_score"] == 0
    
    def test_format_signal_message_with_all_data(self, analyzer):
        """Test message formatting with all data."""
        signal_data = {
            "direction": "📈 ВВЕРХ",
            "strength": "сильный",
            "strength_percent": 78,
            "confidence": "Высокая",
            "total_score": 25.0,
            "whale_score": 8.0,
            "market_score": 6.0,
            "technical_score": 12.0,
            "rsi_score": 5.0,
            "macd_score": 10.0,
            "bb_score": -3.0,
            "fg_score": -3.0,
            "fr_score": 2.0
        }
        
        whale_data = {
            "transaction_count": 15,
            "total_volume_usd": 45_200_000,
            "deposits": 5,
            "withdrawals": 10,
            "largest_transaction": 10_000_000,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 98450,
            "change_24h": 2.3,
            "volume_24h": 28_500_000_000,
            "market_cap": 1_900_000_000_000
        }
        
        technical_data = {
            "rsi": {"value": 42.5, "signal": "neutral", "period": 14},
            "macd": {
                "macd_line": 125.4,
                "signal_line": 98.2,
                "histogram": 27.2,
                "signal": "bullish"
            },
            "bollinger_bands": {
                "upper": 100000,
                "middle": 98000,
                "lower": 96000,
                "current_price": 97200,
                "position": "lower_half",
                "bandwidth": 4.2,
                "percent_b": 0.35
            }
        }
        
        fear_greed = {"value": 68, "classification": "Greed"}
        funding_rate = {"rate": 0.00012, "rate_percent": 0.012}
        
        message = analyzer.format_signal_message(
            "BTC", signal_data, whale_data, market_data,
            technical_data, fear_greed, funding_rate
        )
        
        # Check all sections are present
        assert "🤖 *AI СИГНАЛ: BTC*" in message
        assert "📈 ВВЕРХ" in message
        assert "78%" in message
        assert "Высокая" in message
        assert "🐋 *Анализ китов" in message
        assert "📈 *Технический анализ" in message
        assert "RSI (14):" in message
        assert "MACD:" in message
        assert "Bollinger Bands:" in message
        assert "😱 *Fear & Greed Index:*" in message
        assert "📊 *Funding Rate:*" in message
        assert "🎯 *Breakdown сигнала:*" in message
        assert "Итого: +25 очков" in message
        assert "⚠️" in message
        assert "🕐" in message
    
    def test_cache_get_set(self, analyzer):
        """Test cache get/set functionality."""
        # Set cache
        test_data = {"value": 100}
        analyzer._set_cache("test_key", test_data)
        
        # Get from cache with long TTL
        result = analyzer._get_cache("test_key", 3600)
        assert result == test_data
        
        # Get from cache with expired TTL
        result_expired = analyzer._get_cache("test_key", 0)
        assert result_expired is None
        
        # Get non-existent key
        result_none = analyzer._get_cache("non_existent", 3600)
        assert result_none is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
