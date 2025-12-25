"""
Tests for coin statistics functionality.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.signal_tracker import SignalTracker


class TestCoinStatistics:
    """Tests for coin statistics functionality."""
    
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
    
    @pytest.mark.asyncio
    async def test_get_coin_stats_no_signals(self, tracker):
        """Test getting stats when user has no signals for a coin."""
        user_id = 123
        symbol = "BTC"
        
        stats = await tracker.get_coin_stats(user_id, symbol)
        
        assert stats['total'] == 0
        assert stats['wins'] == 0
        assert stats['losses'] == 0
        assert stats['pending'] == 0
        assert stats['win_rate'] == 0.0
        assert stats['total_pl'] == 0.0
        assert stats['best_signal'] == 0.0
        assert stats['worst_signal'] == 0.0
        assert stats['last_signal_time'] is None
    
    @pytest.mark.asyncio
    async def test_get_coin_stats_with_signals(self, tracker):
        """Test getting stats with multiple signals."""
        user_id = 123
        symbol = "BTC"
        
        # Save some test signals
        tracker.save_signal(
            user_id=user_id,
            symbol=symbol,
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=0.75
        )
        
        tracker.save_signal(
            user_id=user_id,
            symbol=symbol,
            direction="short",
            entry_price=51000.0,
            target1_price=50235.0,
            target2_price=49980.0,
            stop_loss_price=51306.0,
            probability=0.68
        )
        
        # Mark first signal as win
        with sqlite3.connect(tracker.db_path) as conn:
            conn.execute(
                'UPDATE signals SET result = ?, exit_price = ? WHERE id = ?',
                ('win', 50750.0, 1)
            )
            conn.commit()
        
        # Mark second signal as loss
        with sqlite3.connect(tracker.db_path) as conn:
            conn.execute(
                'UPDATE signals SET result = ?, exit_price = ? WHERE id = ?',
                ('loss', 51306.0, 2)
            )
            conn.commit()
        
        stats = await tracker.get_coin_stats(user_id, symbol)
        
        assert stats['total'] == 2
        assert stats['wins'] == 1
        assert stats['losses'] == 1
        assert stats['pending'] == 0
        assert stats['win_rate'] == 50.0
        assert stats['total_pl'] > 0  # Should have positive P/L overall
        assert stats['best_signal'] > 0
        assert stats['worst_signal'] < 0
        assert stats['last_signal_time'] is not None
    
    @pytest.mark.asyncio
    async def test_get_coin_stats_pending_signals(self, tracker):
        """Test stats with pending signals."""
        user_id = 123
        symbol = "ETH"
        
        # Save pending signals
        tracker.save_signal(
            user_id=user_id,
            symbol=symbol,
            direction="long",
            entry_price=3000.0,
            target1_price=3045.0,
            target2_price=3060.0,
            stop_loss_price=2982.0,
            probability=0.72
        )
        
        tracker.save_signal(
            user_id=user_id,
            symbol=symbol,
            direction="long",
            entry_price=3050.0,
            target1_price=3095.75,
            target2_price=3111.0,
            stop_loss_price=3031.7,
            probability=0.68
        )
        
        stats = await tracker.get_coin_stats(user_id, symbol)
        
        assert stats['total'] == 2
        assert stats['wins'] == 0
        assert stats['losses'] == 0
        assert stats['pending'] == 2
        assert stats['win_rate'] == 0.0  # No completed signals
        assert stats['total_pl'] == 0.0
    
    @pytest.mark.asyncio
    async def test_get_coin_stats_multiple_users(self, tracker):
        """Test that stats are properly isolated per user."""
        user1_id = 123
        user2_id = 456
        symbol = "BTC"
        
        # User 1 signals
        tracker.save_signal(
            user_id=user1_id,
            symbol=symbol,
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=0.75
        )
        
        # User 2 signals
        tracker.save_signal(
            user_id=user2_id,
            symbol=symbol,
            direction="short",
            entry_price=51000.0,
            target1_price=50235.0,
            target2_price=49980.0,
            stop_loss_price=51306.0,
            probability=0.68
        )
        
        tracker.save_signal(
            user_id=user2_id,
            symbol=symbol,
            direction="long",
            entry_price=50500.0,
            target1_price=51257.5,
            target2_price=51510.0,
            stop_loss_price=50197.0,
            probability=0.70
        )
        
        # Get stats for each user
        user1_stats = await tracker.get_coin_stats(user1_id, symbol)
        user2_stats = await tracker.get_coin_stats(user2_id, symbol)
        
        # User 1 should have 1 signal
        assert user1_stats['total'] == 1
        
        # User 2 should have 2 signals
        assert user2_stats['total'] == 2
    
    @pytest.mark.asyncio
    async def test_get_coin_stats_different_coins(self, tracker):
        """Test that stats are properly isolated per coin."""
        user_id = 123
        
        # BTC signals
        tracker.save_signal(
            user_id=user_id,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=0.75
        )
        
        # ETH signals
        tracker.save_signal(
            user_id=user_id,
            symbol="ETH",
            direction="long",
            entry_price=3000.0,
            target1_price=3045.0,
            target2_price=3060.0,
            stop_loss_price=2982.0,
            probability=0.72
        )
        
        tracker.save_signal(
            user_id=user_id,
            symbol="ETH",
            direction="short",
            entry_price=3100.0,
            target1_price=3053.5,
            target2_price=3038.0,
            stop_loss_price=3118.6,
            probability=0.68
        )
        
        # Get stats for each coin
        btc_stats = await tracker.get_coin_stats(user_id, "BTC")
        eth_stats = await tracker.get_coin_stats(user_id, "ETH")
        
        # BTC should have 1 signal
        assert btc_stats['total'] == 1
        
        # ETH should have 2 signals
        assert eth_stats['total'] == 2
    
    @pytest.mark.asyncio
    async def test_get_coin_stats_sideways_signals(self, tracker):
        """Test stats calculation with sideways signals."""
        user_id = 123
        symbol = "TON"
        
        # Save sideways signal
        tracker.save_signal(
            user_id=user_id,
            symbol=symbol,
            direction="sideways",
            entry_price=5.0,
            target1_price=5.0,
            target2_price=5.0,
            stop_loss_price=5.0,
            probability=0.65
        )
        
        # Mark as win
        with sqlite3.connect(tracker.db_path) as conn:
            conn.execute(
                'UPDATE signals SET result = ?, exit_price = ? WHERE id = ?',
                ('win', 5.0, 1)
            )
            conn.commit()
        
        stats = await tracker.get_coin_stats(user_id, symbol)
        
        assert stats['total'] == 1
        assert stats['wins'] == 1
        assert stats['losses'] == 0
        assert stats['win_rate'] == 100.0
        assert stats['total_pl'] == 0.5  # Sideways win gives 0.5% P/L
