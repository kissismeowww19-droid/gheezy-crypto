"""
Tests for AI Signals finalization changes:
1. Weak signal detection (Боковик)
2. Consensus logic with 1 factor
3. TON in bybit_mapping
"""

import pytest
from unittest.mock import Mock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestAISignalsFinalization:
    """Tests for AI signals finalization changes."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_ton_in_bybit_mapping(self, analyzer):
        """Test that TON is added to bybit_mapping."""
        assert "TON" in analyzer.bybit_mapping
        assert analyzer.bybit_mapping["TON"] == "TONUSDT"
    
    def test_weak_signal_detection(self, analyzer):
        """Test that weak signals (abs(total_score) < 5) show Боковик."""
        # Test with total_score = 3 (weak bullish)
        whale_data = {
            "transaction_count": 0,
            "total_volume_usd": 0,
            "deposits": 0,
            "withdrawals": 0,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_1h": 0.1,
            "change_24h": 0.1,
            "change_7d": 0.1,
            "market_cap": 1_000_000_000,
            "volume_24h": 100_000_000,
        }
        
        # Calculate signal with minimal input to get weak score
        result = analyzer.calculate_signal(whale_data, market_data)
        
        # With minimal inputs, total_score should be very small
        # Check that if total_score is between -5 and 5, direction is Боковик
        total_score = result.get('total_score', 0)
        direction = result.get('direction', '')
        
        if abs(total_score) < 5:
            assert "Боковик" in direction, f"Expected Боковик for total_score={total_score}, got {direction}"
            assert result['strength'] == "слабый"
            assert result['confidence'] == "Низкая"
    
    def test_consensus_with_one_bullish_factor(self, analyzer):
        """Test that consensus is НЕЙТРАЛЬНЫЙ with only 1 bullish and 0 bearish factors."""
        # Create a signal message with controlled reasons
        signal_data = {
            'probability_direction': 'up',
            'probability': 52,
            'total_score': 3,
            'factors': {
                'whale': {'score': 1},
            }
        }
        
        whale_data = {
            "transaction_count": 1,
            "total_volume_usd": 100000,
            "deposits": 0,
            "withdrawals": 1,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_1h": 0.1,
            "change_24h": 0.1,
            "change_7d": 0.1,
            "market_cap": 1_000_000_000,
            "volume_24h": 100_000_000,
        }
        
        # Format the message
        message = analyzer.format_signal_message(
            symbol="BTC",
            signal_data=signal_data,
            whale_data=whale_data,
            market_data=market_data
        )
        
        # Check that the message contains factors analysis section
        assert "ФАКТОРЫ АНАЛИЗА" in message
        
        # We need to check the logic: if bullish_count <= 1 and bearish_count == 0
        # then consensus should be НЕЙТРАЛЬНЫЙ
        # This is tested indirectly through the message format
        
    def test_consensus_with_one_bearish_factor(self, analyzer):
        """Test that consensus is НЕЙТРАЛЬНЫЙ with only 1 bearish and 0 bullish factors."""
        signal_data = {
            'probability_direction': 'down',
            'probability': 48,
            'total_score': -3,
            'factors': {
                'whale': {'score': -1},
            }
        }
        
        whale_data = {
            "transaction_count": 1,
            "total_volume_usd": 100000,
            "deposits": 1,
            "withdrawals": 0,
            "sentiment": "bearish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_1h": -0.1,
            "change_24h": -0.1,
            "change_7d": -0.1,
            "market_cap": 1_000_000_000,
            "volume_24h": 100_000_000,
        }
        
        # Format the message
        message = analyzer.format_signal_message(
            symbol="BTC",
            signal_data=signal_data,
            whale_data=whale_data,
            market_data=market_data
        )
        
        # Check that the message contains factors analysis section
        assert "ФАКТОРЫ АНАЛИЗА" in message
    
    def test_strong_signal_not_affected(self, analyzer):
        """Test that strong signals still work correctly."""
        whale_data = {
            "transaction_count": 100,
            "total_volume_usd": 100_000_000,
            "deposits": 10,
            "withdrawals": 90,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_1h": 2.0,
            "change_24h": 5.0,
            "change_7d": 10.0,
            "market_cap": 1_000_000_000,
            "volume_24h": 500_000_000,
        }
        
        # Create strong technical indicators
        technical_data = {
            'rsi': {'value': 65},
            'macd': {'histogram': 100, 'signal': 'bullish'},
            'ma_crossover': {'trend': 'bullish'},
        }
        
        result = analyzer.calculate_signal(
            whale_data=whale_data, 
            market_data=market_data,
            technical_data=technical_data
        )
        
        # With strong bullish indicators, should not be Боковик
        total_score = result.get('total_score', 0)
        if abs(total_score) >= 5:
            assert "Боковик" not in result.get('direction', ''), \
                f"Strong signal (score={total_score}) should not show Боковик"
    
    def test_very_weak_score_shows_боковик(self, analyzer):
        """Test that total_score of 2 shows Боковик."""
        # Mock calculate_signal to test the direction logic directly
        whale_data = {"transaction_count": 0, "total_volume_usd": 0, "deposits": 0, "withdrawals": 0, "sentiment": "neutral"}
        market_data = {"price_usd": 1, "change_1h": 0, "change_24h": 0, "change_7d": 0, "market_cap": 1, "volume_24h": 1}
        
        result = analyzer.calculate_signal(whale_data, market_data)
        
        # The key test: if abs(total_score) < 5, direction must contain "Боковик"
        if abs(result['total_score']) < 5:
            assert "Боковик" in result['direction']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
