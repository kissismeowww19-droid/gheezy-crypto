"""
Tests for Cross-Asset Correlation feature in AI Signals.
"""

import pytest
import time
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
            neutral_count=10,
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
            neutral_count=10,
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
        current_time = time.time()
        
        # Setup: BTC is in SHORT with strong negative score
        analyzer._correlation_signals["BTC"] = {
            "direction": "short",
            "probability": 67,
            "total_score": -13.0,
            "trend_score": -7.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
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
            neutral_count=10,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # ETH should be adjusted based on BTC
        # BTC influence: -13 * 0.70 = -9.1
        # Adjusted score: 14 + (-9.1) = 4.9
        # With abs(4.9) < 10, should become sideways
        assert new_direction == "sideways", f"Expected sideways, got {new_direction}"
        assert new_total_score < total_score, "Total score should be reduced by BTC influence"
        # Conflict should be detected only if long -> short or short -> long
        # long -> sideways is NOT a conflict
        assert is_conflict is False, "long -> sideways should not be a conflict"
    
    def test_ton_with_btc_short_signal(self, analyzer):
        """Test TON adjustment when BTC is in SHORT."""
        current_time = time.time()
        
        # Setup: BTC is in SHORT
        analyzer._correlation_signals["BTC"] = {
            "direction": "short",
            "probability": 67,
            "total_score": -13.0,
            "trend_score": -7.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
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
            neutral_count=10,
            data_sources_count=18,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # TON should be adjusted
        # BTC influence: -13 * 0.30 = -3.9
        # Adjusted score: 4 + (-3.9) = 0.1
        # With abs(0.1) < 15 (TON dead zone), should become sideways
        assert new_direction == "sideways", f"Expected sideways, got {new_direction}"
        assert new_total_score < total_score, "Total score should be reduced by BTC influence"
        # long -> sideways is NOT a conflict
        assert is_conflict is False, "long -> sideways should not be a conflict"
    
    def test_eth_long_with_btc_long_agreement(self, analyzer):
        """Test ETH LONG when BTC is also LONG (agreement bonus)."""
        current_time = time.time()
        
        # Setup: BTC is in LONG
        analyzer._correlation_signals["BTC"] = {
            "direction": "long",
            "probability": 70,
            "total_score": 20.0,
            "trend_score": 5.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
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
            neutral_count=10,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # Should stay LONG with positive BTC influence
        # BTC influence: 20 * 0.70 = 14.0
        # Adjusted score: 18 + 14 = 32
        assert new_direction == "long", f"Expected long, got {new_direction}"
        assert new_total_score > total_score, "Total score should increase with positive BTC"
        assert is_conflict is False, "No conflict when both in same direction"
    
    def test_eth_short_disagrees_with_btc_long(self, analyzer):
        """Test conflict detection when ETH is SHORT but BTC is LONG."""
        current_time = time.time()
        
        # Setup: BTC is in LONG
        analyzer._correlation_signals["BTC"] = {
            "direction": "long",
            "probability": 70,
            "total_score": 20.0,
            "trend_score": 5.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
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
            neutral_count=10,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # BTC influence: 20 * 0.70 = 14.0
        # Adjusted score: -11 + 14 = 3
        # With abs(3) < 10, should become sideways
        assert new_direction == "sideways", f"Expected sideways after BTC correction, got {new_direction}"
        # Conflict should NOT be detected when changing from short to sideways
        # Only long -> short or short -> long triggers conflict
        assert is_conflict is False, "short -> sideways should NOT be a conflict"
    
    def test_correlation_strength_differences(self, analyzer):
        """Test that ETH has stronger correlation (70%) than TON (30%)."""
        current_time = time.time()
        
        # Setup: BTC with strong signal
        analyzer._correlation_signals["BTC"] = {
            "direction": "long",
            "probability": 75,
            "total_score": 30.0,
            "trend_score": 8.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
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
            neutral_count=10,
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
            neutral_count=10,
            data_sources_count=20,
        )
        
        eth_adjusted_score = eth_result[2]
        ton_adjusted_score = ton_result[2]
        
        # ETH should get more influence (30 * 0.70 = 21.0)
        # TON should get less influence (30 * 0.30 = 9.0)
        assert eth_adjusted_score > ton_adjusted_score, "ETH should have stronger BTC correlation than TON"
        
        # ETH: 5 + 21.0 = 26.0 -> should be LONG (> 10)
        # TON: 5 + 9.0 = 14.0 -> should be LONG (> 10)
        assert eth_result[0] == "long", "ETH should be LONG with strong BTC influence"
    
    def test_conflict_detection_only_for_opposite_directions(self, analyzer):
        """Test that conflict is only detected for long<->short changes, not sideways."""
        current_time = time.time()
        
        # Setup: BTC is in LONG
        analyzer._correlation_signals["BTC"] = {
            "direction": "long",
            "probability": 75,
            "total_score": 30.0,
            "trend_score": 8.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        # Test 1: long -> sideways (NO conflict)
        result1 = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction="long",
            probability=60,
            total_score=5.0,  # weak long
            trend_score=1.0,
            block_trend_score=1.0,
            block_momentum_score=1.0,
            block_whales_score=1.0,
            block_derivatives_score=1.0,
            block_sentiment_score=1.0,
            bullish_count=11,
            bearish_count=9,
            neutral_count=10,
            data_sources_count=20,
        )
        # 5 + (30 * 0.40) = 5 + 12 = 17 -> long
        # No direction change, no conflict
        assert result1[3] is False, "long -> long should not be a conflict"
        
        # Test 2: sideways -> long (NO conflict)
        result2 = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction="sideways",
            probability=52,
            total_score=3.0,
            trend_score=0.5,
            block_trend_score=0.5,
            block_momentum_score=0.5,
            block_whales_score=0.5,
            block_derivatives_score=0.5,
            block_sentiment_score=0.5,
            bullish_count=10,
            bearish_count=10,
            neutral_count=10,
            data_sources_count=20,
        )
        # 3 + (30 * 0.40) = 3 + 12 = 15 -> long
        # sideways -> long is NOT a conflict
        assert result2[3] is False, "sideways -> long should not be a conflict"
        
        # Test 3: Setup BTC as SHORT, then ETH long -> should become sideways/short
        analyzer._correlation_signals["BTC"] = {
            "direction": "short",
            "probability": 70,
            "total_score": -30.0,
            "trend_score": -8.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        result3 = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction="long",
            probability=65,
            total_score=15.0,  # originally long
            trend_score=3.0,
            block_trend_score=3.0,
            block_momentum_score=2.0,
            block_whales_score=2.0,
            block_derivatives_score=2.0,
            block_sentiment_score=2.0,
            bullish_count=14,
            bearish_count=6,
            neutral_count=10,
            data_sources_count=20,
        )
        # With new 0.70 correlation: 15 + (-30 * 0.70) = 15 - 21 = -6 -> sideways (< 10)
        # long -> sideways is NOT a conflict
        assert result3[3] is False, "long -> sideways should not be a conflict"
        
        # Test 4: Strong opposite signal (long -> short) SHOULD be conflict
        result4 = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction="long",
            probability=62,
            total_score=5.0,  # weak long
            trend_score=1.0,
            block_trend_score=1.0,
            block_momentum_score=1.0,
            block_whales_score=0.5,
            block_derivatives_score=1.0,
            block_sentiment_score=0.5,
            bullish_count=11,
            bearish_count=9,
            neutral_count=10,
            data_sources_count=20,
        )
        # With new 0.70 correlation: 5 + (-30 * 0.70) = 5 - 21 = -16 -> short
        # long -> short IS a conflict (with stronger correlation)
        assert result4[3] is True, "long -> short should be a conflict"
        
        # Test 5: Very strong BTC SHORT forcing ETH from long to short
        analyzer._correlation_signals["BTC"] = {
            "direction": "short",
            "probability": 80,
            "total_score": -50.0,
            "trend_score": -10.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        result5 = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction="long",
            probability=62,
            total_score=8.0,  # weak long
            trend_score=1.5,
            block_trend_score=1.5,
            block_momentum_score=1.0,
            block_whales_score=1.0,
            block_derivatives_score=1.0,
            block_sentiment_score=1.0,
            bullish_count=12,
            bearish_count=8,
            neutral_count=10,
            data_sources_count=20,
        )
        # With new 0.70 correlation: 8 + (-50 * 0.70) = 8 - 35 = -27 -> short (< -10)
        # long -> short IS a conflict
        assert result5[0] == "short", f"Expected short, got {result5[0]}"
        assert result5[3] is True, "long -> short SHOULD be a conflict"


    def test_correlation_signals_storage_initialization(self, analyzer):
        """Test that _correlation_signals storage is initialized."""
        assert hasattr(analyzer, '_correlation_signals')
        assert isinstance(analyzer._correlation_signals, dict)
        assert len(analyzer._correlation_signals) == 0
    
    def test_correlation_signals_preserved_on_clear_cache(self, analyzer):
        """Test that _correlation_signals are NOT cleared when cache is cleared."""
        current_time = time.time()
        
        # Add a correlation signal
        analyzer._correlation_signals["BTC"] = {
            "direction": "long",
            "probability": 70,
            "total_score": 20.0,
            "trend_score": 5.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        # Add some cache data
        analyzer._cache["test_key"] = {"data": "test"}
        analyzer._cache_timestamps["test_key"] = time.time()
        
        # Clear cache
        analyzer.clear_cache()
        
        # Cache should be cleared
        assert len(analyzer._cache) == 0
        assert len(analyzer._cache_timestamps) == 0
        
        # But correlation signals should be preserved
        assert len(analyzer._correlation_signals) == 1
        assert "BTC" in analyzer._correlation_signals
        assert analyzer._correlation_signals["BTC"]["direction"] == "long"
    
    def test_cleanup_expired_signals(self, analyzer):
        """Test that expired signals are removed by cleanup."""
        current_time = time.time()
        
        # Add a fresh signal (not expired)
        analyzer._correlation_signals["BTC"] = {
            "direction": "long",
            "probability": 70,
            "total_score": 20.0,
            "trend_score": 5.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,  # expires in 10 minutes
        }
        
        # Add an expired signal
        analyzer._correlation_signals["ETH"] = {
            "direction": "short",
            "probability": 65,
            "total_score": -15.0,
            "trend_score": -4.0,
            "generated_at": current_time - 700,  # 11.67 minutes ago
            "expires_at": current_time - 100,  # expired 100 seconds ago
        }
        
        # Run cleanup
        analyzer._cleanup_expired_signals()
        
        # Fresh signal should remain
        assert "BTC" in analyzer._correlation_signals
        
        # Expired signal should be removed
        assert "ETH" not in analyzer._correlation_signals
    
    def test_eth_with_expired_btc_signal(self, analyzer):
        """Test that expired BTC signal is not used for ETH correlation."""
        current_time = time.time()
        
        # Add an expired BTC signal
        analyzer._correlation_signals["BTC"] = {
            "direction": "short",
            "probability": 67,
            "total_score": -13.0,
            "trend_score": -7.0,
            "generated_at": current_time - 700,  # 11.67 minutes ago
            "expires_at": current_time - 100,  # expired
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
            neutral_count=10,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # ETH should NOT be adjusted because BTC signal is expired
        assert new_direction == direction
        assert new_probability == probability
        assert new_total_score == total_score
        assert is_conflict is False
    
    def test_eth_with_fresh_btc_signal(self, analyzer):
        """Test that fresh BTC signal IS used for ETH correlation."""
        current_time = time.time()
        
        # Add a fresh BTC signal
        analyzer._correlation_signals["BTC"] = {
            "direction": "short",
            "probability": 67,
            "total_score": -13.0,
            "trend_score": -7.0,
            "generated_at": current_time,  # just now
            "expires_at": current_time + 600,  # expires in 10 minutes
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
            neutral_count=10,
            data_sources_count=20,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # ETH SHOULD be adjusted
        # BTC influence: -13 * 0.40 = -5.2
        # Adjusted score: 14 + (-5.2) = 8.8
        assert new_total_score < total_score, "Total score should be reduced by BTC influence"
        assert new_direction == "sideways", f"Expected sideways after BTC correlation, got {new_direction}"
    
    def test_correlation_signal_ttl_constant(self, analyzer):
        """Test that CORRELATION_SIGNAL_TTL constant exists and is 600 seconds (10 minutes)."""
        assert hasattr(analyzer, 'CORRELATION_SIGNAL_TTL')
        assert analyzer.CORRELATION_SIGNAL_TTL == 600


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
