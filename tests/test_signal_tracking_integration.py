"""
Integration test for signal tracking workflow.
"""

import pytest
import asyncio
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.signal_tracker import SignalTracker
from signals.ai_signals import AISignalAnalyzer


class TestSignalTrackingIntegration:
    """Integration tests for signal tracking workflow."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        return tracker
    
    @pytest.fixture
    def signal_tracker(self, tmp_path):
        """Create a signal tracker with temporary database."""
        db_path = tmp_path / "test_signals.db"
        return SignalTracker(db_path=str(db_path))
    
    @pytest.fixture
    def ai_analyzer(self, mock_whale_tracker):
        """Create an AI signal analyzer."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def _make_signal_old(self, tracker, signal_id, hours_ago=5):
        """Helper to make a signal appear older than it is."""
        old_timestamp = datetime.now() - timedelta(hours=hours_ago)
        with sqlite3.connect(tracker.db_path) as conn:
            conn.execute(
                'UPDATE signals SET timestamp = ? WHERE id = ?',
                (old_timestamp.isoformat(), signal_id)
            )
            conn.commit()
    
    def test_signal_workflow_long_win(self, signal_tracker):
        """Test complete workflow: save signal, check result (win)."""
        user_id = 12345
        symbol = "BTC"
        
        # Step 1: Save a long signal
        signal = signal_tracker.save_signal(
            user_id=user_id,
            symbol=symbol,
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        assert signal.result == "pending"
        
        # Make signal old enough to check
        self._make_signal_old(signal_tracker, signal.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Step 2: Check signal with winning price
            result = signal_tracker.check_previous_signal(
                user_id=user_id,
                symbol=symbol,
                current_price=50800.0  # Above target1
            )
        
        assert result is not None
        assert result["had_signal"] is True
        assert result["result"] == "win"
        assert result["target1_reached"] is True
        assert result["pnl_percent"] > 0
    
    def test_signal_workflow_short_loss(self, signal_tracker):
        """Test complete workflow: save signal, check result (loss)."""
        user_id = 67890
        symbol = "ETH"
        
        # Step 1: Save a short signal
        signal = signal_tracker.save_signal(
            user_id=user_id,
            symbol=symbol,
            direction="short",
            entry_price=3000.0,
            target1_price=2955.0,
            target2_price=2940.0,
            stop_loss_price=3018.0,
            probability=70.0
        )
        
        assert signal.result == "pending"
        
        # Make signal old enough to check
        self._make_signal_old(signal_tracker, signal.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Step 2: Check signal with losing price
            result = signal_tracker.check_previous_signal(
                user_id=user_id,
                symbol=symbol,
                current_price=3050.0  # Above stop loss
            )
        
        assert result is not None
        assert result["had_signal"] is True
        assert result["result"] == "loss"
        assert result["stop_hit"] is True
        assert result["pnl_percent"] < 0
    
    def test_multiple_signals_per_user(self, signal_tracker):
        """Test that user can have multiple signals for different symbols."""
        user_id = 11111
        
        # Save BTC signal
        btc_signal = signal_tracker.save_signal(
            user_id=user_id,
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49700.0,
            probability=65.0
        )
        
        # Save ETH signal
        eth_signal = signal_tracker.save_signal(
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
        self._make_signal_old(signal_tracker, btc_signal.id, hours_ago=5)
        self._make_signal_old(signal_tracker, eth_signal.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            # Check both signals
            btc_result = signal_tracker.check_previous_signal(user_id, "BTC", 50800.0)
            eth_result = signal_tracker.check_previous_signal(user_id, "ETH", 2900.0)
        
        assert btc_result["direction"] == "long"
        assert btc_result["result"] == "win"
        
        assert eth_result["direction"] == "short"
        assert eth_result["result"] == "win"
        
        # Check stats
        stats = signal_tracker.get_user_stats(user_id)
        assert stats["total_signals"] == 2
        assert stats["wins"] == 2
        assert stats["losses"] == 0
        assert stats["win_rate"] == 100.0
    
    def test_stats_calculation_accuracy(self, signal_tracker):
        """Test that statistics are calculated correctly."""
        user_id = 22222
        
        # Create 5 signals: 3 wins, 2 losses
        # Win 1 - BTC
        s1 = signal_tracker.save_signal(user_id, "BTC", "long", 50000, 50750, 51000, 49700, 65)
        self._make_signal_old(signal_tracker, s1.id, hours_ago=5)
        
        # Win 2 - ETH
        s2 = signal_tracker.save_signal(user_id, "ETH", "short", 3000, 2955, 2940, 3018, 70)
        self._make_signal_old(signal_tracker, s2.id, hours_ago=5)
        
        # Win 3 - TON
        s3 = signal_tracker.save_signal(user_id, "TON", "long", 5.0, 5.075, 5.1, 4.97, 60)
        self._make_signal_old(signal_tracker, s3.id, hours_ago=5)
        
        # Loss 1 - SOL
        s4 = signal_tracker.save_signal(user_id, "SOL", "long", 100, 101.5, 102, 99.4, 55)
        self._make_signal_old(signal_tracker, s4.id, hours_ago=5)
        
        # Loss 2 - XRP
        s5 = signal_tracker.save_signal(user_id, "XRP", "short", 1.0, 0.985, 0.98, 1.006, 58)
        self._make_signal_old(signal_tracker, s5.id, hours_ago=5)
        
        # Mock API to fail, forcing fallback to current price
        with patch('api_manager.get_historical_prices', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"success": False}
            
            signal_tracker.check_previous_signal(user_id, "BTC", 50800)  # Win
            signal_tracker.check_previous_signal(user_id, "ETH", 2950)  # Win
            signal_tracker.check_previous_signal(user_id, "TON", 5.08)  # Win
            signal_tracker.check_previous_signal(user_id, "SOL", 99.0)  # Loss
            signal_tracker.check_previous_signal(user_id, "XRP", 1.01)  # Loss
        
        # Get stats
        stats = signal_tracker.get_user_stats(user_id)
        
        assert stats["total_signals"] == 5
        assert stats["wins"] == 3
        assert stats["losses"] == 2
        assert stats["pending"] == 0
        assert stats["win_rate"] == 60.0  # 3/5 = 60%
        assert stats["total_pnl"] != 0.0  # Should have some P&L
