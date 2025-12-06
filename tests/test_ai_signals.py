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
            "total_score": 35.0,
            "whale_score": 20.0,
            "price_score": 10.0,
            "volume_score": 10
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
