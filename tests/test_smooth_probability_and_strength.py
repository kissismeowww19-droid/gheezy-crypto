"""
Tests for smooth probability calculation and signal strength improvements.

Tests verify:
1. No single factor contributes more than ±15 to total score
2. Different scores produce different probabilities (smooth scaling)
3. L/S Ratio is properly limited
4. Signal strength calculation follows the new smooth scale
"""

import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestSmoothProbabilityAndStrength:
    """Test smooth probability and signal strength calculations."""
    
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
    
    # ========== Test 1: Factor Contribution Capping ==========
    
    def test_factor_contribution_capped_at_15(self, analyzer):
        """Test that individual factor contributions are capped at ±15."""
        # Test positive cap
        raw_score = 10.0
        weight = 2.0
        capped = analyzer._cap_factor_contribution(raw_score, weight)
        assert capped == 15.0, f"Expected 15.0, got {capped} (10.0 * 2.0 = 20 should be capped at 15)"
        
        # Test negative cap
        raw_score = -10.0
        weight = 2.0
        capped = analyzer._cap_factor_contribution(raw_score, weight)
        assert capped == -15.0, f"Expected -15.0, got {capped} (-10.0 * 2.0 = -20 should be capped at -15)"
        
        # Test within limits
        raw_score = 5.0
        weight = 2.0
        capped = analyzer._cap_factor_contribution(raw_score, weight)
        assert capped == 10.0, f"Expected 10.0, got {capped} (5.0 * 2.0 = 10 should not be capped)"
    
    def test_max_single_factor_score_constant(self, analyzer):
        """Test that MAX_SINGLE_FACTOR_SCORE is set to 15."""
        assert analyzer.MAX_SINGLE_FACTOR_SCORE == 15, \
            f"MAX_SINGLE_FACTOR_SCORE should be 15, got {analyzer.MAX_SINGLE_FACTOR_SCORE}"
    
    # ========== Test 2: L/S Ratio Detailed Score Limits ==========
    
    def test_ls_ratio_extreme_high_limited(self, analyzer):
        """Test that extreme high L/S ratio (>2.5) gives -10 score."""
        ls_ratio_data = {"average_ratio": 3.0}
        score = analyzer._calculate_ls_ratio_detailed_score(ls_ratio_data)
        assert score == -10, f"L/S ratio 3.0 should give -10, got {score}"
        
        # After weighting (1.5x) and capping, should be -15
        weighted = analyzer._cap_factor_contribution(score, analyzer.LS_RATIO_DETAILED_WEIGHT)
        assert weighted == -15.0, f"Weighted L/S score should be -15, got {weighted}"
    
    def test_ls_ratio_extreme_low_limited(self, analyzer):
        """Test that extreme low L/S ratio (<0.4) gives +10 score."""
        ls_ratio_data = {"average_ratio": 0.3}
        score = analyzer._calculate_ls_ratio_detailed_score(ls_ratio_data)
        assert score == 10, f"L/S ratio 0.3 should give +10, got {score}"
        
        # After weighting (1.5x) and capping, should be +15
        weighted = analyzer._cap_factor_contribution(score, analyzer.LS_RATIO_DETAILED_WEIGHT)
        assert weighted == 15.0, f"Weighted L/S score should be +15, got {weighted}"
    
    def test_ls_ratio_gradual_scaling(self, analyzer):
        """Test that L/S ratio uses gradual scaling for moderate values."""
        test_cases = [
            (2.6, -10),  # >2.5 = -10
            (2.3, -7),   # >2.0 = -7
            (1.7, -3),   # >1.5 = -3
            (1.0, 0),    # neutral zone (0.7-1.5) = 0
            (0.6, 3),    # <0.7 = +3
            (0.45, 7),   # <0.5 = +7
            (0.35, 10),  # <0.4 = +10
        ]
        
        for ratio, expected_score in test_cases:
            ls_ratio_data = {"average_ratio": ratio}
            score = analyzer._calculate_ls_ratio_detailed_score(ls_ratio_data)
            assert score == expected_score, \
                f"L/S ratio {ratio} should give {expected_score}, got {score}"
    
    # ========== Test 3: Signal Strength Calculation ==========
    
    def test_signal_strength_smooth_scaling(self, analyzer):
        """Test that signal strength follows smooth scaling based on score."""
        test_cases = [
            # score, expected_strength_range (min, max)
            (0, (0, 0)),      # 0 score = 0%
            (10, (12, 13)),   # 10 score ≈ 12.5% (10 * 1.25)
            (20, (25, 25)),   # 20 score = 25%
            (30, (37, 38)),   # 30 score ≈ 37.5% (25 + (10 * 1.25))
            (40, (50, 50)),   # 40 score = 50%
            (50, (62, 63)),   # 50 score ≈ 62.5% (50 + (10 * 1.25))
            (60, (75, 75)),   # 60 score = 75%
            (80, (87, 88)),   # 80 score ≈ 87.5% (75 + (20 * 0.625))
            (100, (100, 100)), # 100 score = 100%
            (-50, (62, 63)),   # -50 score ≈ 62.5% (abs value used)
        ]
        
        for score, (min_strength, max_strength) in test_cases:
            strength = analyzer.calculate_signal_strength(score)
            assert min_strength <= strength <= max_strength, \
                f"Score {score} should give strength {min_strength}-{max_strength}%, got {strength}%"
    
    def test_signal_strength_boundaries(self, analyzer):
        """Test signal strength boundaries."""
        # Minimum
        strength = analyzer.calculate_signal_strength(0)
        assert strength == 0, f"Score 0 should give 0% strength, got {strength}%"
        
        # Maximum
        strength = analyzer.calculate_signal_strength(100)
        assert strength == 100, f"Score 100 should give 100% strength, got {strength}%"
        
        # Negative scores use absolute value
        strength_neg = analyzer.calculate_signal_strength(-75)
        strength_pos = analyzer.calculate_signal_strength(75)
        assert strength_neg == strength_pos, \
            f"Score -75 and 75 should give same strength, got {strength_neg}% vs {strength_pos}%"
    
    # ========== Test 4: Probability Smooth Scaling ==========
    
    def test_probability_from_score_smooth_scaling(self, analyzer):
        """Test that probability calculation uses smooth scaling."""
        test_cases = [
            # score, expected_probability
            (0, 50),     # 0 score = 50%
            (10, 52),    # 10 score = 52%
            (15, 55),    # 15 score = 55% (boundary)
            (20, 58),    # 20 score = 58%
            (30, 65),    # 30 score = 65% (boundary)
            (45, 69),    # 45 score = 69%
            (60, 75),    # 60 score = 75% (boundary)
            (80, 79),    # 80 score = 79%
            (100, 85),   # 100 score = 85% (boundary)
            (120, 87),   # 120 score = 87%
            (-50, 71),   # -50 score = 71% (abs value used)
        ]
        
        for score, expected_prob in test_cases:
            prob = analyzer._calculate_probability_from_score(score)
            assert prob == expected_prob, \
                f"Score {score} should give probability {expected_prob}%, got {prob}%"
    
    def test_probability_different_scores_different_probabilities(self, analyzer):
        """Test that different scores give different probabilities (main bug fix)."""
        # This is the key test from the problem statement:
        # BTC: score = -118 → probability should be higher than
        # ETH: score = -38  → probability (both were 75% before fix)
        
        score_btc = -118
        score_eth = -38
        
        prob_btc = analyzer._calculate_probability_from_score(score_btc)
        prob_eth = analyzer._calculate_probability_from_score(score_eth)
        
        # BTC has higher absolute score, so should have higher probability
        assert prob_btc > prob_eth, \
            f"Score {score_btc} (prob={prob_btc}%) should give higher probability than score {score_eth} (prob={prob_eth}%)"
        
        # Check they're in reasonable ranges
        assert prob_btc >= 85, f"Score -118 should give probability ≥85%, got {prob_btc}%"
        assert 65 <= prob_eth <= 75, f"Score -38 should give probability 65-75%, got {prob_eth}%"
    
    def test_probability_boundaries(self, analyzer):
        """Test probability calculation boundaries."""
        # Minimum
        prob = analyzer._calculate_probability_from_score(0)
        assert prob == 50, f"Score 0 should give 50% probability, got {prob}%"
        
        # Maximum (capped at 95%)
        prob = analyzer._calculate_probability_from_score(200)
        assert prob <= 95, f"Very high score should be capped at 95%, got {prob}%"
        
        # Check range 50-95%
        for score in [0, 10, 20, 30, 50, 75, 100, 150]:
            prob = analyzer._calculate_probability_from_score(score)
            assert 50 <= prob <= 95, \
                f"Probability for score {score} should be in range 50-95%, got {prob}%"
    
    # ========== Test 5: Full Probability Calculation ==========
    
    def test_full_probability_calculation_with_adjustments(self, analyzer):
        """Test that full probability calculation applies smooth base + adjustments."""
        # Test with minimal adjustments to see base probability effect
        prob = analyzer._calculate_probability(
            total_score=50.0,
            direction="long",
            bullish_count=5,
            bearish_count=0,
            data_sources_count=20,
            total_sources=30,
            trend_score=5.0,
        )
        
        # Base probability from score 50 should be around 69-70%
        # With good consensus and data coverage, should get bonuses
        assert 70 <= prob <= 80, \
            f"Score 50 with good factors should give probability 70-80%, got {prob}%"
    
    def test_full_probability_respects_95_percent_cap(self, analyzer):
        """Test that full probability calculation is capped at 95%."""
        # Even with extreme score and all bonuses, should not exceed 95%
        prob = analyzer._calculate_probability(
            total_score=150.0,
            direction="long",
            bullish_count=20,
            bearish_count=0,
            data_sources_count=30,
            total_sources=30,
            trend_score=10.0,
        )
        
        assert prob <= 95, f"Probability should be capped at 95%, got {prob}%"
        assert prob >= 50, f"Probability should be at least 50%, got {prob}%"
    
    def test_sideways_probability_uses_special_calculation(self, analyzer):
        """Test that sideways direction uses special probability calculation."""
        # For sideways signals, should use score-dependent calculation with 50-62% range
        prob = analyzer._calculate_probability(
            total_score=5.0,
            direction="sideways",
            bullish_count=2,
            bearish_count=2,
            data_sources_count=15,
            total_sources=30,
            trend_score=0.0,
        )
        
        # Sideways with low score should be in 50-62% range
        assert 50 <= prob <= 62, \
            f"Sideways probability should be in range 50-62%, got {prob}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
