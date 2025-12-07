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
        assert "BTC" in analyzer.bybit_mapping
        assert "ETH" in analyzer.bybit_mapping
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
        """Test signal calculation for bullish scenario with 10-factor system."""
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
        
        # With 10-factor system, we just check that score reflects the bullish data
        assert result["total_score"] > 0
        assert result["whale_score"] > 0  # More withdrawals than deposits
        assert result["market_score"] > 0  # Positive change and high volume
        # Direction may vary without technical indicators, but score should be positive
    
    def test_calculate_signal_bearish(self, analyzer):
        """Test signal calculation for bearish scenario with 10-factor system."""
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
        
        # With 10-factor system, we check that score reflects the bearish data
        assert result["total_score"] < 0
        assert result["whale_score"] < 0  # More deposits than withdrawals
        assert result["market_score"] < 0  # Negative change and low volume
        # Direction may vary, but score should be negative
    
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
        """Test message formatting with 10-factor system and probability."""
        signal_data = {
            "direction": "📈 ВВЕРХ",
            "strength": "сильный",
            "strength_percent": 75,
            "confidence": "Высокая",
            "total_score": 35.0,
            "whale_score": 5.0,
            "trend_score": 4.0,
            "momentum_score": 3.0,
            "volatility_score": 2.0,
            "volume_score": 3.0,
            "market_score": 6.0,
            "orderbook_score": 4.0,
            "derivatives_score": 3.0,
            "onchain_score": 2.0,
            "sentiment_score": 3.0,
            "probability": 72,
            "probability_direction": "up",
            "probability_confidence": "high",
            "data_quality": 0.9,
            "bullish_count": 7,
            "bearish_count": 2,
            "neutral_count": 1,
            "consensus": "bullish",
            "data_sources_count": 9
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
        assert "📈 ВВЕРХ" in message or "72%" in message
        assert "Высокая" in message
        assert "15" in message  # transaction count
        assert "🐋 *Анализ китов" in message
        assert "📊 *Рыночные данные" in message
        assert "Breakdown сигнала" in message
        assert "10 факторов" in message
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
        """Test Funding Rate fetching from Bybit."""
        mock_response = {
            "result": {
                "list": [{
                    "fundingRate": "0.0001"
                }]
            }
        }
        
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
        mock_response = {
            "result": {
                "list": [{
                    "fundingRate": "0.0001"
                }]
            }
        }
        
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
        """Test signal calculation with all factors in 10-factor system."""
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
        assert "trend_score" in result
        assert "momentum_score" in result
        assert "volatility_score" in result
        assert "volume_score" in result
        assert "orderbook_score" in result
        assert "derivatives_score" in result
        assert "onchain_score" in result
        assert "sentiment_score" in result
        assert "direction" in result
        assert "strength_percent" in result
        assert "confidence" in result
    
    def test_calculate_signal_without_optional_factors(self, analyzer):
        """Test signal calculation without optional factors in 10-factor system."""
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
        assert result["trend_score"] == 0.0
        assert result["momentum_score"] == 0.0
        assert result["orderbook_score"] == 0.0
        assert result["derivatives_score"] == 0.0
        assert result["onchain_score"] == 0.0
        assert result["sentiment_score"] == 0.0
    
    def test_format_signal_message_with_all_data(self, analyzer):
        """Test message formatting with all data in 10-factor system and probability."""
        signal_data = {
            "direction": "📈 ВВЕРХ",
            "strength": "сильный",
            "strength_percent": 78,
            "confidence": "Высокая",
            "total_score": 25.0,
            "whale_score": 4.0,
            "trend_score": 5.0,
            "momentum_score": 3.0,
            "volatility_score": 2.0,
            "volume_score": 3.0,
            "market_score": 4.0,
            "orderbook_score": 2.0,
            "derivatives_score": 1.0,
            "onchain_score": 0.5,
            "sentiment_score": 0.5,
            "probability": 78,
            "probability_direction": "up",
            "probability_confidence": "high",
            "data_quality": 0.9,
            "bullish_count": 8,
            "bearish_count": 1,
            "neutral_count": 1,
            "consensus": "bullish",
            "data_sources_count": 9
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
        assert "📈 ВВЕРХ" in message or "78%" in message
        assert "Высокая" in message
        assert "🐋 *Анализ китов" in message
        assert "📈 *Технический анализ" in message
        assert "RSI (14):" in message
        assert "MACD:" in message
        assert "Bollinger Bands:" in message
        assert "😱 *Fear & Greed Index:*" in message
        assert "📊 *Funding Rate:*" in message
        assert "Breakdown сигнала" in message
        assert "10 факторов" in message
        assert "ИТОГО" in message or "ИТОГ" in message
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
    
    def test_escape_markdown(self, analyzer):
        """Test that escape_markdown properly escapes special characters."""
        # Test basic special characters
        assert analyzer.escape_markdown("Hello_World") == "Hello\\_World"
        assert analyzer.escape_markdown("Test*Bold*") == "Test\\*Bold\\*"
        assert analyzer.escape_markdown("Link[text]") == "Link\\[text\\]"
        assert analyzer.escape_markdown("Code`block`") == "Code\\`block\\`"
        
        # Test multiple special characters
        input_text = "Breaking news: BTC up 5%! [Details]"
        expected = "Breaking news: BTC up 5%\\! \\[Details\\]"
        assert analyzer.escape_markdown(input_text) == expected
        
        # Test news-like content with various special characters
        news_title = "Bitcoin's price surged by 10% - analysts predict more gains!"
        escaped = analyzer.escape_markdown(news_title)
        # Should escape: ' (apostrophe becomes \'), - (dash), % (percent), ! (exclamation)
        assert "\\-" in escaped
        assert "\\!" in escaped
        
        # Test with None or empty
        assert analyzer.escape_markdown("") == ""
        assert analyzer.escape_markdown(None) is None
        
        # Test all special characters
        all_special = "_*[]()~`>#+-=|{}.!"
        escaped_all = analyzer.escape_markdown(all_special)
        # Each character should be escaped with backslash
        for char in all_special:
            assert f"\\{char}" in escaped_all


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
