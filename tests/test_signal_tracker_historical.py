"""
Tests for Signal Tracker with historical price checking.
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


class TestSignalTrackerHistorical:
    """Tests for SignalTracker with historical price checking."""
    
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
    
    def _create_old_signal(self, tracker, hours_ago=5, **kwargs):
        """Helper to create a signal that appears to be created hours ago."""
        # Save the signal
        signal = tracker.save_signal(**kwargs)
        
        # Manually update the timestamp to be in the past
        old_timestamp = datetime.now() - timedelta(hours=hours_ago)
        with sqlite3.connect(tracker.db_path) as conn:
            conn.execute(
                'UPDATE signals SET timestamp = ? WHERE id = ?',
                (old_timestamp.isoformat(), signal.id)
            )
            conn.commit()
        
        return signal
    
    def test_signal_less_than_4_hours_returns_pending(self, tracker):
        """Test that signals less than 4 hours old return pending status."""
        # Create a signal just 2 hours ago
        self._create_old_signal(
            tracker,
            hours_ago=2,
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Check with a winning price - should still be pending
        result = tracker.check_previous_signal(
            user_id=123,
            symbol="BTC",
            current_price=51000.0  # Way above target
        )
        
        assert result is not None
        assert result["result"] == "pending"
        assert result["had_signal"] is True
    
    def test_signal_more_than_4_hours_checks_historical(self, tracker):
        """Test that signals more than 4 hours old check historical prices."""
        # Create a signal 5 hours ago
        self._create_old_signal(
            tracker,
            hours_ago=5,
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Mock the historical price API to return winning prices
        mock_historical_data = {
            "success": True,
            "min_price": 50000.0,
            "max_price": 51500.0,  # Target reached!
            "prices": [50000.0, 50500.0, 51000.0, 51500.0, 51200.0],
            "data_points": 5
        }
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            result = tracker.check_previous_signal(
                user_id=123,
                symbol="BTC",
                current_price=48000.0  # Current price is low, but historical was high
            )
        
        assert result is not None
        assert result["result"] == "win"
        assert result["target1_reached"] is True
        assert result["stop_hit"] is False
    
    def test_long_signal_stop_hit_first(self, tracker):
        """Test long signal where stop was hit before target."""
        self._create_old_signal(
            tracker,
            hours_ago=5,
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Mock historical data: price dropped to stop loss
        mock_historical_data = {
            "success": True,
            "min_price": 49600.0,  # Below stop loss
            "max_price": 50200.0,  # Never reached target
            "prices": [50000.0, 49900.0, 49700.0, 49600.0, 49800.0],
            "data_points": 5
        }
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            result = tracker.check_previous_signal(
                user_id=123,
                symbol="BTC",
                current_price=50000.0
            )
        
        assert result is not None
        assert result["result"] == "loss"
        assert result["stop_hit"] is True
        assert result["target1_reached"] is False
    
    def test_long_signal_target_not_reached(self, tracker):
        """Test long signal where neither target nor stop was reached."""
        self._create_old_signal(
            tracker,
            hours_ago=5,
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Mock historical data: price stayed in middle
        mock_historical_data = {
            "success": True,
            "min_price": 49800.0,  # Above stop loss
            "max_price": 50400.0,  # Below target
            "prices": [50000.0, 50100.0, 50200.0, 50300.0, 50400.0],
            "data_points": 5
        }
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            result = tracker.check_previous_signal(
                user_id=123,
                symbol="BTC",
                current_price=50000.0
            )
        
        assert result is not None
        assert result["result"] == "loss"  # Considered loss if target not reached in 4h
        assert result["stop_hit"] is False
        assert result["target1_reached"] is False
    
    def test_short_signal_win(self, tracker):
        """Test short signal that wins."""
        self._create_old_signal(
            tracker,
            hours_ago=5,
            user_id=123,
            symbol="ETH",
            direction="short",
            entry_price=3000.0,
            target1_price=2955.0,
            target2_price=2940.0,
            stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Mock historical data: price dropped to target
        mock_historical_data = {
            "success": True,
            "min_price": 2940.0,  # Reached target2
            "max_price": 3010.0,  # Below stop loss
            "prices": [3000.0, 2980.0, 2960.0, 2940.0, 2950.0],
            "data_points": 5
        }
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            result = tracker.check_previous_signal(
                user_id=123,
                symbol="ETH",
                current_price=3100.0  # Current price is high
            )
        
        assert result is not None
        assert result["result"] == "win"
        assert result["target1_reached"] is True
        assert result["target2_reached"] is True
        assert result["stop_hit"] is False
    
    def test_short_signal_stop_hit(self, tracker):
        """Test short signal where stop was hit."""
        self._create_old_signal(
            tracker,
            hours_ago=5,
            user_id=123,
            symbol="ETH",
            direction="short",
            entry_price=3000.0,
            target1_price=2955.0,
            target2_price=2940.0,
            stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Mock historical data: price went up to stop
        mock_historical_data = {
            "success": True,
            "min_price": 2990.0,
            "max_price": 3025.0,  # Above stop loss
            "prices": [3000.0, 3010.0, 3020.0, 3025.0, 3015.0],
            "data_points": 5
        }
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            result = tracker.check_previous_signal(
                user_id=123,
                symbol="ETH",
                current_price=2900.0
            )
        
        assert result is not None
        assert result["result"] == "loss"
        assert result["stop_hit"] is True
        assert result["target1_reached"] is False
    
    def test_result_caching(self, tracker):
        """Test that once a result is determined, it's cached and not recalculated."""
        self._create_old_signal(
            tracker,
            hours_ago=5,
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        mock_historical_data = {
            "success": True,
            "min_price": 50000.0,
            "max_price": 51500.0,
            "prices": [50000.0, 51000.0, 51500.0],
            "data_points": 3
        }
        
        # First check - should call API
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            result1 = tracker.check_previous_signal(
                user_id=123,
                symbol="BTC",
                current_price=48000.0
            )
            
            assert mock_api.called
            assert result1["result"] == "win"
        
        # Second check - should use cached result, NOT call API
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}  # Different data
            
            result2 = tracker.check_previous_signal(
                user_id=123,
                symbol="BTC",
                current_price=45000.0  # Very different current price
            )
            
            # API should NOT be called because result is cached
            assert not mock_api.called
            assert result2["result"] == "win"  # Same as before
    
    def test_fallback_to_current_price_on_api_failure(self, tracker):
        """Test that system falls back to current price if historical API fails."""
        self._create_old_signal(
            tracker,
            hours_ago=5,
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Mock API to fail
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Current price shows a win
            result = tracker.check_previous_signal(
                user_id=123,
                symbol="BTC",
                current_price=51000.0
            )
        
        assert result is not None
        assert result["result"] == "win"  # Based on current price fallback
    
    def test_sideways_signal_historical(self, tracker):
        """Test sideways signal with historical prices."""
        self._create_old_signal(
            tracker,
            hours_ago=5,
            user_id=123,
            symbol="TON",
            direction="sideways",
            entry_price=5.0,
            target1_price=5.05,
            target2_price=5.10,
            stop_loss_price=4.97,
            probability=55.0
        )
        
        # Mock historical data: stayed in range (+/- 1%)
        mock_historical_data = {
            "success": True,
            "min_price": 4.96,  # Within 1% range (4.95 - 5.05)
            "max_price": 5.04,  # Within range
            "prices": [5.0, 5.02, 4.98, 5.01, 5.04],
            "data_points": 5
        }
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            result = tracker.check_previous_signal(
                user_id=123,
                symbol="TON",
                current_price=6.0  # Current price is out of range
            )
        
        assert result is not None
        assert result["result"] == "win"  # Based on historical staying in range
