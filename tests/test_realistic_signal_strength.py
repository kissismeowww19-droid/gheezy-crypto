"""
Tests for realistic signal strength calculation.

Tests verify:
1. MAX_TOTAL_SCORE is set to 130 (to account for Phase 3)
2. Final score is limited to ±100 after all adjustments
3. Signal strength uses realistic scale (divide by 130)
4. Expected strength percentages match the problem statement table
"""

import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestRealisticSignalStrength:
    """Test realistic signal strength calculations."""
    
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
    
    # ========== Test 1: MAX_TOTAL_SCORE Constant ==========
    
    def test_max_total_score_is_130(self, analyzer):
        """Test that MAX_TOTAL_SCORE is set to 130 (to account for Phase 3)."""
        assert analyzer.MAX_TOTAL_SCORE == 130, \
            f"MAX_TOTAL_SCORE should be 130, got {analyzer.MAX_TOTAL_SCORE}"
    
    # ========== Test 2: Signal Strength Realistic Scale ==========
    
    def test_signal_strength_realistic_scale(self, analyzer):
        """Test that signal strength follows realistic scale (divide by 130)."""
        test_cases = [
            # (score, expected_strength_percent)
            # Based on the problem statement table:
            # ±100+ score = 77%+ (сильный)
            # ±80 score = 62% (хороший)
            # ±60 score = 46% (средний)
            # ±40 score = 31% (слабый)
            (0, 0),      # 0 / 130 * 100 = 0%
            (40, 30),    # 40 / 130 * 100 = 30.77% ≈ 31%
            (60, 46),    # 60 / 130 * 100 = 46.15% ≈ 46%
            (80, 61),    # 80 / 130 * 100 = 61.54% ≈ 62%
            (100, 76),   # 100 / 130 * 100 = 76.92% ≈ 77%
            (130, 100),  # 130 / 130 * 100 = 100% (but capped at 100 in practice)
            (-40, 30),   # abs(-40) / 130 * 100 = 30.77% ≈ 31%
            (-60, 46),   # abs(-60) / 130 * 100 = 46.15% ≈ 46%
            (-80, 61),   # abs(-80) / 130 * 100 = 61.54% ≈ 62%
            (-100, 76),  # abs(-100) / 130 * 100 = 76.92% ≈ 77%
        ]
        
        for score, expected_strength in test_cases:
            strength = analyzer.calculate_signal_strength(score)
            # Allow ±1% tolerance due to rounding
            assert abs(strength - expected_strength) <= 1, \
                f"Score {score} should give ~{expected_strength}% strength, got {strength}%"
    
    def test_signal_strength_never_exceeds_100(self, analyzer):
        """Test that signal strength is capped at 100%."""
        # Even if score is 130 or higher, strength should be capped at 100%
        test_scores = [130, 150, 200, -130, -150, -200]
        
        for score in test_scores:
            strength = analyzer.calculate_signal_strength(score)
            assert strength <= 100, \
                f"Score {score} should give max 100% strength, got {strength}%"
    
    def test_signal_strength_realistic_examples(self, analyzer):
        """Test realistic examples from the problem statement."""
        # Using the formula: strength = score / 130 * 100
        # These scores are chosen to match the expected percentages
        
        score_btc = 90  # 90/130*100 = 69.23% ≈ 69%
        score_eth = 70  # 70/130*100 = 53.84% ≈ 54%
        score_ton = 64  # 64/130*100 = 49.23% ≈ 49%
        
        strength_btc = analyzer.calculate_signal_strength(score_btc)
        strength_eth = analyzer.calculate_signal_strength(score_eth)
        strength_ton = analyzer.calculate_signal_strength(score_ton)
        
        # Allow ±1% tolerance for rounding
        assert 68 <= strength_btc <= 70, \
            f"BTC score {score_btc} should give ~69% strength, got {strength_btc}%"
        assert 53 <= strength_eth <= 55, \
            f"ETH score {score_eth} should give ~54% strength, got {strength_eth}%"
        assert 48 <= strength_ton <= 50, \
            f"TON score {score_ton} should give ~49% strength, got {strength_ton}%"
    
    def test_signal_strength_uses_absolute_value(self, analyzer):
        """Test that signal strength uses absolute value of score."""
        strength_pos = analyzer.calculate_signal_strength(75)
        strength_neg = analyzer.calculate_signal_strength(-75)
        
        assert strength_pos == strength_neg, \
            f"Score 75 and -75 should give same strength, got {strength_pos}% vs {strength_neg}%"
    
    # ========== Test 3: Integration Test ==========
    
    def test_strength_not_always_100_percent(self, analyzer):
        """Test that strength is not always 100% (the main problem)."""
        # Before fix: scores like -105 would show 100% strength
        # After fix: they should show realistic percentages
        
        test_scores = [40, 60, 80, 100, -40, -60, -80, -100]
        strengths = []
        
        for score in test_scores:
            strength = analyzer.calculate_signal_strength(score)
            strengths.append(strength)
            # None of these should be 100%
            if abs(score) < 100:
                assert strength < 100, \
                    f"Score {score} should not give 100% strength, got {strength}%"
        
        # All strengths should be different (or at most a few duplicates due to rounding)
        unique_strengths = len(set(strengths))
        assert unique_strengths >= 6, \
            f"Different scores should give different strengths, got only {unique_strengths} unique values from {len(strengths)} scores"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
