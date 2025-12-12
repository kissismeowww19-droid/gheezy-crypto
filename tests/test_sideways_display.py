"""
Tests for sideways display in Telegram messages.
"""

import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestSidewaysDisplay:
    """Tests for sideways signal display in format_signal_message."""
    
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
    
    @pytest.fixture
    def base_market_data(self):
        """Base market data for testing."""
        return {
            'price_usd': 45000.0,
            'market_cap': 900000000000,
            'volume_24h': 30000000000,
            'change_1h': 0.5,
            'change_24h': 1.2,
            'change_7d': -2.3,
        }
    
    @pytest.fixture
    def base_short_term_data(self):
        """Base short-term data for testing."""
        return {
            'current_price': 45000.0,
            'price_1h_ago': 44775.0,
            'price_10min_ago': 44955.0,
        }
    
    @pytest.fixture
    def base_whale_data(self):
        """Base whale data for testing."""
        return {
            'transaction_count': 5,
            'total_volume_usd': 10000000,
            'buy_volume_usd': 6000000,
            'sell_volume_usd': 4000000,
        }
    
    def test_sideways_signal_display(self, analyzer, base_market_data, base_short_term_data, base_whale_data):
        """Test that sideways signal displays correctly with range instead of TP/SL."""
        # Create signal data for sideways (score between -10 and +10)
        signal_data = {
            'symbol': 'BTC',
            'direction': '➡️ Боковик',
            'raw_direction': 'sideways',
            'probability_direction': 'sideways',
            'probability': 55,
            'total_score': 5.0,
            'strength': 'слабый',
            'confidence': 'Низкая',
            'block_trend_score': 1.2,
            'block_momentum_score': 0.8,
            'block_whales_score': 1.5,
            'block_derivatives_score': 0.9,
            'block_sentiment_score': 0.6,
        }
        
        # Format message
        message = analyzer.format_signal_message(
            symbol='BTC',
            signal_data=signal_data,
            whale_data=base_whale_data,
            market_data=base_market_data,
            short_term_data=base_short_term_data,
            is_cross_conflict=False
        )
        
        # Verify sideways direction is displayed
        assert '➡️' in message, "Sideways emoji should be present"
        assert 'Боковик' in message, "Sideways text should be present"
        
        # Verify range is displayed instead of TP/SL
        assert 'Верх диапазона' in message, "Range high should be displayed"
        assert 'Низ диапазона' in message, "Range low should be displayed"
        assert 'Ожидается движение в диапазоне' in message, "Range message should be displayed"
        
        # Verify TP/SL are NOT displayed for sideways
        assert 'TP1' not in message, "TP1 should not be displayed for sideways"
        assert 'TP2' not in message, "TP2 should not be displayed for sideways"
        assert 'SL' not in message or 'Низ диапазона' in message, "SL should not be displayed independently for sideways"
    
    def test_long_signal_display(self, analyzer, base_market_data, base_short_term_data, base_whale_data):
        """Test that long signal displays correctly with TP/SL."""
        # Create signal data for long (score >= 10)
        signal_data = {
            'symbol': 'BTC',
            'direction': '📈 ЛОНГ',
            'raw_direction': 'long',
            'probability_direction': 'up',
            'probability': 70,
            'total_score': 25.0,
            'strength': 'сильный',
            'confidence': 'Высокая',
            'block_trend_score': 5.2,
            'block_momentum_score': 4.8,
            'block_whales_score': 5.5,
            'block_derivatives_score': 4.9,
            'block_sentiment_score': 4.6,
        }
        
        # Format message
        message = analyzer.format_signal_message(
            symbol='BTC',
            signal_data=signal_data,
            whale_data=base_whale_data,
            market_data=base_market_data,
            short_term_data=base_short_term_data,
            is_cross_conflict=False
        )
        
        # Verify long direction is displayed
        assert '📈' in message, "Long emoji should be present"
        assert 'ЛОНГ' in message, "Long text should be present"
        
        # Verify TP/SL are displayed
        assert 'TP1' in message, "TP1 should be displayed for long"
        assert 'TP2' in message, "TP2 should be displayed for long"
        assert '🛑 SL' in message, "SL should be displayed for long"
        
        # Verify range is NOT displayed for long
        assert 'Верх диапазона' not in message, "Range high should not be displayed for long"
        assert 'Низ диапазона' not in message, "Range low should not be displayed for long"
    
    def test_short_signal_display(self, analyzer, base_market_data, base_short_term_data, base_whale_data):
        """Test that short signal displays correctly with TP/SL."""
        # Create signal data for short (score <= -10)
        signal_data = {
            'symbol': 'BTC',
            'direction': '📉 ШОРТ',
            'raw_direction': 'short',
            'probability_direction': 'down',
            'probability': 68,
            'total_score': -22.0,
            'strength': 'средний',
            'confidence': 'Средняя',
            'block_trend_score': -4.2,
            'block_momentum_score': -3.8,
            'block_whales_score': -4.5,
            'block_derivatives_score': -5.9,
            'block_sentiment_score': -3.6,
        }
        
        # Format message
        message = analyzer.format_signal_message(
            symbol='BTC',
            signal_data=signal_data,
            whale_data=base_whale_data,
            market_data=base_market_data,
            short_term_data=base_short_term_data,
            is_cross_conflict=False
        )
        
        # Verify short direction is displayed
        assert '📉' in message, "Short emoji should be present"
        assert 'ШОРТ' in message, "Short text should be present"
        
        # Verify TP/SL are displayed
        assert 'TP1' in message, "TP1 should be displayed for short"
        assert 'TP2' in message, "TP2 should be displayed for short"
        assert '🛑 SL' in message, "SL should be displayed for short"
        
        # Verify range is NOT displayed for short
        assert 'Верх диапазона' not in message, "Range high should not be displayed for short"
        assert 'Низ диапазона' not in message, "Range low should not be displayed for short"
    
    def test_sideways_range_calculation(self, analyzer, base_market_data, base_short_term_data, base_whale_data):
        """Test that sideways range is calculated correctly (+/- 1%)."""
        signal_data = {
            'symbol': 'BTC',
            'direction': '➡️ Боковик',
            'raw_direction': 'sideways',
            'probability_direction': 'sideways',
            'probability': 58,
            'total_score': 3.0,
            'strength': 'слабый',
            'confidence': 'Низкая',
            'block_trend_score': 0.5,
            'block_momentum_score': 0.3,
            'block_whales_score': 0.8,
            'block_derivatives_score': 0.7,
            'block_sentiment_score': 0.7,
        }
        
        # Format message
        message = analyzer.format_signal_message(
            symbol='BTC',
            signal_data=signal_data,
            whale_data=base_whale_data,
            market_data=base_market_data,
            short_term_data=base_short_term_data,
            is_cross_conflict=False
        )
        
        # Calculate expected range
        current_price = 45000.0
        expected_high = current_price * 1.01  # +1%
        expected_low = current_price * 0.99   # -1%
        
        # Verify range values are present (approximate check due to formatting)
        assert '45,450' in message or '45450' in message, f"Range high should be approximately {expected_high}"
        assert '44,550' in message or '44550' in message, f"Range low should be approximately {expected_low}"
        assert '+1.0%' in message, "Range high percentage should be displayed"
        assert '-1.0%' in message, "Range low percentage should be displayed"
