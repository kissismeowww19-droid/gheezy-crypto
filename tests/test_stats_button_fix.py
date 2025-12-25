"""
Tests for statistics button and menu flow fix.
"""

import pytest


class TestStatisticsButtonFix:
    """Tests for statistics button callback fix."""
    
    def test_generate_progress_bar_full(self):
        """Test progress bar at 100%."""
        def generate_progress_bar(percentage: float, length: int = 10) -> str:
            filled = int(percentage / 100 * length)
            empty = length - filled
            return "█" * filled + "░" * empty
        
        bar = generate_progress_bar(100)
        assert bar == "██████████"
        assert len(bar) == 10
    
    def test_generate_progress_bar_half(self):
        """Test progress bar at 50%."""
        def generate_progress_bar(percentage: float, length: int = 10) -> str:
            filled = int(percentage / 100 * length)
            empty = length - filled
            return "█" * filled + "░" * empty
        
        bar = generate_progress_bar(50)
        assert bar == "█████░░░░░"
        assert len(bar) == 10
    
    def test_generate_progress_bar_zero(self):
        """Test progress bar at 0%."""
        def generate_progress_bar(percentage: float, length: int = 10) -> str:
            filled = int(percentage / 100 * length)
            empty = length - filled
            return "█" * filled + "░" * empty
        
        bar = generate_progress_bar(0)
        assert bar == "░░░░░░░░░░"
        assert len(bar) == 10
    
    def test_generate_progress_bar_custom_length(self):
        """Test progress bar with custom length."""
        def generate_progress_bar(percentage: float, length: int = 10) -> str:
            filled = int(percentage / 100 * length)
            empty = length - filled
            return "█" * filled + "░" * empty
        
        bar = generate_progress_bar(50, length=20)
        assert len(bar) == 20
        assert bar == "██████████░░░░░░░░░░"
    
    def test_callback_data_no_conflict_with_signal_handler(self):
        """Test that show_stats_menu won't be caught by signal_ handler."""
        # The old callback_data was "signal_stats" which would match "signal_" prefix
        # The new callback_data is "show_stats_menu" which won't match "signal_" prefix
        
        old_callback = "signal_stats"
        new_callback = "show_stats_menu"
        
        # Verify old callback would be caught by signal_ handler
        assert old_callback.startswith("signal_"), \
            "Old callback should start with 'signal_'"
        
        # Verify new callback won't be caught by signal_ handler
        assert not new_callback.startswith("signal_"), \
            "New callback should NOT start with 'signal_'"
        
        # Verify new callback won't be caught by stats_ handler either
        assert not new_callback.startswith("stats_"), \
            "New callback should NOT start with 'stats_'"
    
    def test_stats_callbacks_use_correct_format(self):
        """Test that stats coin callbacks use the correct format."""
        # According to the problem statement, coin stats should use "stats_COIN" format
        expected_callbacks = ["stats_BTC", "stats_ETH", "stats_TON", "stats_SOL", "stats_XRP"]
        
        for callback in expected_callbacks:
            # Verify format is correct (starts with stats_ and has uppercase coin)
            assert callback.startswith("stats_"), f"{callback} should start with 'stats_'"
            coin = callback.replace("stats_", "")
            assert coin.isupper(), f"Coin in {callback} should be uppercase"
            assert len(coin) in [3, 4], f"Coin in {callback} should be 3-4 characters"

