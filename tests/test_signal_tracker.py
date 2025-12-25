"""
Tests for Signal Tracker module.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import sys
import os
from unittest.mock import patch, AsyncMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.signal_tracker import SignalTracker, TrackedSignal


class TestSignalTracker:
    """Tests for SignalTracker class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
            db_path = f.name
        yield db_path
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def tracker(self, temp_db):
        """Create a tracker instance with temporary database."""
        return SignalTracker(db_path=temp_db)
    
    def _make_signal_old(self, tracker, signal_id, hours_ago=5):
        """Helper to make a signal appear older than it is."""
        old_timestamp = datetime.now() - timedelta(hours=hours_ago)
        with sqlite3.connect(tracker.db_path) as conn:
            conn.execute(
                'UPDATE signals SET timestamp = ? WHERE id = ?',
                (old_timestamp.isoformat(), signal_id)
            )
            conn.commit()
    
    def test_initialization(self, tracker, temp_db):
        """Test that tracker initializes correctly."""
        assert tracker.db_path == Path(temp_db)
        assert tracker.db_path.exists()
        
        # Verify table exists
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='signals'"
            )
            assert cursor.fetchone() is not None
    
    def test_save_signal_long(self, tracker):
        """Test saving a long signal."""
        signal = tracker.save_signal(
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,  # +1.5%
            target2_price=51000.0,  # +2.0%
            stop_loss_price=49700.0,  # -0.6%
            probability=65.0
        )
        
        assert signal.id is not None
        assert signal.user_id == 123
        assert signal.symbol == "BTC"
        assert signal.direction == "long"
        assert signal.entry_price == 50000.0
        assert signal.target1_price == 50750.0
        assert signal.target2_price == 51000.0
        assert signal.stop_loss_price == 49700.0
        assert signal.probability == 65.0
        assert signal.result == "pending"
    
    def test_save_signal_short(self, tracker):
        """Test saving a short signal."""
        signal = tracker.save_signal(
            user_id=456,
            symbol="ETH",
            direction="short",
            entry_price=3000.0,
            target1_price=2955.0,  # -1.5%
            target2_price=2940.0,  # -2.0%
            stop_loss_price=3018.0,  # +0.6%
            probability=70.0
        )
        
        assert signal.id is not None
        assert signal.direction == "short"
        assert signal.result == "pending"
    
    def test_save_signal_sideways(self, tracker):
        """Test saving a sideways signal."""
        signal = tracker.save_signal(
            user_id=789,
            symbol="TON",
            direction="sideways",
            entry_price=5.0,
            target1_price=5.05,
            target2_price=5.10,
            stop_loss_price=4.97,
            probability=55.0
        )
        
        assert signal.id is not None
        assert signal.direction == "sideways"
    
    def test_check_previous_signal_no_signal(self, tracker):
        """Test checking when there's no previous signal."""
        result = tracker.check_previous_signal(
            user_id=999,
            symbol="BTC",
            current_price=50000.0
        )
        
        assert result is None
    
    def test_check_previous_signal_long_win(self, tracker):
        """Test checking a long signal that wins (fallback to current price)."""
        # Save a long signal
        signal = tracker.save_signal(
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Make signal old enough (>4 hours)
        self._make_signal_old(tracker, signal.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Check with price at target1 (win)
            result = tracker.check_previous_signal(
                user_id=123,
                symbol="BTC",
                current_price=50750.0
            )
        
        assert result is not None
        assert result["had_signal"] is True
        assert result["direction"] == "long"
        assert result["entry_price"] == 50000.0
        assert result["target1_reached"] is True
        assert result["target2_reached"] is False
        assert result["stop_hit"] is False
        assert result["result"] == "win"
        assert result["pnl_percent"] == pytest.approx(1.5, rel=0.01)
    
    def test_check_previous_signal_long_loss(self, tracker):
        """Test checking a long signal that loses (fallback to current price)."""
        # Save a long signal
        signal = tracker.save_signal(
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Make signal old enough (>4 hours)
        self._make_signal_old(tracker, signal.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Check with price at stop loss (loss)
            result = tracker.check_previous_signal(
                user_id=123,
                symbol="BTC",
                current_price=49700.0
            )
        
        assert result is not None
        assert result["had_signal"] is True
        assert result["target1_reached"] is False
        assert result["stop_hit"] is True
        assert result["result"] == "loss"
        assert result["pnl_percent"] < 0
    
    def test_check_previous_signal_short_win(self, tracker):
        """Test checking a short signal that wins (fallback to current price)."""
        # Save a short signal
        signal = tracker.save_signal(
            user_id=456,
            symbol="ETH",
            direction="short",
            entry_price=3000.0,
            target1_price=2955.0,
            target2_price=2940.0,
            stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Make signal old enough (>4 hours)
        self._make_signal_old(tracker, signal.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Check with price at target1 (win)
            result = tracker.check_previous_signal(
                user_id=456,
                symbol="ETH",
                current_price=2955.0
            )
        
        assert result is not None
        assert result["direction"] == "short"
        assert result["target1_reached"] is True
        assert result["result"] == "win"
        assert result["pnl_percent"] == pytest.approx(1.5, rel=0.01)
    
    def test_check_previous_signal_short_loss(self, tracker):
        """Test checking a short signal that loses (fallback to current price)."""
        # Save a short signal
        signal = tracker.save_signal(
            user_id=456,
            symbol="ETH",
            direction="short",
            entry_price=3000.0,
            target1_price=2955.0,
            target2_price=2940.0,
            stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Make signal old enough (>4 hours)
        self._make_signal_old(tracker, signal.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Check with price at stop loss (loss)
            result = tracker.check_previous_signal(
                user_id=456,
                symbol="ETH",
                current_price=3018.0
            )
        
        assert result is not None
        assert result["stop_hit"] is True
        assert result["result"] == "loss"
    
    def test_check_previous_signal_pending(self, tracker):
        """Test checking a signal that's still pending."""
        # Save a long signal
        tracker.save_signal(
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Check with price between entry and targets (pending)
        result = tracker.check_previous_signal(
            user_id=123,
            symbol="BTC",
            current_price=50400.0
        )
        
        assert result is not None
        assert result["result"] == "pending"
        assert result["target1_reached"] is False
        assert result["stop_hit"] is False
    
    def test_check_previous_signal_sideways_win(self, tracker):
        """Test checking a sideways signal that wins (fallback to current price)."""
        # Save a sideways signal
        signal = tracker.save_signal(
            user_id=789,
            symbol="TON",
            direction="sideways",
            entry_price=5.0,
            target1_price=5.05,
            target2_price=5.10,
            stop_loss_price=4.97,
            probability=55.0
        )
        
        # Make signal old enough (>4 hours)
        self._make_signal_old(tracker, signal.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Check with price in range (win)
            result = tracker.check_previous_signal(
                user_id=789,
                symbol="TON",
                current_price=5.0
            )
        
        assert result is not None
        assert result["direction"] == "sideways"
        assert result["result"] == "win"
    
    def test_get_user_stats_empty(self, tracker):
        """Test getting stats for user with no signals."""
        stats = tracker.get_user_stats(user_id=999)
        
        assert stats["total_signals"] == 0
        assert stats["wins"] == 0
        assert stats["losses"] == 0
        assert stats["pending"] == 0
        assert stats["win_rate"] == 0.0
        assert stats["total_pnl"] == 0.0
    
    def test_get_user_stats_with_signals(self, tracker):
        """Test getting stats for user with signals."""
        user_id = 123
        
        # Save some signals
        signal1 = tracker.save_signal(
            user_id=user_id,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        signal2 = tracker.save_signal(
            user_id=user_id,
            symbol="ETH",
            direction="short",
            entry_price=3000.0,
            target1_price=2955.0,
            target2_price=2940.0,
            stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Make signals old enough
        self._make_signal_old(tracker, signal1.id, hours_ago=5)
        self._make_signal_old(tracker, signal2.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Trigger wins and losses
            tracker.check_previous_signal(user_id, "BTC", 50750.0)  # Win
            tracker.check_previous_signal(user_id, "ETH", 3018.0)  # Loss
        
        stats = tracker.get_user_stats(user_id)
        
        assert stats["total_signals"] == 2
        assert stats["wins"] == 1
        assert stats["losses"] == 1
        assert stats["pending"] == 0
        assert stats["win_rate"] == 50.0
        assert stats["total_pnl"] != 0.0  # Should have some P&L
    
    def test_multiple_users(self, tracker):
        """Test that signals are isolated per user."""
        # User 1 signal
        tracker.save_signal(
            user_id=111,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # User 2 signal (same symbol)
        tracker.save_signal(
            user_id=222,
            symbol="BTC",
            direction="short",
            entry_price=50000.0,
            target1_price=49250.0,
            target2_price=49000.0,
            stop_loss_price=50300.0,
            probability=70.0
        )
        
        # Check user 1
        result1 = tracker.check_previous_signal(111, "BTC", 50800.0)
        assert result1["direction"] == "long"
        
        # Check user 2
        result2 = tracker.check_previous_signal(222, "BTC", 50800.0)
        assert result2["direction"] == "short"
    
    def test_multiple_symbols_per_user(self, tracker):
        """Test that user can have signals for different symbols."""
        user_id = 123
        
        # BTC signal
        tracker.save_signal(
            user_id=user_id,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # ETH signal
        tracker.save_signal(
            user_id=user_id,
            symbol="ETH",
            direction="short",
            entry_price=3000.0,
            target1_price=2955.0,
            target2_price=2940.0,
            stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Check both
        btc_result = tracker.check_previous_signal(user_id, "BTC", 50800.0)
        eth_result = tracker.check_previous_signal(user_id, "ETH", 2900.0)
        
        assert btc_result["direction"] == "long"
        assert eth_result["direction"] == "short"
