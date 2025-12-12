"""
Tests for probability calculation and consensus counting.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer
from unittest.mock import Mock


class TestProbabilityCalculation:
    """Tests for probability calculation."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance."""
        mock_tracker = Mock()
        return AISignalAnalyzer(mock_tracker)
    
    def test_calculate_probability_bullish(self, analyzer):
        """Test probability calculation for bullish scenario."""
        result = analyzer.calculate_probability(
            total_score=50,  # Positive score
            data_sources_count=9,  # 9 out of 10 sources
            consensus_count=7,  # 7 factors agree
            total_factors=10
        )
        
        assert result["direction"] == "up"
        assert result["probability"] >= 50
        assert result["probability"] <= 95
        assert result["confidence"] in ["high", "medium", "low"]
        assert 0 <= result["data_quality"] <= 1
    
    def test_calculate_probability_bearish(self, analyzer):
        """Test probability calculation for bearish scenario."""
        result = analyzer.calculate_probability(
            total_score=-50,  # Negative score
            data_sources_count=8,  # 8 out of 10 sources
            consensus_count=6,  # 6 factors agree
            total_factors=10
        )
        
        assert result["direction"] == "down"
        assert result["probability"] >= 50
        assert result["probability"] <= 95
        assert result["confidence"] in ["high", "medium", "low"]
        assert 0 <= result["data_quality"] <= 1
    
    def test_calculate_probability_neutral(self, analyzer):
        """Test probability calculation for neutral scenario."""
        result = analyzer.calculate_probability(
            total_score=5,  # Small positive score
            data_sources_count=5,  # 5 out of 10 sources
            consensus_count=3,  # 3 factors agree
            total_factors=10
        )
        
        assert result["probability"] >= 20
        assert result["probability"] <= 95
        # Probability should be close to 50% for neutral
        assert 40 <= result["probability"] <= 60
    
    def test_calculate_probability_high_confidence(self, analyzer):
        """Test that high scores produce high confidence."""
        result = analyzer.calculate_probability(
            total_score=80,  # Very high score
            data_sources_count=10,  # All sources
            consensus_count=9,  # Almost all factors agree
            total_factors=10
        )
        
        assert result["confidence"] == "high"
        assert result["probability"] >= 75
    
    def test_calculate_probability_low_confidence(self, analyzer):
        """Test that low scores produce low confidence."""
        result = analyzer.calculate_probability(
            total_score=10,  # Low score
            data_sources_count=3,  # Few sources
            consensus_count=2,  # Few factors agree
            total_factors=10
        )
        
        assert result["confidence"] == "low"
        assert 40 <= result["probability"] <= 60


class TestConsensusCount:
    """Tests for consensus counting."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance."""
        mock_tracker = Mock()
        return AISignalAnalyzer(mock_tracker)
    
    def test_count_consensus_bullish(self, analyzer):
        """Test consensus counting for bullish scenario."""
        scores = {
            "whale_score": 5.0,
            "trend_score": 4.0,
            "momentum_score": 3.0,
            "volatility_score": 2.0,
            "volume_score": 3.0,
            "market_score": 6.0,
            "orderbook_score": -1.0,  # Slightly bearish
            "derivatives_score": 3.0,
            "onchain_score": 2.0,
            "sentiment_score": 4.0
        }
        
        result = analyzer.count_consensus(scores)
        
        assert result["consensus"] == "bullish"
        assert result["bullish_count"] > result["bearish_count"]
        assert result["bullish_count"] + result["bearish_count"] + result["neutral_count"] == 10
    
    def test_count_consensus_bearish(self, analyzer):
        """Test consensus counting for bearish scenario."""
        scores = {
            "whale_score": -5.0,
            "trend_score": -4.0,
            "momentum_score": -3.0,
            "volatility_score": -2.0,
            "volume_score": -3.0,
            "market_score": -6.0,
            "orderbook_score": 1.0,  # Slightly bullish
            "derivatives_score": -3.0,
            "onchain_score": -2.0,
            "sentiment_score": -4.0
        }
        
        result = analyzer.count_consensus(scores)
        
        assert result["consensus"] == "bearish"
        assert result["bearish_count"] > result["bullish_count"]
        assert result["bullish_count"] + result["bearish_count"] + result["neutral_count"] == 10
    
    def test_count_consensus_neutral(self, analyzer):
        """Test consensus counting for neutral scenario."""
        scores = {
            "whale_score": 0.5,
            "trend_score": -0.5,
            "momentum_score": 0.3,
            "volatility_score": -0.2,
            "volume_score": 0.1,
            "market_score": -0.1,
            "orderbook_score": 0.0,
            "derivatives_score": 0.4,
            "onchain_score": -0.3,
            "sentiment_score": 0.2
        }
        
        result = analyzer.count_consensus(scores)
        
        # Most scores should be neutral (between -1 and 1)
        assert result["neutral_count"] > 0
        assert result["bullish_count"] + result["bearish_count"] + result["neutral_count"] == 10
    
    def test_count_consensus_threshold(self, analyzer):
        """Test that consensus uses correct threshold (±1)."""
        scores = {
            "score1_score": 1.5,  # Bullish (> 1)
            "score2_score": -1.5,  # Bearish (< -1)
            "score3_score": 0.9,  # Neutral (between -1 and 1)
            "score4_score": -0.9,  # Neutral
            "score5_score": 1.0,  # Neutral (exactly 1)
            "score6_score": -1.0,  # Neutral (exactly -1)
        }
        
        result = analyzer.count_consensus(scores)
        
        assert result["bullish_count"] == 1
        assert result["bearish_count"] == 1
        assert result["neutral_count"] == 4


class TestIntegration:
    """Integration tests for probability with signal calculation."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance."""
        mock_tracker = Mock()
        return AISignalAnalyzer(mock_tracker)
    
    def test_calculate_signal_includes_probability(self, analyzer):
        """Test that calculate_signal includes probability data."""
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
        
        result = analyzer.calculate_signal("BTC", whale_data, market_data)
        
        # Check that probability fields are included
        assert "probability" in result
        assert "probability_direction" in result
        assert "probability_confidence" in result
        assert "data_quality" in result
        assert "bullish_count" in result
        assert "bearish_count" in result
        assert "neutral_count" in result
        assert "consensus" in result
        assert "data_sources_count" in result
        
        # Validate probability values
        assert 20 <= result["probability"] <= 95
        assert result["probability_direction"] in ["up", "down", "sideways"]
        assert result["probability_confidence"] in ["high", "medium", "low"]
        assert 0 <= result["data_quality"] <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
