"""
Tests for honest signals fix - direction and probability based strictly on score.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer
from unittest.mock import Mock, AsyncMock


class TestHonestSignals:
    """Tests for honest signal direction and probability calculation."""
    
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
    
    def test_determine_direction_from_score_sideways(self, analyzer):
        """Test direction determination for sideways (score between -10 and 10)."""
        # Test various sideways scores
        assert analyzer._determine_direction_from_score(-9.99) == "sideways"
        assert analyzer._determine_direction_from_score(-5) == "sideways"
        assert analyzer._determine_direction_from_score(-0.11) == "sideways"
        assert analyzer._determine_direction_from_score(0) == "sideways"
        assert analyzer._determine_direction_from_score(5) == "sideways"
        assert analyzer._determine_direction_from_score(6.41) == "sideways"
        assert analyzer._determine_direction_from_score(9.99) == "sideways"
    
    def test_determine_direction_from_score_long(self, analyzer):
        """Test direction determination for long (score >= 10)."""
        assert analyzer._determine_direction_from_score(10) == "long"
        assert analyzer._determine_direction_from_score(10.01) == "long"
        assert analyzer._determine_direction_from_score(13.05) == "long"
        assert analyzer._determine_direction_from_score(25) == "long"
        assert analyzer._determine_direction_from_score(50) == "long"
        assert analyzer._determine_direction_from_score(100) == "long"
    
    def test_determine_direction_from_score_short(self, analyzer):
        """Test direction determination for short (score <= -10)."""
        assert analyzer._determine_direction_from_score(-10) == "short"
        assert analyzer._determine_direction_from_score(-10.01) == "short"
        assert analyzer._determine_direction_from_score(-15) == "short"
        assert analyzer._determine_direction_from_score(-25) == "short"
        assert analyzer._determine_direction_from_score(-50) == "short"
        assert analyzer._determine_direction_from_score(-100) == "short"
    
    def test_calculate_real_probability_sideways_very_confident(self, analyzer):
        """Test probability for very confident sideways (score < 2)."""
        # Very close to 0 = high confidence sideways
        prob = analyzer._calculate_real_probability(
            total_score=-0.11,
            direction="sideways",
            bullish_count=5,
            bearish_count=5,
            neutral_count=12
        )
        assert 68 <= prob <= 71  # Base 68 + neutral bonus
        
        prob = analyzer._calculate_real_probability(
            total_score=0.5,
            direction="sideways",
            bullish_count=3,
            bearish_count=4,
            neutral_count=15
        )
        assert 68 <= prob <= 71  # Base 68 + neutral bonus
    
    def test_calculate_real_probability_sideways_medium(self, analyzer):
        """Test probability for medium sideways (score 4-8)."""
        prob = analyzer._calculate_real_probability(
            total_score=6.41,
            direction="sideways",
            bullish_count=6,
            bearish_count=5,
            neutral_count=11
        )
        assert 54 <= prob <= 61  # Base 54-58 with possible bonuses
    
    def test_calculate_real_probability_long_weak(self, analyzer):
        """Test probability for weak long signal (score just over 10)."""
        prob = analyzer._calculate_real_probability(
            total_score=11,
            direction="long",
            bullish_count=8,
            bearish_count=4,
            neutral_count=10
        )
        assert 52 <= prob <= 60  # Base 52 + consensus bonus
    
    def test_calculate_real_probability_long_medium(self, analyzer):
        """Test probability for medium long signal (score ~15)."""
        prob = analyzer._calculate_real_probability(
            total_score=13.05,
            direction="long",
            bullish_count=10,
            bearish_count=5,
            neutral_count=7
        )
        assert 56 <= prob <= 65  # Base 56 + consensus bonus
    
    def test_calculate_real_probability_long_strong(self, analyzer):
        """Test probability for strong long signal (score > 25)."""
        prob = analyzer._calculate_real_probability(
            total_score=30,
            direction="long",
            bullish_count=15,
            bearish_count=3,
            neutral_count=4
        )
        assert 70 <= prob <= 80  # Base 70-75 + consensus bonus
    
    def test_calculate_real_probability_short_with_conflict(self, analyzer):
        """Test probability for short signal with bullish data (conflict)."""
        prob = analyzer._calculate_real_probability(
            total_score=-15,
            direction="short",
            bullish_count=10,
            bearish_count=5,
            neutral_count=7
        )
        assert 50 <= prob <= 56  # Base 56 minus conflict penalty
    
    def test_calculate_real_probability_long_with_consensus(self, analyzer):
        """Test probability for long signal with strong bullish consensus."""
        prob = analyzer._calculate_real_probability(
            total_score=20,
            direction="long",
            bullish_count=18,
            bearish_count=2,
            neutral_count=2
        )
        assert 65 <= prob <= 75  # Base 65 + good consensus bonus
    
    def test_probability_range(self, analyzer):
        """Test that probability is always within 50-85% range."""
        test_cases = [
            (-0.11, "sideways", 5, 5, 12),
            (6.41, "sideways", 6, 5, 11),
            (13.05, "long", 10, 5, 7),
            (-15, "short", 5, 10, 7),
            (50, "long", 18, 2, 2),
            (-50, "short", 2, 18, 2),
        ]
        
        for score, direction, bull, bear, neutral in test_cases:
            prob = analyzer._calculate_real_probability(
                total_score=score,
                direction=direction,
                bullish_count=bull,
                bearish_count=bear,
                neutral_count=neutral
            )
            assert 50 <= prob <= 85, f"Probability {prob} out of range for score={score}"
    
    def test_examples_from_problem_statement(self, analyzer):
        """Test the exact examples from problem statement."""
        # BTC: score=-0.11 should be sideways with ~68% probability
        direction = analyzer._determine_direction_from_score(-0.11)
        assert direction == "sideways"
        
        prob = analyzer._calculate_real_probability(
            total_score=-0.11,
            direction=direction,
            bullish_count=5,
            bearish_count=5,
            neutral_count=12
        )
        assert 65 <= prob <= 71  # Around 68%
        
        # ETH: score=+13.05 should be long with ~56% probability
        direction = analyzer._determine_direction_from_score(13.05)
        assert direction == "long"
        
        prob = analyzer._calculate_real_probability(
            total_score=13.05,
            direction=direction,
            bullish_count=10,
            bearish_count=5,
            neutral_count=7
        )
        assert 52 <= prob <= 65  # Around 56%
        
        # TON: score=+6.41 should be sideways with ~58% probability
        direction = analyzer._determine_direction_from_score(6.41)
        assert direction == "sideways"
        
        prob = analyzer._calculate_real_probability(
            total_score=6.41,
            direction=direction,
            bullish_count=6,
            bearish_count=5,
            neutral_count=11
        )
        assert 54 <= prob <= 63  # Around 58%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
