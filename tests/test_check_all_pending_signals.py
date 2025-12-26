"""
Tests for checking all pending signals functionality.
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


class TestCheckAllPendingSignals:
    """Tests for check_all_pending_signals and check_pending_signals_for_symbol methods."""
    
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
    
    def test_get_pending_signals_all(self, tracker):
        """Test getting all pending signals for a user."""
        # Create some signals
        self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        self._create_old_signal(
            tracker, hours_ago=6,
            user_id=123, symbol="ETH", direction="short",
            entry_price=3000.0, target1_price=2955.0,
            target2_price=2940.0, stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Get all pending signals
        pending = tracker.get_pending_signals(user_id=123)
        
        assert len(pending) == 2
        assert all(s.result == 'pending' for s in pending)
        assert any(s.symbol == 'BTC' for s in pending)
        assert any(s.symbol == 'ETH' for s in pending)
    
    def test_get_pending_signals_filtered_by_symbol(self, tracker):
        """Test getting pending signals filtered by symbol."""
        # Create signals for different symbols
        self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        self._create_old_signal(
            tracker, hours_ago=6,
            user_id=123, symbol="ETH", direction="short",
            entry_price=3000.0, target1_price=2955.0,
            target2_price=2940.0, stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Get only BTC signals
        btc_pending = tracker.get_pending_signals(user_id=123, symbol="BTC")
        
        assert len(btc_pending) == 1
        assert btc_pending[0].symbol == "BTC"
        assert btc_pending[0].result == 'pending'
    
    def test_get_pending_signals_excludes_completed(self, tracker):
        """Test that get_pending_signals excludes completed signals."""
        # Create a pending signal
        signal1 = self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Create a completed signal
        signal2 = self._create_old_signal(
            tracker, hours_ago=6,
            user_id=123, symbol="ETH", direction="short",
            entry_price=3000.0, target1_price=2955.0,
            target2_price=2940.0, stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Mark the ETH signal as completed
        with sqlite3.connect(tracker.db_path) as conn:
            conn.execute(
                "UPDATE signals SET result = 'win' WHERE id = ?",
                (signal2.id,)
            )
            conn.commit()
        
        # Get pending signals
        pending = tracker.get_pending_signals(user_id=123)
        
        assert len(pending) == 1
        assert pending[0].symbol == "BTC"
    
    @pytest.mark.asyncio
    async def test_check_all_pending_signals_wins(self, tracker):
        """Test checking all pending signals with winning results."""
        # Create old signals (>4 hours)
        self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        self._create_old_signal(
            tracker, hours_ago=6,
            user_id=123, symbol="ETH", direction="short",
            entry_price=3000.0, target1_price=2955.0,
            target2_price=2940.0, stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Mock the historical price API to return winning prices
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_hist:
            # BTC signal wins (price went up)
            mock_hist.side_effect = [
                {
                    "success": True,
                    "min_price": 50000.0,
                    "max_price": 51500.0,  # Target reached
                    "prices": [50000.0, 50500.0, 51500.0]
                },
                # ETH signal wins (price went down for short)
                {
                    "success": True,
                    "min_price": 2900.0,  # Target reached for short
                    "max_price": 3000.0,
                    "prices": [3000.0, 2950.0, 2900.0]
                }
            ]
            
            results = await tracker.check_all_pending_signals(user_id=123)
        
        assert results['checked'] == 2
        assert results['wins'] == 2
        assert results['losses'] == 0
        assert results['still_pending'] == 0
    
    @pytest.mark.asyncio
    async def test_check_all_pending_signals_losses(self, tracker):
        """Test checking all pending signals with losing results."""
        # Create old signals (>4 hours)
        self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Mock the historical price API to return losing prices
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_hist:
            # BTC signal loses (stop loss hit)
            mock_hist.return_value = {
                "success": True,
                "min_price": 49500.0,  # Below stop loss
                "max_price": 50500.0,
                "prices": [50000.0, 49700.0, 49500.0]
            }
            
            results = await tracker.check_all_pending_signals(user_id=123)
        
        assert results['checked'] == 1
        assert results['wins'] == 0
        assert results['losses'] == 1
        assert results['still_pending'] == 0
    
    @pytest.mark.asyncio
    async def test_check_all_pending_signals_mixed_results(self, tracker):
        """Test checking pending signals with mixed win/loss results."""
        # Create multiple old signals
        self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        self._create_old_signal(
            tracker, hours_ago=6,
            user_id=123, symbol="ETH", direction="short",
            entry_price=3000.0, target1_price=2955.0,
            target2_price=2940.0, stop_loss_price=3018.0,
            probability=70.0
        )
        
        self._create_old_signal(
            tracker, hours_ago=7,
            user_id=123, symbol="SOL", direction="long",
            entry_price=100.0, target1_price=101.5,
            target2_price=102.0, stop_loss_price=99.4,
            probability=60.0
        )
        
        # Mock the historical price API with mixed results
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_hist:
            mock_hist.side_effect = [
                # BTC wins
                {
                    "success": True,
                    "min_price": 50000.0,
                    "max_price": 51500.0,
                    "prices": [50000.0, 50500.0, 51500.0]
                },
                # ETH loses
                {
                    "success": True,
                    "min_price": 2950.0,
                    "max_price": 3050.0,  # Stop loss hit for short
                    "prices": [3000.0, 3020.0, 3050.0]
                },
                # SOL wins
                {
                    "success": True,
                    "min_price": 100.0,
                    "max_price": 102.5,
                    "prices": [100.0, 101.0, 102.5]
                }
            ]
            
            results = await tracker.check_all_pending_signals(user_id=123)
        
        assert results['checked'] == 3
        assert results['wins'] == 2
        assert results['losses'] == 1
        assert results['still_pending'] == 0
    
    @pytest.mark.asyncio
    async def test_check_all_pending_signals_skips_recent(self, tracker):
        """Test that signals less than 4 hours old are not checked."""
        # Create one old signal and one recent signal
        self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        self._create_old_signal(
            tracker, hours_ago=2,  # Less than 4 hours
            user_id=123, symbol="ETH", direction="short",
            entry_price=3000.0, target1_price=2955.0,
            target2_price=2940.0, stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Mock the historical price API
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_hist:
            mock_hist.return_value = {
                "success": True,
                "min_price": 50000.0,
                "max_price": 51500.0,
                "prices": [50000.0, 50500.0, 51500.0]
            }
            
            results = await tracker.check_all_pending_signals(user_id=123)
        
        # Only the old signal should be checked
        assert results['checked'] == 1
        assert results['still_pending'] == 1
        
        # The API should only be called once (for BTC, not ETH)
        assert mock_hist.call_count == 1
    
    @pytest.mark.asyncio
    async def test_check_pending_signals_for_symbol(self, tracker):
        """Test checking pending signals for a specific symbol."""
        # Create signals for multiple symbols
        self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        self._create_old_signal(
            tracker, hours_ago=6,
            user_id=123, symbol="ETH", direction="short",
            entry_price=3000.0, target1_price=2955.0,
            target2_price=2940.0, stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Mock the historical price API
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_hist:
            mock_hist.return_value = {
                "success": True,
                "min_price": 50000.0,
                "max_price": 51500.0,
                "prices": [50000.0, 50500.0, 51500.0]
            }
            
            results = await tracker.check_pending_signals_for_symbol(user_id=123, symbol="BTC")
        
        # Only BTC signal should be checked
        assert results['checked'] == 1
        assert results['wins'] == 1
        assert results['losses'] == 0
        assert results['still_pending'] == 0
        
        # API should only be called once
        assert mock_hist.call_count == 1
    
    @pytest.mark.asyncio
    async def test_check_all_pending_signals_handles_api_failure(self, tracker):
        """Test that API failures are handled gracefully."""
        # Create old signal
        self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Mock the historical price API to fail
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_hist:
            mock_hist.return_value = {
                "success": False,
                "error": "API error"
            }
            
            results = await tracker.check_all_pending_signals(user_id=123)
        
        # Signal should remain pending due to API failure
        assert results['checked'] == 0
        assert results['still_pending'] == 1
    
    @pytest.mark.asyncio
    async def test_check_all_pending_signals_different_users(self, tracker):
        """Test that check_all_pending_signals only checks signals for the specified user."""
        # Create signals for different users
        self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="long",
            entry_price=50000.0, target1_price=50750.0,
            target2_price=51000.0, stop_loss_price=49700.0,
            probability=65.0
        )
        
        self._create_old_signal(
            tracker, hours_ago=6,
            user_id=456, symbol="ETH", direction="short",
            entry_price=3000.0, target1_price=2955.0,
            target2_price=2940.0, stop_loss_price=3018.0,
            probability=70.0
        )
        
        # Mock the historical price API
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_hist:
            mock_hist.return_value = {
                "success": True,
                "min_price": 50000.0,
                "max_price": 51500.0,
                "prices": [50000.0, 50500.0, 51500.0]
            }
            
            results = await tracker.check_all_pending_signals(user_id=123)
        
        # Only user 123's signal should be checked
        assert results['checked'] == 1
        assert mock_hist.call_count == 1
    
    @pytest.mark.asyncio
    async def test_evaluate_signal_result_sideways(self, tracker):
        """Test evaluation of sideways signals."""
        # Create a sideways signal
        signal = self._create_old_signal(
            tracker, hours_ago=5,
            user_id=123, symbol="BTC", direction="sideways",
            entry_price=50000.0, target1_price=50000.0,
            target2_price=50000.0, stop_loss_price=50000.0,
            probability=65.0
        )
        
        # Test winning sideways (price stayed in range)
        pending_signals = tracker.get_pending_signals(user_id=123)
        result = tracker._evaluate_signal_result(
            pending_signals[0],
            max_price=50450.0,  # Within +/- 1% range
            min_price=49550.0
        )
        
        assert result == 'win'
        
        # Create another sideways signal
        signal2 = self._create_old_signal(
            tracker, hours_ago=5,
            user_id=456, symbol="ETH", direction="sideways",
            entry_price=3000.0, target1_price=3000.0,
            target2_price=3000.0, stop_loss_price=3000.0,
            probability=60.0
        )
        
        # Test losing sideways (price moved too much)
        pending_signals2 = tracker.get_pending_signals(user_id=456)
        result2 = tracker._evaluate_signal_result(
            pending_signals2[0],
            max_price=3050.0,  # Outside +/- 1% range
            min_price=2900.0
        )
        
        assert result2 == 'loss'
