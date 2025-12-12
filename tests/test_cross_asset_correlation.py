"""
Tests for Cross-Asset Correlation feature in AI Signals.
"""

import pytest
from unittest.mock import Mock, AsyncMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestCrossAssetCorrelation:
    """Tests for cross-asset correlation check."""
    
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
    
    def test_last_symbol_signals_initialization(self, analyzer):
        """Test that last_symbol_signals is initialized."""
        assert hasattr(analyzer, 'last_symbol_signals')
        assert isinstance(analyzer.last_symbol_signals, dict)
        assert len(analyzer.last_symbol_signals) == 0
    
    def test_btc_no_correlation_adjustment(self, analyzer):
        """Test that BTC signal is not adjusted (leading indicator)."""
        direction = "long"
        probability = 70
        total_score = 20.0
        
        result = analyzer._cross_asset_correlation_check(
            symbol="BTC",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=5.0,
            block_trend_score=5.0,
            block_momentum_score=3.0,
            block_whales_score=2.0,
            block_derivatives_score=4.0,
            block_sentiment_score=1.0,
            bullish_count=15,
            bearish_count=5,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # BTC should not be adjusted
        assert new_direction == direction
        assert new_probability == probability
        assert new_total_score == total_score
        assert is_conflict is False
    
    def test_eth_no_btc_signal(self, analyzer):
        """Test ETH when BTC signal doesn't exist yet."""
        direction = "long"
        probability = 78
        total_score = 14.0
        
        result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=3.0,
            block_trend_score=3.0,
            block_momentum_score=2.0,
            block_whales_score=1.0,
            block_derivatives_score=3.0,
            block_sentiment_score=2.0,
            bullish_count=12,
            bearish_count=8,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # Without BTC signal, no adjustment should happen
        assert new_direction == direction
        assert new_probability == probability
        assert new_total_score == total_score
        assert is_conflict is False
    
    def test_eth_with_btc_short_signal(self, analyzer):
        """Test ETH adjustment when BTC is in SHORT."""
        # Setup: BTC is in SHORT with strong negative score
        analyzer.last_symbol_signals["BTC"] = {
            "direction": "short",
            "probability": 67,
            "total_score": -13.0,
            "trend_score": -7.0,
            "generated_at": 1234567890
        }
        
        # ETH originally LONG
        direction = "long"
        probability = 78
        total_score = 14.0
        
        result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=3.0,
            block_trend_score=3.0,
            block_momentum_score=2.0,
            block_whales_score=1.0,
            block_derivatives_score=3.0,
            block_sentiment_score=2.0,
            bullish_count=12,
            bearish_count=8,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # ETH should be adjusted based on BTC
        # BTC influence: -13 * 0.35 = -4.55
        # Adjusted score: 14 + (-4.55) = 9.45
        # With abs(9.45) < 10, should become sideways
        assert new_direction == "sideways", f"Expected sideways, got {new_direction}"
        assert new_total_score < total_score, "Total score should be reduced by BTC influence"
        # Conflict should be detected (long -> sideways is not a conflict for our logic)
        # But long -> short would be
    
    def test_ton_with_btc_short_signal(self, analyzer):
        """Test TON adjustment when BTC is in SHORT."""
        # Setup: BTC is in SHORT
        analyzer.last_symbol_signals["BTC"] = {
            "direction": "short",
            "probability": 67,
            "total_score": -13.0,
            "trend_score": -7.0,
            "generated_at": 1234567890
        }
        
        # TON originally LONG (weak)
        direction = "long"
        probability = 58
        total_score = 4.0
        
        result = analyzer._cross_asset_correlation_check(
            symbol="TON",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=1.0,
            block_trend_score=1.0,
            block_momentum_score=1.0,
            block_whales_score=0.5,
            block_derivatives_score=1.0,
            block_sentiment_score=0.5,
            bullish_count=10,
            bearish_count=10,
            data_sources_count=18,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # TON should be adjusted
        # BTC influence: -13 * 0.25 = -3.25
        # Adjusted score: 4 + (-3.25) = 0.75
        # With abs(0.75) < 15 (TON dead zone), should become sideways
        assert new_direction == "sideways", f"Expected sideways, got {new_direction}"
        assert new_total_score < total_score, "Total score should be reduced by BTC influence"
    
    def test_eth_long_with_btc_long_agreement(self, analyzer):
        """Test ETH LONG when BTC is also LONG (agreement bonus)."""
        # Setup: BTC is in LONG
        analyzer.last_symbol_signals["BTC"] = {
            "direction": "long",
            "probability": 70,
            "total_score": 20.0,
            "trend_score": 5.0,
            "generated_at": 1234567890
        }
        
        # ETH also LONG
        direction = "long"
        probability = 72
        total_score = 18.0
        
        result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=4.0,
            block_trend_score=4.0,
            block_momentum_score=3.0,
            block_whales_score=2.0,
            block_derivatives_score=3.0,
            block_sentiment_score=2.0,
            bullish_count=15,
            bearish_count=5,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # Should stay LONG with positive BTC influence
        # BTC influence: 20 * 0.35 = 7.0
        # Adjusted score: 18 + 7 = 25
        assert new_direction == "long", f"Expected long, got {new_direction}"
        assert new_total_score > total_score, "Total score should increase with positive BTC"
        assert is_conflict is False, "No conflict when both in same direction"
    
    def test_eth_short_disagrees_with_btc_long(self, analyzer):
        """Test conflict detection when ETH is SHORT but BTC is LONG."""
        # Setup: BTC is in LONG
        analyzer.last_symbol_signals["BTC"] = {
            "direction": "long",
            "probability": 70,
            "total_score": 20.0,
            "trend_score": 5.0,
            "generated_at": 1234567890
        }
        
        # ETH SHORT (weak)
        direction = "short"
        probability = 55
        total_score = -11.0
        
        result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=-2.0,
            block_trend_score=-2.0,
            block_momentum_score=-1.0,
            block_whales_score=-1.0,
            block_derivatives_score=-2.0,
            block_sentiment_score=-1.0,
            bullish_count=8,
            bearish_count=12,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # BTC influence: 20 * 0.35 = 7.0
        # Adjusted score: -11 + 7 = -4
        # With abs(-4) < 10, should become sideways
        assert new_direction == "sideways", f"Expected sideways after BTC correction, got {new_direction}"
        # Conflict detected since original was short
        assert is_conflict is True, "Conflict should be detected when changing from short to sideways"
    
    def test_correlation_strength_differences(self, analyzer):
        """Test that ETH has stronger correlation (35%) than TON (25%)."""
        # Setup: BTC with strong signal
        analyzer.last_symbol_signals["BTC"] = {
            "direction": "long",
            "probability": 75,
            "total_score": 30.0,
            "trend_score": 8.0,
            "generated_at": 1234567890
        }
        
        # Test ETH
        eth_result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction="sideways",
            probability=52,
            total_score=5.0,
            trend_score=1.0,
            block_trend_score=1.0,
            block_momentum_score=1.0,
            block_whales_score=1.0,
            block_derivatives_score=1.0,
            block_sentiment_score=1.0,
            bullish_count=10,
            bearish_count=10,
            data_sources_count=20,
        )
        
        # Test TON
        ton_result = analyzer._cross_asset_correlation_check(
            symbol="TON",
            direction="sideways",
            probability=52,
            total_score=5.0,
            trend_score=1.0,
            block_trend_score=1.0,
            block_momentum_score=1.0,
            block_whales_score=1.0,
            block_derivatives_score=1.0,
            block_sentiment_score=1.0,
            bullish_count=10,
            bearish_count=10,
            data_sources_count=20,
        )
        
        eth_adjusted_score = eth_result[2]
        ton_adjusted_score = ton_result[2]
        
        # ETH should get more influence (30 * 0.35 = 10.5)
        # TON should get less influence (30 * 0.25 = 7.5)
        assert eth_adjusted_score > ton_adjusted_score, "ETH should have stronger BTC correlation than TON"
        
        # ETH: 5 + 10.5 = 15.5 -> should be LONG
        # TON: 5 + 7.5 = 12.5 -> could be sideways or LONG depending on dead zone
        assert eth_result[0] == "long", "ETH should be LONG with strong BTC influence"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
