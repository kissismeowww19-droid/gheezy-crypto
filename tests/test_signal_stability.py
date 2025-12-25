"""
Tests for Signal Stability Manager.
"""

import pytest
import time
from unittest.mock import Mock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import directly to avoid dependency issues
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'signals'))
from signal_stability import SignalStabilityManager


class TestSignalStabilityManager:
    """Tests for SignalStabilityManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a stability manager instance."""
        return SignalStabilityManager()
    
    def test_initialization(self, manager):
        """Test that manager initializes correctly."""
        assert manager.last_signals == {}
        assert manager.COOLDOWN_MINUTES == 60
        assert manager.CONFIRMATION_REQUIRED == 3
        assert manager.SCORE_CHANGE_THRESHOLD == 0.3
    
    def test_first_signal_allowed(self, manager):
        """Test that first signal is always allowed."""
        result = manager.should_change_signal(
            coin="BTC",
            new_direction="long",
            new_score=5.5
        )
        assert result is True
    
    def test_same_direction_allowed(self, manager):
        """Test that same direction update is always allowed."""
        # First signal
        manager.update_signal("BTC", "long", 5.0)
        
        # Same direction - should be allowed
        result = manager.should_change_signal(
            coin="BTC",
            new_direction="long",
            new_score=6.0
        )
        assert result is True
    
    def test_cooldown_blocks_change(self, manager):
        """Test that cooldown blocks signal change within 1 hour."""
        # Set initial signal
        manager.update_signal("BTC", "long", 5.0)
        
        # Try to change immediately (should be blocked)
        result = manager.should_change_signal(
            coin="BTC",
            new_direction="short",
            new_score=5.2
        )
        assert result is False
    
    def test_cooldown_passes_after_time(self, manager):
        """Test that cooldown allows change after 1 hour."""
        # Set initial signal with old timestamp
        manager.update_signal("BTC", "long", 5.0)
        
        # Mock time to be 61 minutes later
        with patch('time.time') as mock_time:
            old_time = manager.last_signals["BTC"]["time"]
            mock_time.return_value = old_time + (61 * 60)  # 61 minutes later
            
            result = manager.should_change_signal(
                coin="BTC",
                new_direction="short",
                new_score=5.2
            )
            assert result is True
    
    def test_score_threshold_bypasses_cooldown(self, manager):
        """Test that 30% score change bypasses cooldown."""
        # Set initial signal
        manager.update_signal("BTC", "long", 5.0)
        
        # Change with 40% score change (should bypass cooldown)
        result = manager.should_change_signal(
            coin="BTC",
            new_direction="short",
            new_score=7.0  # 40% change from 5.0
        )
        assert result is True
    
    def test_confirmations_allow_change(self, manager):
        """Test that 3 confirmations allow signal change."""
        # Set initial signal
        manager.update_signal("BTC", "long", 5.0)
        
        # First confirmation
        result1 = manager.should_change_signal(
            coin="BTC",
            new_direction="short",
            new_score=5.2
        )
        assert result1 is False
        assert manager.last_signals["BTC"]["confirmations"] == 1
        
        # Second confirmation
        result2 = manager.should_change_signal(
            coin="BTC",
            new_direction="short",
            new_score=5.2
        )
        assert result2 is False
        assert manager.last_signals["BTC"]["confirmations"] == 2
        
        # Third confirmation (should allow change)
        result3 = manager.should_change_signal(
            coin="BTC",
            new_direction="short",
            new_score=5.2
        )
        assert result3 is True
        assert manager.last_signals["BTC"]["confirmations"] == 3
    
    def test_confirmations_reset_on_direction_change(self, manager):
        """Test that confirmations reset if pending direction changes."""
        # Set initial signal
        manager.update_signal("BTC", "long", 5.0)
        
        # First confirmation for short
        manager.should_change_signal("BTC", "short", 5.2)
        assert manager.last_signals["BTC"]["confirmations"] == 1
        
        # Change to sideways (should reset)
        manager.should_change_signal("BTC", "sideways", 5.1)
        assert manager.last_signals["BTC"]["confirmations"] == 1
        assert manager.last_signals["BTC"]["pending_direction"] == "sideways"
    
    def test_update_signal(self, manager):
        """Test updating signal."""
        manager.update_signal("BTC", "long", 5.5)
        
        signal = manager.last_signals["BTC"]
        assert signal["direction"] == "long"
        assert signal["score"] == 5.5
        assert signal["time"] > 0
        assert signal["confirmations"] == 0
        assert signal["pending_direction"] is None
    
    def test_get_stable_signal_changes(self, manager):
        """Test get_stable_signal when change is allowed."""
        result = manager.get_stable_signal(
            coin="BTC",
            new_direction="long",
            new_score=6.0
        )
        
        assert result["direction"] == "long"
        assert result["score"] == 6.0
        assert result["changed"] is True
        assert "conditions met" in result["reason"].lower()
    
    def test_get_stable_signal_blocked(self, manager):
        """Test get_stable_signal when change is blocked."""
        # Set initial signal
        manager.update_signal("BTC", "long", 5.0)
        
        # Try to change (should be blocked)
        result = manager.get_stable_signal(
            coin="BTC",
            new_direction="short",
            new_score=5.2
        )
        
        assert result["direction"] == "long"  # Old direction
        assert result["score"] == 5.0  # Old score
        assert result["changed"] is False
        assert "blocked" in result["reason"].lower()
    
    def test_get_last_signal(self, manager):
        """Test getting last signal."""
        # No signal yet
        assert manager.get_last_signal("BTC") is None
        
        # Add signal
        manager.update_signal("BTC", "long", 5.5)
        
        # Get signal
        signal = manager.get_last_signal("BTC")
        assert signal is not None
        assert signal["direction"] == "long"
        assert signal["score"] == 5.5
    
    def test_clear_signals(self, manager):
        """Test clearing all signals."""
        manager.update_signal("BTC", "long", 5.5)
        manager.update_signal("ETH", "short", 3.2)
        
        assert len(manager.last_signals) == 2
        
        manager.clear_signals()
        
        assert len(manager.last_signals) == 0
    
    def test_case_insensitive_coin(self, manager):
        """Test that coin symbol is case-insensitive."""
        manager.update_signal("btc", "long", 5.0)
        
        result = manager.should_change_signal(
            coin="BTC",
            new_direction="short",
            new_score=5.2
        )
        
        # Should find the signal despite different case
        assert result is False
        assert "BTC" in manager.last_signals
    
    def test_multiple_coins_independent(self, manager):
        """Test that different coins are tracked independently."""
        manager.update_signal("BTC", "long", 5.0)
        manager.update_signal("ETH", "short", 3.0)
        
        # Change BTC (should be blocked by cooldown)
        btc_result = manager.should_change_signal("BTC", "short", 5.2)
        assert btc_result is False
        
        # ETH should still have its own state
        eth_signal = manager.get_last_signal("ETH")
        assert eth_signal["direction"] == "short"
        assert eth_signal["score"] == 3.0
    
    def test_zero_score_handling(self, manager):
        """Test handling of zero score in score change calculation."""
        manager.update_signal("BTC", "long", 0.0)
        
        # Any change from zero should be considered significant
        result = manager.should_change_signal(
            coin="BTC",
            new_direction="short",
            new_score=1.0
        )
        
        # Should allow change due to significant score change
        assert result is True
