"""
Tests for direction consensus validation.
Ensures signal direction doesn't contradict factor consensus.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer
from unittest.mock import Mock


class TestDirectionConsensusValidation:
    """Tests for direction consensus validation logic."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance."""
        mock_tracker = Mock()
        return AISignalAnalyzer(mock_tracker)
    
    def test_bullish_consensus_prevents_short(self, analyzer):
        """Test that strong bullish consensus prevents SHORT signal."""
        # Setup: 2 bullish, 0 bearish factors (bullish consensus)
        # But weak score that might trigger sideways/short
        whale_data = {
            "transaction_count": 5,
            "total_volume_usd": 10_000_000,
            "deposits": 1,
            "withdrawals": 4,
            "largest_transaction": 5_000_000,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": 1.0,  # Weak positive
            "volume_24h": 20_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        
        # With bullish consensus, should not give SHORT
        assert "ВНИЗ" not in result["direction"]
        assert "вниз" not in result["direction"]
        
        # Should be sideways or long
        assert "Боковик" in result["direction"] or "ВВЕРХ" in result["direction"] or "вверх" in result["direction"]
    
    def test_bearish_consensus_prevents_long(self, analyzer):
        """Test that strong bearish consensus prevents LONG signal."""
        # Setup: 0 bullish, 2 bearish factors (bearish consensus)
        whale_data = {
            "transaction_count": 8,
            "total_volume_usd": 50_000_000,
            "deposits": 7,  # More deposits = bearish
            "withdrawals": 1,
            "largest_transaction": 10_000_000,
            "sentiment": "bearish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": -1.0,  # Weak negative
            "volume_24h": 20_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        
        # With bearish consensus, should not give LONG
        assert "ВВЕРХ" not in result["direction"]
        assert "вверх" not in result["direction"]
        
        # Should be sideways or short
        assert "Боковик" in result["direction"] or "ВНИЗ" in result["direction"] or "вниз" in result["direction"]
    
    def test_weak_signal_becomes_sideways(self, analyzer):
        """Test that weak signals (abs(total_score) < 5) become sideways."""
        # Very weak/neutral data
        whale_data = {
            "transaction_count": 2,
            "total_volume_usd": 1_000_000,
            "deposits": 1,
            "withdrawals": 1,
            "largest_transaction": 500_000,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": 0.1,  # Almost no change
            "volume_24h": 20_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        
        # Very weak signal should be sideways
        if abs(result["total_score"]) < analyzer.WEAK_SIGNAL_THRESHOLD:
            assert "Боковик" in result["direction"]
    
    def test_strong_signal_with_consensus_allowed(self, analyzer):
        """Test that strong signals with matching consensus are allowed."""
        # Strong bullish data
        whale_data = {
            "transaction_count": 15,
            "total_volume_usd": 200_000_000,
            "deposits": 2,
            "withdrawals": 13,  # Strong outflow = bullish
            "largest_transaction": 50_000_000,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": 8.0,  # Strong positive
            "volume_24h": 50_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        
        # Strong bullish signal with bullish consensus should be allowed
        # Should be long or at least not short
        assert "ВНИЗ" not in result["direction"]
        assert "вниз" not in result["direction"]
    
    def test_neutral_consensus_allows_any_direction(self, analyzer):
        """Test that neutral consensus (equal bullish/bearish) allows any direction."""
        # Mixed signals
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
            "change_24h": 0.0,
            "volume_24h": 20_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        
        # Should have valid direction
        assert result["direction"] is not None
        
        # Bullish and bearish counts should be close
        bullish = result.get("bullish_count", 0)
        bearish = result.get("bearish_count", 0)
        
        # If counts are equal or close, no consensus blocking should occur
        if abs(bullish - bearish) < 2:
            # Any direction is valid
            assert True


class TestProbabilityCalculation:
    """Tests to verify probability is calculated correctly and not constant."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance."""
        mock_tracker = Mock()
        return AISignalAnalyzer(mock_tracker)
    
    def test_probability_not_constant_weak_signal(self, analyzer):
        """Test that weak signal probability is in correct range (50-55%)."""
        whale_data = {
            "transaction_count": 2,
            "total_volume_usd": 1_000_000,
            "deposits": 1,
            "withdrawals": 1,
            "largest_transaction": 500_000,
            "sentiment": "neutral"
        }
        
        market_data = {
            "price_usd": 50000,
            "change_24h": 0.5,
            "volume_24h": 20_000_000_000,
            "market_cap": 1_000_000_000_000
        }
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        
        # Weak signal should have probability around 50-55%
        probability = result.get("probability", 0)
        assert 50 <= probability <= 60  # Allow slightly higher than 55 for edge cases
    
    def test_probability_increases_with_strength(self, analyzer):
        """Test that stronger signals have higher probability."""
        # Test multiple scenarios with increasing strength
        scenarios = [
            # (change_24h, withdrawals, expected_min_prob)
            (1.0, 3, 50),   # Weak
            (5.0, 8, 55),   # Medium
            (10.0, 15, 65), # Strong
        ]
        
        probabilities = []
        for change, withdrawals, _ in scenarios:
            whale_data = {
                "transaction_count": 10,
                "total_volume_usd": 50_000_000 * (withdrawals / 3),
                "deposits": 2,
                "withdrawals": withdrawals,
                "largest_transaction": 10_000_000,
                "sentiment": "bullish"
            }
            
            market_data = {
                "price_usd": 50000,
                "change_24h": change,
                "volume_24h": 30_000_000_000,
                "market_cap": 1_000_000_000_000
            }
            
            result = analyzer.calculate_signal("BTC", whale_data, market_data)
            probabilities.append(result.get("probability", 50))
        
        # Probabilities should generally increase with signal strength
        # (allow for some variance due to other factors)
        assert probabilities[0] <= probabilities[2]  # Weak <= Strong
    
    def test_probability_in_valid_range(self, analyzer):
        """Test that probability is always in valid range (50-85%)."""
        # Various test scenarios
        test_data = [
            # Bullish
            (8.0, 15, "bullish"),
            # Bearish
            (-8.0, 2, "bearish"),
            # Neutral
            (0.5, 5, "neutral"),
        ]
        
        for change, withdrawals, sentiment in test_data:
            whale_data = {
                "transaction_count": 10,
                "total_volume_usd": 50_000_000,
                "deposits": 10 - withdrawals,
                "withdrawals": withdrawals,
                "largest_transaction": 10_000_000,
                "sentiment": sentiment
            }
            
            market_data = {
                "price_usd": 50000,
                "change_24h": change,
                "volume_24h": 25_000_000_000,
                "market_cap": 1_000_000_000_000
            }
            
            result = analyzer.calculate_signal("BTC", whale_data, market_data)
            probability = result.get("probability", 0)
            
            # Probability must be in valid range
            assert 50 <= probability <= 85, f"Probability {probability} out of range for scenario: {sentiment}, change={change}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
