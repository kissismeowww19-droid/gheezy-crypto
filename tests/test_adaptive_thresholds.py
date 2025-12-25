"""
Tests for adaptive thresholds functionality.
"""

import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


class TestAdaptiveThresholds:
    """Tests for adaptive threshold functionality."""
    
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
    
    def test_calculate_adaptive_threshold_no_conflict(self, analyzer):
        """Test adaptive threshold with no conflict."""
        # Strong bullish: 5 bullish, 1 bearish
        threshold, conflict_level = analyzer.calculate_adaptive_threshold(5, 1)
        
        assert threshold == 1.75  # Base threshold
        assert conflict_level == "none"
    
    def test_calculate_adaptive_threshold_moderate_conflict(self, analyzer):
        """Test adaptive threshold with moderate conflict."""
        # Moderate conflict: 3 bullish, 2 bearish (difference = 1)
        threshold, conflict_level = analyzer.calculate_adaptive_threshold(3, 2)
        
        assert threshold == 2.25  # Base (1.75) + 0.5
        assert conflict_level == "moderate"
    
    def test_calculate_adaptive_threshold_strong_conflict(self, analyzer):
        """Test adaptive threshold with strong conflict."""
        # Strong conflict: 3 bullish, 3 bearish (difference = 0)
        threshold, conflict_level = analyzer.calculate_adaptive_threshold(3, 3)
        
        assert threshold == 2.50  # Base (1.75) + 0.75
        assert conflict_level == "strong"
    
    def test_calculate_adaptive_threshold_insufficient_factors(self, analyzer):
        """Test adaptive threshold with insufficient factors."""
        # Only 1 factor on each side - not enough for conflict analysis
        threshold, conflict_level = analyzer.calculate_adaptive_threshold(1, 1)
        
        assert threshold == 1.75  # Base threshold
        assert conflict_level == "none"
    
    def test_calculate_adaptive_threshold_asymmetric(self, analyzer):
        """Test adaptive threshold with asymmetric factor counts."""
        # 2 bullish, 4 bearish - difference is 2, no conflict
        threshold, conflict_level = analyzer.calculate_adaptive_threshold(2, 4)
        
        assert threshold == 1.75  # Base threshold (difference > 1)
        assert conflict_level == "none"
    
    def test_apply_adaptive_threshold_long(self, analyzer):
        """Test applying adaptive threshold for long signal."""
        # Score above base threshold (1.75) but below moderate threshold (2.25)
        weighted_score = 2.0
        bullish_count = 3
        bearish_count = 2  # Moderate conflict
        
        direction, warning = analyzer.apply_adaptive_threshold(
            weighted_score, bullish_count, bearish_count
        )
        
        # With moderate conflict (threshold = 2.25), score 2.0 is NOT enough for long
        assert direction == "sideways"
        assert warning == "⚠️ Умеренный конфликт — порог повышен до ±2.25"
    
    def test_apply_adaptive_threshold_long_strong_signal(self, analyzer):
        """Test applying adaptive threshold for strong long signal with conflict."""
        # Score above moderate threshold even with conflict
        weighted_score = 2.6
        bullish_count = 3
        bearish_count = 3  # Strong conflict, threshold = 2.50
        
        direction, warning = analyzer.apply_adaptive_threshold(
            weighted_score, bullish_count, bearish_count
        )
        
        # Score 2.6 > 2.50, so still long
        assert direction == "long"
        assert warning == "⚠️ Сильный конфликт факторов — порог повышен до ±2.50"
    
    def test_apply_adaptive_threshold_short(self, analyzer):
        """Test applying adaptive threshold for short signal."""
        # Score below negative base threshold with no conflict
        weighted_score = -2.0
        bullish_count = 1
        bearish_count = 5  # No conflict
        
        direction, warning = analyzer.apply_adaptive_threshold(
            weighted_score, bullish_count, bearish_count
        )
        
        assert direction == "short"
        assert warning is None  # No conflict warning
    
    def test_apply_adaptive_threshold_sideways_with_conflict(self, analyzer):
        """Test applying adaptive threshold for sideways with strong conflict."""
        # Weak score with strong conflict
        weighted_score = 1.5
        bullish_count = 4
        bearish_count = 4  # Strong conflict
        
        direction, warning = analyzer.apply_adaptive_threshold(
            weighted_score, bullish_count, bearish_count
        )
        
        # Score 1.5 < 2.50 (strong conflict threshold)
        assert direction == "sideways"
        assert warning == "⚠️ Сильный конфликт факторов — порог повышен до ±2.50"
    
    def test_apply_adaptive_threshold_no_warning_when_no_conflict(self, analyzer):
        """Test that no warning is shown when there's no conflict."""
        weighted_score = 2.0
        bullish_count = 5
        bearish_count = 1  # No conflict
        
        direction, warning = analyzer.apply_adaptive_threshold(
            weighted_score, bullish_count, bearish_count
        )
        
        assert direction == "long"
        assert warning is None
    
    def test_adaptive_threshold_edge_case_equal_strong(self, analyzer):
        """Test edge case with equal strong factors."""
        # 5 bullish, 5 bearish - very strong conflict
        threshold, conflict_level = analyzer.calculate_adaptive_threshold(5, 5)
        
        assert threshold == 2.50
        assert conflict_level == "strong"
    
    def test_adaptive_threshold_edge_case_moderate_boundary(self, analyzer):
        """Test edge case at moderate conflict boundary."""
        # 3 bullish, 4 bearish - difference = 1 (moderate)
        threshold, conflict_level = analyzer.calculate_adaptive_threshold(3, 4)
        
        assert threshold == 2.25
        assert conflict_level == "moderate"
    
    def test_adaptive_threshold_prevents_weak_signals(self, analyzer):
        """Test that adaptive threshold prevents weak signals during conflict."""
        # Scenario: factors are conflicted, but score is weak
        # Without adaptive threshold: would be "long" (1.8 > 1.75)
        # With adaptive threshold: should be "sideways" (1.8 < 2.25)
        
        weighted_score = 1.8
        bullish_count = 3
        bearish_count = 2  # Moderate conflict
        
        direction, warning = analyzer.apply_adaptive_threshold(
            weighted_score, bullish_count, bearish_count
        )
        
        # Adaptive threshold correctly filters out weak signal
        assert direction == "sideways"
        assert "Умеренный конфликт" in warning


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
