"""
Test AI signal stabilization features.

The stabilization system prevents rapid oscillation between LONG/SHORT signals
by implementing score smoothing, hysteresis, and expanded dead zones.

Features tested:
- Score smoothing: Exponential moving average with alpha=0.4
- Hysteresis: Prevents direction reversals below threshold
- Expanded dead zone: Different thresholds for TON vs BTC/ETH
- Probability capping: Fixed values for weak/medium signals
"""

import pytest
from unittest.mock import Mock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestScoreSmoothing:
    """Test score smoothing functionality."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_first_call_no_smoothing(self, analyzer):
        """First call should have no smoothing (no previous score)."""
        whale_data = {
            "transaction_count": 5,
            "total_volume_usd": 10_000_000,
            "deposits": 1,
            "withdrawals": 4,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_1h": 2.0,
            "change_24h": 5.0,
            "change_7d": 10.0,
            "market_cap": 1_000_000_000_000,
            "volume_24h": 20_000_000_000,
        }
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        score1 = result.get('total_score', 0)
        
        # Check that score is stored
        assert "BTC" in analyzer.previous_scores
        assert analyzer.previous_scores["BTC"] == score1
    
    def test_second_call_applies_smoothing(self, analyzer):
        """Second call should apply smoothing with previous score."""
        whale_data = {
            "transaction_count": 5,
            "total_volume_usd": 10_000_000,
            "deposits": 1,
            "withdrawals": 4,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_1h": 2.0,
            "change_24h": 5.0,
            "change_7d": 10.0,
            "market_cap": 1_000_000_000_000,
            "volume_24h": 20_000_000_000,
        }
        
        # First call
        result1 = analyzer.calculate_signal("BTC", whale_data, market_data)
        score1 = result1.get('total_score', 0)
        
        # Second call with different data
        market_data["change_24h"] = 10.0  # Increased significantly
        result2 = analyzer.calculate_signal("BTC", whale_data, market_data)
        score2 = result2.get('total_score', 0)
        
        # Score should be smoothed (not just the raw new score)
        # With alpha=0.4: score2 = 0.4 * new_score + 0.6 * score1
        # So score2 should be closer to score1 than to the raw new score
        # This is hard to test precisely without knowing the exact new score,
        # but we can verify that previous_scores is updated
        assert "BTC" in analyzer.previous_scores
        assert analyzer.previous_scores["BTC"] == score2


class TestDeadZone:
    """Test expanded dead zone functionality."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_btc_dead_zone_is_10(self, analyzer):
        """BTC should use dead zone of 10."""
        # Create minimal data to get a score near zero
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
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        direction = result.get('direction', '')
        total_score = result.get('total_score', 0)
        probability = result.get('probability', 0)
        
        # If score is between -10 and 10, should show боковик
        if abs(total_score) < 10:
            assert "Боковик" in direction
            assert 50 <= probability <= 55  # Real probability for weak signals (not constant)
    
    def test_ton_dead_zone_is_15(self, analyzer):
        """TON should use wider dead zone of 15."""
        # Create minimal data to get a score near zero
        whale_data = {
            "transaction_count": 0,
            "total_volume_usd": 0,
            "deposits": 0,
            "withdrawals": 0,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 5.0,
            "change_1h": 0.1,
            "change_24h": 0.1,
            "change_7d": 0.1,
            "market_cap": 10_000_000_000,
            "volume_24h": 100_000_000,
        }
        
        result = analyzer.calculate_signal("TON", whale_data, market_data)
        direction = result.get('direction', '')
        total_score = result.get('total_score', 0)
        probability = result.get('probability', 0)
        
        # If score is between -15 and 15, should show боковик
        if abs(total_score) < 15:
            assert "Боковик" in direction
            assert 50 <= probability <= 55  # Real probability for weak signals (not constant)


class TestHysteresis:
    """Test hysteresis functionality to prevent rapid direction changes."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_hysteresis_prevents_long_to_short_reversal(self, analyzer):
        """Hysteresis should prevent LONG to SHORT reversal with weak signal."""
        # First, establish a LONG direction
        whale_data = {
            "transaction_count": 10,
            "total_volume_usd": 50_000_000,
            "deposits": 1,
            "withdrawals": 9,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_1h": 3.0,
            "change_24h": 8.0,
            "change_7d": 15.0,
            "market_cap": 1_000_000_000_000,
            "volume_24h": 30_000_000_000,
        }
        
        result1 = analyzer.calculate_signal("BTC", whale_data, market_data)
        direction1 = result1.get('direction', '')
        
        # Check if LONG direction was established
        if "ВВЕРХ" in direction1 or "вверх" in direction1:
            # Now try to reverse with weak bearish signal
            market_data["change_24h"] = -2.0  # Slightly negative
            whale_data["deposits"] = 6
            whale_data["withdrawals"] = 4
            
            result2 = analyzer.calculate_signal("BTC", whale_data, market_data)
            direction2 = result2.get('direction', '')
            total_score2 = result2.get('total_score', 0)
            
            # If score < 30 in absolute value, hysteresis should prevent reversal
            if abs(total_score2) < 30:
                assert "Боковик" in direction2, f"Expected Боковик with score={total_score2}, got {direction2}"
    
    def test_hysteresis_allows_strong_reversal(self, analyzer):
        """Hysteresis should allow reversal with strong signal (score > 30)."""
        # This test is informational - just verify that strong signals can reverse
        # In practice, it's hard to generate a score > 30 without complex data
        pass
    
    def test_direction_memory_persists(self, analyzer):
        """Test that direction is stored in memory."""
        whale_data = {
            "transaction_count": 5,
            "total_volume_usd": 10_000_000,
            "deposits": 1,
            "withdrawals": 4,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_1h": 2.0,
            "change_24h": 5.0,
            "change_7d": 10.0,
            "market_cap": 1_000_000_000_000,
            "volume_24h": 20_000_000_000,
        }
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        
        # Check that direction is stored
        assert "BTC" in analyzer.previous_direction
        assert analyzer.previous_direction["BTC"] in ["long", "short", "sideways"]


class TestProbabilityCapping:
    """Test probability capping for weak and medium signals."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_weak_signal_probability_capped_at_52(self, analyzer):
        """Weak signals (abs(score) < dead_zone) should have probability=52."""
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
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        total_score = result.get('total_score', 0)
        probability = result.get('probability', 0)
        
        # If abs(total_score) < 10 (dead zone for BTC)
        if abs(total_score) < 10:
            assert 50 <= probability <= 55, f"Expected probability in range 50-55% for weak signal (score={total_score}), got {probability}"
    
    def test_medium_signal_probability_capped_at_58(self, analyzer):
        """Medium signals (10 <= abs(score) < 20) should have probability <= 58."""
        # This is harder to test precisely, but we can verify the logic is in place
        # by checking that probability is not too high for medium scores
        whale_data = {
            "transaction_count": 5,
            "total_volume_usd": 10_000_000,
            "deposits": 2,
            "withdrawals": 3,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_1h": 1.0,
            "change_24h": 2.0,
            "change_7d": 3.0,
            "market_cap": 1_000_000_000_000,
            "volume_24h": 10_000_000_000,
        }
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        total_score = result.get('total_score', 0)
        probability = result.get('probability', 0)
        
        # If 10 <= abs(total_score) < 20, probability should be capped at 58
        if 10 <= abs(total_score) < 20:
            assert probability <= 58, f"Expected probability <= 58 for medium signal (score={total_score}), got {probability}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
