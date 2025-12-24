"""
Test for correct weight percentages display in ИТОГОВЫЙ РАСЧЁТ section.
"""

import pytest
import sys
import os
from unittest.mock import Mock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestWeightDisplayFix:
    """Tests for weight display fix in format_signal_message."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_btc_weight_percentages_display(self, analyzer):
        """Test that BTC shows correct weight percentages (with whale data)."""
        signal_data = {
            "symbol": "BTC",
            "direction": "📈 ВВЕРХ",
            "raw_direction": "long",
            "strength": "сильный",
            "strength_percent": 75,
            "confidence": "Высокая",
            "total_score": 35.0,
            "weighted_score": 5.5,
            "probability": 72,
            "probability_direction": "up",
            "factor_scores": {
                "whales": 5.0,
                "derivatives": 6.0,
                "trend": 4.0,
                "momentum": 3.0,
                "volume": 2.0,
                "adx": 1.0,
                "divergence": 1.0,
                "sentiment": 0.5,
                "macro": 0.3,
                "options": 0.2,
            },
            "data_sources": 10,
        }
        
        message = analyzer.format_signal_message(signal_data)
        
        # Check that BTC uses correct weights
        assert "× 25% =" in message  # whales
        assert "× 20% =" in message  # derivatives
        assert "× 15% =" in message  # trend
        assert "× 12% =" in message  # momentum
        assert "× 10% =" in message  # volume
        
        # Verify incorrect old percentages are NOT present
        assert "× 22% =" not in message  # old incorrect derivatives %
        assert "× 18% =" not in message  # old incorrect trend %
        assert "× 2% =" not in message   # old incorrect sentiment %
        
    def test_ton_weight_percentages_display(self, analyzer):
        """Test that TON shows correct weight percentages (without whale data)."""
        signal_data = {
            "symbol": "TON",
            "direction": "📈 ВВЕРХ",
            "raw_direction": "long",
            "strength": "сильный",
            "strength_percent": 75,
            "confidence": "Высокая",
            "total_score": 35.0,
            "weighted_score": 5.5,
            "probability": 72,
            "probability_direction": "up",
            "factor_scores": {
                "whales": 0.0,
                "derivatives": 6.0,
                "trend": 4.0,
                "momentum": 3.0,
                "volume": 2.0,
                "adx": 1.0,
                "divergence": 1.0,
                "sentiment": 0.5,
                "macro": 0.3,
                "options": 0.2,
            },
            "data_sources": 9,
        }
        
        message = analyzer.format_signal_message(signal_data)
        
        # Check that TON uses correct weights (no whale data)
        assert "× 0% =" in message   # whales (no data)
        assert "× 28% =" in message  # derivatives (increased)
        assert "× 22% =" in message  # trend (increased)
        assert "× 16% =" in message  # momentum (increased)
        assert "× 14% =" in message  # volume (increased)
        assert "× 6% =" in message   # adx (increased)
        
    def test_eth_weight_percentages_display(self, analyzer):
        """Test that ETH shows correct weight percentages (with whale data)."""
        signal_data = {
            "symbol": "ETH",
            "direction": "📉 ВНИЗ",
            "raw_direction": "short",
            "strength": "средний",
            "strength_percent": 60,
            "confidence": "Средняя",
            "total_score": 20.0,
            "weighted_score": 3.5,
            "probability": 65,
            "probability_direction": "down",
            "factor_scores": {
                "whales": 4.0,
                "derivatives": 5.0,
                "trend": 3.0,
                "momentum": 2.0,
                "volume": 2.0,
                "adx": 1.0,
                "divergence": 0.5,
                "sentiment": 0.5,
                "macro": 0.3,
                "options": 0.2,
            },
            "data_sources": 10,
        }
        
        message = analyzer.format_signal_message(signal_data)
        
        # Check that ETH uses correct weights (same as BTC)
        assert "× 25% =" in message  # whales
        assert "× 20% =" in message  # derivatives
        assert "× 15% =" in message  # trend
        
    def test_weight_calculation_matches_display(self, analyzer):
        """Test that weight calculations match displayed percentages."""
        signal_data = {
            "symbol": "BTC",
            "direction": "📈 ВВЕРХ",
            "raw_direction": "long",
            "strength": "сильный",
            "strength_percent": 75,
            "confidence": "Высокая",
            "total_score": 35.0,
            "weighted_score": 5.5,
            "probability": 72,
            "probability_direction": "up",
            "factor_scores": {
                "whales": 10.0,     # Max score
                "derivatives": 0.0,
                "trend": 0.0,
                "momentum": 0.0,
                "volume": 0.0,
                "adx": 0.0,
                "divergence": 0.0,
                "sentiment": 0.0,
                "macro": 0.0,
                "options": 0.0,
            },
            "data_sources": 10,
        }
        
        message = analyzer.format_signal_message(signal_data)
        
        # For BTC with whale score of 10.0, contribution should be 10.0 * 0.25 = 2.50
        # Check that the line shows: "• Киты:       +10.0 × 25% = +2.50"
        assert "Киты:       +10.0 × 25% = +2.50" in message
