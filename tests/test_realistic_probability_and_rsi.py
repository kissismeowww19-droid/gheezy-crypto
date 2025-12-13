"""
Tests for realistic probability calculation and RSI logic fix.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import Mock
from signals.ai_signals import AISignalAnalyzer


class TestRealisticProbabilityAndRSI:
    """Tests for realistic probability and RSI logic."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance."""
        mock_whale_tracker = Mock()
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_constants_defined(self, analyzer):
        """Test that new constants are defined."""
        assert hasattr(analyzer, 'MAX_TOTAL_SCORE')
        assert hasattr(analyzer, 'MAX_PROBABILITY')
        assert hasattr(analyzer, 'MAX_SINGLE_FACTOR_SCORE')
        
        assert analyzer.MAX_TOTAL_SCORE == 100
        assert analyzer.MAX_PROBABILITY == 78
        assert analyzer.MAX_SINGLE_FACTOR_SCORE == 15
    
    def test_apply_total_score_limit(self, analyzer):
        """Test that total score is limited to ±100."""
        # Test positive overflow
        assert analyzer.apply_total_score_limit(150) == 100
        assert analyzer.apply_total_score_limit(100) == 100
        assert analyzer.apply_total_score_limit(50) == 50
        
        # Test negative overflow
        assert analyzer.apply_total_score_limit(-150) == -100
        assert analyzer.apply_total_score_limit(-100) == -100
        assert analyzer.apply_total_score_limit(-50) == -50
        
        # Test within range
        assert analyzer.apply_total_score_limit(0) == 0
    
    def test_calculate_realistic_probability_basic(self, analyzer):
        """Test realistic probability calculation with basic inputs."""
        # Test low score (should give ~50-55%)
        prob_low = analyzer.calculate_realistic_probability(score=10, factors_count=20, max_factors=22)
        assert 50 <= prob_low <= 55
        
        # Test medium score (should give ~55-65%)
        prob_mid = analyzer.calculate_realistic_probability(score=40, factors_count=20, max_factors=22)
        assert 55 <= prob_mid <= 65
        
        # Test high score (should give ~65-73%)
        prob_high = analyzer.calculate_realistic_probability(score=80, factors_count=20, max_factors=22)
        assert 65 <= prob_high <= 73
        
        # Test very high score (should be capped at MAX_PROBABILITY = 78%)
        prob_very_high = analyzer.calculate_realistic_probability(score=150, factors_count=20, max_factors=22)
        assert prob_very_high <= 78
    
    def test_calculate_realistic_probability_max_cap(self, analyzer):
        """Test that probability never exceeds MAX_PROBABILITY."""
        # Test with extreme scores
        for score in [100, 150, 200, 500]:
            prob = analyzer.calculate_realistic_probability(score=score, factors_count=30, max_factors=30)
            assert prob <= analyzer.MAX_PROBABILITY, f"Score {score} gave probability {prob} > {analyzer.MAX_PROBABILITY}"
    
    def test_calculate_realistic_probability_data_completeness(self, analyzer):
        """Test that data completeness affects probability."""
        score = 50
        
        # Full data (should give higher probability)
        prob_full = analyzer.calculate_realistic_probability(score=score, factors_count=30, max_factors=30)
        
        # Half data (should give lower probability)
        prob_half = analyzer.calculate_realistic_probability(score=score, factors_count=15, max_factors=30)
        
        # Less data should result in lower probability
        assert prob_half < prob_full
    
    def test_rsi_logic_oversold(self, analyzer):
        """Test that RSI < 30 (oversold) gives LONG signal."""
        # RSI = 6 (extremely oversold) should contribute to LONG
        score = analyzer._calc_momentum_score(rsi=6, rsi_5m=None, rsi_15m=None, price_momentum_10min=None)
        # When RSI < 20, score should be positive (LONG direction)
        assert score > 0, f"RSI=6 (oversold) should give positive score for LONG, got {score}"
        
        # RSI = 25 (oversold) should also contribute to LONG
        score = analyzer._calc_momentum_score(rsi=25, rsi_5m=None, rsi_15m=None, price_momentum_10min=None)
        assert score > 0, f"RSI=25 (oversold) should give positive score for LONG, got {score}"
    
    def test_rsi_logic_overbought(self, analyzer):
        """Test that RSI > 70 (overbought) gives SHORT signal."""
        # RSI = 85 (extremely overbought) should contribute to SHORT
        score = analyzer._calc_momentum_score(rsi=85, rsi_5m=None, rsi_15m=None, price_momentum_10min=None)
        # When RSI > 80, score should be negative (SHORT direction)
        assert score < 0, f"RSI=85 (overbought) should give negative score for SHORT, got {score}"
        
        # RSI = 75 (overbought) should also contribute to SHORT
        score = analyzer._calc_momentum_score(rsi=75, rsi_5m=None, rsi_15m=None, price_momentum_10min=None)
        assert score < 0, f"RSI=75 (overbought) should give negative score for SHORT, got {score}"
    
    def test_rsi_extreme_levels(self, analyzer):
        """Test that extreme RSI levels give stronger signals."""
        # RSI < 20 should give stronger signal than RSI < 30
        score_extreme = analyzer._calc_momentum_score(rsi=10, rsi_5m=None, rsi_15m=None, price_momentum_10min=None)
        score_normal = analyzer._calc_momentum_score(rsi=25, rsi_5m=None, rsi_15m=None, price_momentum_10min=None)
        
        # Both should be positive (LONG), but extreme should be stronger
        assert score_extreme > 0
        assert score_normal > 0
        assert score_extreme > score_normal, "RSI=10 should give stronger LONG signal than RSI=25"
        
        # Similarly for overbought
        score_extreme = analyzer._calc_momentum_score(rsi=90, rsi_5m=None, rsi_15m=None, price_momentum_10min=None)
        score_normal = analyzer._calc_momentum_score(rsi=75, rsi_5m=None, rsi_15m=None, price_momentum_10min=None)
        
        # Both should be negative (SHORT), but extreme should be stronger
        assert score_extreme < 0
        assert score_normal < 0
        assert score_extreme < score_normal, "RSI=90 should give stronger SHORT signal than RSI=75"
    
    def test_rsi_5m_15m_consistency(self, analyzer):
        """Test that RSI logic is consistent across timeframes."""
        # All timeframes with oversold should give LONG
        score = analyzer._calc_momentum_score(rsi=20, rsi_5m=15, rsi_15m=18, price_momentum_10min=None)
        assert score > 0, "All oversold RSI should give LONG signal"
        
        # All timeframes with overbought should give SHORT
        score = analyzer._calc_momentum_score(rsi=80, rsi_5m=85, rsi_15m=82, price_momentum_10min=None)
        assert score < 0, "All overbought RSI should give SHORT signal"
    
    def test_short_term_rsi_logic(self, analyzer):
        """Test RSI logic in short-term trend calculation."""
        # Test with oversold RSI in short-term data
        short_term_data = {
            "rsi_5m": 15,
            "rsi_15m": 20,
        }
        score = analyzer._calculate_short_term_trend_score(short_term_data)
        assert score > 0, "Oversold short-term RSI should give positive score"
        
        # Test with overbought RSI in short-term data
        short_term_data = {
            "rsi_5m": 85,
            "rsi_15m": 80,
        }
        score = analyzer._calculate_short_term_trend_score(short_term_data)
        assert score < 0, "Overbought short-term RSI should give negative score"
    
    def test_calculate_real_probability_uses_realistic_formula(self, analyzer):
        """Test that _calculate_real_probability uses the new realistic formula."""
        # Test with moderate score and factors
        prob = analyzer._calculate_real_probability(
            total_score=50,
            direction="long",
            bullish_count=15,
            bearish_count=5,
            neutral_count=5
        )
        
        # Should be within realistic range (50-78%)
        assert 50 <= prob <= 78
        
        # Test with extreme score
        prob_extreme = analyzer._calculate_real_probability(
            total_score=100,
            direction="long",
            bullish_count=20,
            bearish_count=5,
            neutral_count=5
        )
        
        # Should be capped at MAX_PROBABILITY
        assert prob_extreme <= 78
    
    def test_probability_never_exceeds_max(self, analyzer):
        """Test that probability calculations never exceed MAX_PROBABILITY."""
        # Test various scenarios
        test_cases = [
            (100, "long", 25, 0, 0),
            (150, "short", 0, 25, 0),
            (80, "long", 20, 3, 2),
            (-100, "short", 5, 20, 0),
        ]
        
        for score, direction, bullish, bearish, neutral in test_cases:
            prob = analyzer._calculate_real_probability(
                total_score=score,
                direction=direction,
                bullish_count=bullish,
                bearish_count=bearish,
                neutral_count=neutral
            )
            assert prob <= analyzer.MAX_PROBABILITY, \
                f"Probability {prob} exceeds MAX_PROBABILITY {analyzer.MAX_PROBABILITY} for score={score}"
            assert prob >= 50, f"Probability {prob} is below minimum 50% for score={score}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
