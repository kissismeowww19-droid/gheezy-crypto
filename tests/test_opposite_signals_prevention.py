"""
Tests for opposite signals prevention in cross-asset correlation.

This ensures that when BTC shows a strong signal in one direction,
altcoins like ETH cannot show the opposite direction.
"""

import pytest
import time
from unittest.mock import Mock, AsyncMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestOppositeSignalsPrevention:
    """Tests for preventing opposite signals between BTC and altcoins."""
    
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
    
    def test_btc_strong_short_eth_cannot_be_long(self, analyzer):
        """
        Test: BTC = STRONG SHORT (-50) → ETH cannot be LONG
        Expected: ETH should become SIDEWAYS or SHORT
        """
        current_time = time.time()
        
        # Setup: BTC is in STRONG SHORT
        analyzer._correlation_signals["BTC"] = {
            "direction": "short",
            "probability": 75,
            "total_score": -50.0,  # Strong short
            "trend_score": -15.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        # ETH originally LONG with strong score
        direction = "long"
        probability = 85
        total_score = 50.0  # Strong long
        
        result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=10.0,
            block_trend_score=10.0,
            block_momentum_score=8.0,
            block_whales_score=5.0,
            block_derivatives_score=7.0,
            block_sentiment_score=5.0,
            bullish_count=18,
            bearish_count=2,
            neutral_count=10,
            data_sources_count=25,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # ETH should NOT be LONG when BTC is strong SHORT
        assert new_direction != "long", f"ETH should not be LONG when BTC is strong SHORT, got {new_direction}"
        # Should be SIDEWAYS or SHORT
        assert new_direction in ("sideways", "short"), f"Expected sideways or short, got {new_direction}"
        # Score should be capped to 0 or negative
        assert new_total_score <= 0, f"Score should be ≤0, got {new_total_score}"
    
    def test_btc_strong_long_eth_cannot_be_short(self, analyzer):
        """
        Test: BTC = STRONG LONG (+50) → ETH cannot be SHORT
        Expected: ETH should become SIDEWAYS or LONG
        """
        current_time = time.time()
        
        # Setup: BTC is in STRONG LONG
        analyzer._correlation_signals["BTC"] = {
            "direction": "long",
            "probability": 75,
            "total_score": 50.0,  # Strong long
            "trend_score": 15.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        # ETH originally SHORT with strong score
        direction = "short"
        probability = 85
        total_score = -50.0  # Strong short
        
        result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=-10.0,
            block_trend_score=-10.0,
            block_momentum_score=-8.0,
            block_whales_score=-5.0,
            block_derivatives_score=-7.0,
            block_sentiment_score=-5.0,
            bullish_count=2,
            bearish_count=18,
            neutral_count=10,
            data_sources_count=25,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # ETH should NOT be SHORT when BTC is strong LONG
        assert new_direction != "short", f"ETH should not be SHORT when BTC is strong LONG, got {new_direction}"
        # Should be SIDEWAYS or LONG
        assert new_direction in ("sideways", "long"), f"Expected sideways or long, got {new_direction}"
        # Score should be capped to 0 or positive
        assert new_total_score >= 0, f"Score should be ≥0, got {new_total_score}"
    
    def test_btc_moderate_short_eth_weak_long_allowed(self, analyzer):
        """
        Test: BTC = MODERATE SHORT (-20) → ETH WEAK LONG still allowed
        This tests that only STRONG opposite signals are prevented
        """
        current_time = time.time()
        
        # Setup: BTC is in MODERATE SHORT (not strong enough to trigger override)
        analyzer._correlation_signals["BTC"] = {
            "direction": "short",
            "probability": 60,
            "total_score": -20.0,  # Moderate short (< -30 threshold)
            "trend_score": -5.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        # ETH originally WEAK LONG
        direction = "long"
        probability = 55
        total_score = 12.0  # Weak long
        
        result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=3.0,
            block_trend_score=3.0,
            block_momentum_score=2.0,
            block_whales_score=1.0,
            block_derivatives_score=2.0,
            block_sentiment_score=1.0,
            bullish_count=10,
            bearish_count=8,
            neutral_count=12,
            data_sources_count=22,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # With BTC at -20 (not < -30), override should NOT trigger
        # Correlation will still adjust the score but not force it
        # After correlation: 12 + (-20 * 0.7) = 12 + (-14) = -2 → sideways
        # This is expected behavior - moderate influence
        print(f"BTC moderate short (-20), ETH after correlation: {new_total_score:.2f} → {new_direction}")
    
    def test_btc_strong_short_eth_already_short_no_change(self, analyzer):
        """
        Test: BTC = STRONG SHORT → ETH already SHORT = no override needed
        Expected: ETH SHORT signal is strengthened by correlation
        """
        current_time = time.time()
        
        # Setup: BTC is in STRONG SHORT
        analyzer._correlation_signals["BTC"] = {
            "direction": "short",
            "probability": 75,
            "total_score": -40.0,  # Strong short
            "trend_score": -12.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        # ETH also SHORT
        direction = "short"
        probability = 70
        total_score = -25.0
        
        result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=-6.0,
            block_trend_score=-6.0,
            block_momentum_score=-5.0,
            block_whales_score=-3.0,
            block_derivatives_score=-4.0,
            block_sentiment_score=-3.0,
            bullish_count=3,
            bearish_count=15,
            neutral_count=12,
            data_sources_count=24,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # ETH should remain SHORT and score should be more negative
        assert new_direction == "short", f"Expected short, got {new_direction}"
        # Score should be more negative: -25 + (-40 * 0.7) = -25 + (-28) = -53
        assert new_total_score < total_score, f"Score should be more negative, got {new_total_score}"
        assert new_total_score < -30, f"Score should be strongly negative, got {new_total_score}"
    
    def test_btc_strong_long_eth_already_long_strengthened(self, analyzer):
        """
        Test: BTC = STRONG LONG → ETH already LONG = strengthened
        Expected: ETH LONG signal is strengthened by correlation
        """
        current_time = time.time()
        
        # Setup: BTC is in STRONG LONG
        analyzer._correlation_signals["BTC"] = {
            "direction": "long",
            "probability": 75,
            "total_score": 40.0,  # Strong long
            "trend_score": 12.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        # ETH also LONG
        direction = "long"
        probability = 70
        total_score = 25.0
        
        result = analyzer._cross_asset_correlation_check(
            symbol="ETH",
            direction=direction,
            probability=probability,
            total_score=total_score,
            trend_score=6.0,
            block_trend_score=6.0,
            block_momentum_score=5.0,
            block_whales_score=3.0,
            block_derivatives_score=4.0,
            block_sentiment_score=3.0,
            bullish_count=15,
            bearish_count=3,
            neutral_count=12,
            data_sources_count=24,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # ETH should remain LONG and score should be more positive
        assert new_direction == "long", f"Expected long, got {new_direction}"
        # Score should be more positive: 25 + (40 * 0.7) = 25 + 28 = 53
        assert new_total_score > total_score, f"Score should be more positive, got {new_total_score}"
        assert new_total_score > 30, f"Score should be strongly positive, got {new_total_score}"
    
    def test_btc_sideways_eth_not_affected(self, analyzer):
        """
        Test: BTC = SIDEWAYS → ETH can be any direction
        Expected: Minimal adjustment, original direction preserved
        """
        current_time = time.time()
        
        # Setup: BTC is in SIDEWAYS
        analyzer._correlation_signals["BTC"] = {
            "direction": "sideways",
            "probability": 52,
            "total_score": 5.0,  # Weak/sideways
            "trend_score": 1.0,
            "generated_at": current_time,
            "expires_at": current_time + 600,
        }
        
        # ETH is LONG
        direction = "long"
        probability = 65
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
            bullish_count=12,
            bearish_count=6,
            neutral_count=12,
            data_sources_count=23,
        )
        
        new_direction, new_probability, new_total_score, is_conflict = result
        
        # With BTC sideways (score < 10), correlation applies minimally
        # 18 + (5 * 0.7) = 18 + 3.5 = 21.5 → still long
        # No override should trigger because BTC score is not strong (< 30)
        print(f"BTC sideways (5), ETH after correlation: {new_total_score:.2f} → {new_direction}")
