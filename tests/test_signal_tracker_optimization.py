"""
Tests for Signal Tracker optimizations (LIMIT + index + delays).
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import sys
import os
from unittest.mock import patch, AsyncMock
import asyncio
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.signal_tracker import SignalTracker, TrackedSignal


class TestSignalTrackerOptimization:
    """Tests for SignalTracker optimizations."""
    
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
    
    def test_get_pending_signals_respects_limit(self, tracker):
        """Test that get_pending_signals respects the limit parameter."""
        # Create 30 pending signals
        for i in range(30):
            self._create_old_signal(
                tracker,
                hours_ago=i+1,
                user_id=123,
                symbol="BTC",
                direction="long",
                entry_price=50000.0 + i,
                target1_price=50750.0 + i,
                target2_price=51000.0 + i,
                stop_loss_price=49700.0 + i,
                probability=65.0
            )
        
        # Test default limit (20)
        pending_signals = tracker.get_pending_signals(user_id=123)
        assert len(pending_signals) == 20
        
        # Test custom limit
        pending_signals = tracker.get_pending_signals(user_id=123, limit=10)
        assert len(pending_signals) == 10
        
        # Test limit larger than available
        pending_signals = tracker.get_pending_signals(user_id=123, limit=50)
        assert len(pending_signals) == 30
    
    def test_get_pending_signals_oldest_first(self, tracker):
        """Test that get_pending_signals returns oldest signals first (ORDER BY ASC)."""
        # Create signals at different times
        signal_30h = self._create_old_signal(
            tracker,
            hours_ago=30,
            user_id=123,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        signal_20h = self._create_old_signal(
            tracker,
            hours_ago=20,
            user_id=123,
            symbol="ETH",
            direction="long",
            entry_price=3000.0,
            target1_price=3045.0,
            target2_price=3060.0,
            stop_loss_price=2982.0,
            probability=70.0
        )
        
        signal_10h = self._create_old_signal(
            tracker,
            hours_ago=10,
            user_id=123,
            symbol="SOL",
            direction="long",
            entry_price=100.0,
            target1_price=101.5,
            target2_price=102.0,
            stop_loss_price=99.4,
            probability=60.0
        )
        
        # Get pending signals
        pending_signals = tracker.get_pending_signals(user_id=123, limit=10)
        
        # Should be ordered oldest first
        assert len(pending_signals) == 3
        assert pending_signals[0].symbol == "BTC"  # 30h ago - oldest
        assert pending_signals[1].symbol == "ETH"  # 20h ago
        assert pending_signals[2].symbol == "SOL"  # 10h ago - newest
    
    def test_pending_index_exists(self, tracker):
        """Test that the idx_user_pending index was created."""
        with sqlite3.connect(tracker.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_user_pending'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == 'idx_user_pending'
    
    @pytest.mark.asyncio
    async def test_check_all_pending_signals_with_limit(self, tracker):
        """Test that check_all_pending_signals checks only up to limit=20 signals."""
        # Create 25 old pending signals
        for i in range(25):
            self._create_old_signal(
                tracker,
                hours_ago=i+5,  # All older than 4 hours
                user_id=123,
                symbol=f"COIN{i}",
                direction="long",
                entry_price=100.0 + i,
                target1_price=101.5 + i,
                target2_price=102.0 + i,
                stop_loss_price=99.4 + i,
                probability=65.0
            )
        
        # Mock historical prices API to return wins
        mock_historical_data = {
            "success": True,
            "min_price": 100.0,
            "max_price": 105.0,  # Above all targets
            "prices": [100.0, 102.0, 105.0],
            "data_points": 3
        }
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            results = await tracker.check_all_pending_signals(user_id=123)
        
        # Should check max 20 signals
        assert results['checked_batch'] == 20
        assert results['total_pending'] == 25
        assert results['checked'] == 20  # All 20 should be checked (>4h old)
    
    @pytest.mark.asyncio
    async def test_check_pending_signals_with_delay(self, tracker):
        """Test that delay is applied between signal checks."""
        # Create 3 old pending signals
        for i in range(3):
            self._create_old_signal(
                tracker,
                hours_ago=5,
                user_id=123,
                symbol=f"BTC{i}",
                direction="long",
                entry_price=50000.0,
                target1_price=50750.0,
                target2_price=51000.0,
                stop_loss_price=49700.0,
                probability=65.0
            )
        
        # Mock historical prices API
        mock_historical_data = {
            "success": True,
            "min_price": 50000.0,
            "max_price": 51000.0,
            "prices": [50000.0, 50500.0, 51000.0],
            "data_points": 3
        }
        
        start_time = time.time()
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            results = await tracker.check_all_pending_signals(user_id=123)
        
        elapsed_time = time.time() - start_time
        
        # Should have delays: 3 signals * 0.3s = 0.9s minimum
        # Allow some tolerance for execution time
        assert elapsed_time >= 0.6  # At least 2 delays (0.3s * 2)
        assert results['checked'] == 3
    
    @pytest.mark.asyncio
    async def test_check_pending_signals_for_symbol_with_limit(self, tracker):
        """Test that check_pending_signals_for_symbol uses limit=20."""
        # Create 25 old pending signals for BTC
        for i in range(25):
            self._create_old_signal(
                tracker,
                hours_ago=5+i,
                user_id=123,
                symbol="BTC",
                direction="long",
                entry_price=50000.0 + i,
                target1_price=50750.0 + i,
                target2_price=51000.0 + i,
                stop_loss_price=49700.0 + i,
                probability=65.0
            )
        
        # Mock historical prices API
        mock_historical_data = {
            "success": True,
            "min_price": 50000.0,
            "max_price": 52000.0,
            "prices": [50000.0, 51000.0, 52000.0],
            "data_points": 3
        }
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            results = await tracker.check_pending_signals_for_symbol(
                user_id=123, 
                symbol="BTC"
            )
        
        # Should check max 20 signals
        assert results['checked'] == 20
        assert mock_api.call_count == 20
    
    @pytest.mark.asyncio
    async def test_check_all_pending_returns_correct_counts(self, tracker):
        """Test that check_all_pending_signals returns correct count fields."""
        # Create 15 old signals and 5 new signals (< 4 hours)
        for i in range(15):
            self._create_old_signal(
                tracker,
                hours_ago=5+i,
                user_id=123,
                symbol=f"OLD{i}",
                direction="long",
                entry_price=100.0,
                target1_price=101.5,
                target2_price=102.0,
                stop_loss_price=99.4,
                probability=65.0
            )
        
        for i in range(5):
            self._create_old_signal(
                tracker,
                hours_ago=2,  # Less than 4 hours
                user_id=123,
                symbol=f"NEW{i}",
                direction="long",
                entry_price=100.0,
                target1_price=101.5,
                target2_price=102.0,
                stop_loss_price=99.4,
                probability=65.0
            )
        
        # Mock historical prices API
        mock_historical_data = {
            "success": True,
            "min_price": 100.0,
            "max_price": 102.0,
            "prices": [100.0, 101.0, 102.0],
            "data_points": 3
        }
        
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_historical_data
            
            results = await tracker.check_all_pending_signals(user_id=123)
        
        # Check return structure
        assert 'total_pending' in results
        assert 'checked_batch' in results
        assert 'checked' in results
        assert 'wins' in results
        assert 'losses' in results
        assert 'still_pending' in results
        
        # Total pending should be 20 (all signals)
        assert results['total_pending'] == 20
        # Checked batch should be 20 (limit)
        assert results['checked_batch'] == 20
        # Of the 20 checked, 15 are old (>4h) and 5 are new (<4h)
        assert results['checked'] == 15  # Only old ones get checked
        assert results['still_pending'] == 5  # New ones stay pending
