import pytest
import os
import csv
import tempfile
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ml.data_collector import MLDataCollector


class TestMLDataCollector:
    
    @pytest.fixture
    def collector(self):
        """Create collector with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MLDataCollector(data_dir=tmpdir)
            yield collector
    
    @pytest.mark.asyncio
    async def test_collect_signal_result_win(self, collector):
        """Test collecting a winning signal."""
        await collector.collect_signal_result(
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            exit_price=51000.0,
            target1_price=50750.0,
            target2_price=51000.0,
            stop_loss_price=49500.0,
            probability=0.75,
            min_price_4h=49800.0,
            max_price_4h=51200.0,
            result="win",
            timestamp="2025-12-26 10:00:00"
        )
        
        stats = collector.get_stats()
        assert stats['total'] == 1
        assert stats['wins'] == 1
        assert stats['losses'] == 0
    
    @pytest.mark.asyncio
    async def test_collect_signal_result_loss(self, collector):
        """Test collecting a losing signal."""
        await collector.collect_signal_result(
            symbol="ETH",
            direction="short",
            entry_price=3000.0,
            exit_price=3100.0,
            target1_price=2955.0,
            target2_price=2940.0,
            stop_loss_price=3030.0,
            probability=0.65,
            min_price_4h=2980.0,
            max_price_4h=3150.0,
            result="loss",
            timestamp="2025-12-26 11:00:00"
        )
        
        stats = collector.get_stats()
        assert stats['total'] == 1
        assert stats['wins'] == 0
        assert stats['losses'] == 1
    
    @pytest.mark.asyncio
    async def test_collect_multiple_signals(self, collector):
        """Test collecting multiple signals."""
        # 3 wins
        for i in range(3):
            await collector.collect_signal_result(
                symbol="BTC",
                direction="long",
                entry_price=50000.0 + i * 100,
                exit_price=51000.0 + i * 100,
                target1_price=50750.0,
                target2_price=51000.0,
                stop_loss_price=49500.0,
                probability=0.70,
                min_price_4h=49800.0,
                max_price_4h=51200.0,
                result="win",
                timestamp=f"2025-12-26 {10+i}:00:00"
            )
        
        # 2 losses
        for i in range(2):
            await collector.collect_signal_result(
                symbol="ETH",
                direction="short",
                entry_price=3000.0,
                exit_price=3100.0,
                target1_price=2955.0,
                target2_price=2940.0,
                stop_loss_price=3030.0,
                probability=0.60,
                min_price_4h=2980.0,
                max_price_4h=3150.0,
                result="loss",
                timestamp=f"2025-12-26 {15+i}:00:00"
            )
        
        stats = collector.get_stats()
        assert stats['total'] == 5
        assert stats['wins'] == 3
        assert stats['losses'] == 2
        assert stats['win_rate'] == 60.0
    
    def test_csv_header_created(self, collector):
        """Test that CSV file is created with correct headers."""
        assert os.path.exists(collector.csv_path)
        
        with open(collector.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
        
        assert 'timestamp' in headers
        assert 'symbol' in headers
        assert 'direction' in headers
        assert 'entry_price' in headers
        assert 'result' in headers
    
    def test_get_stats_empty(self, collector):
        """Test stats on empty data."""
        stats = collector.get_stats()
        assert stats['total'] == 0
        assert stats['wins'] == 0
        assert stats['losses'] == 0
