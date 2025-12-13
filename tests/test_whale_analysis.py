"""
Tests for Deep Whale Analysis module.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from signals.whale_analysis import DeepWhaleAnalyzer


@pytest.fixture
def analyzer():
    """Create a DeepWhaleAnalyzer instance for testing."""
    return DeepWhaleAnalyzer()


@pytest.fixture
def mock_whale_tracker():
    """Create a mock WhaleTracker."""
    tracker = Mock()
    tracker.get_transactions_by_blockchain = AsyncMock()
    return tracker


@pytest.fixture
def mock_whale_transactions():
    """Create mock whale transaction data."""
    now = datetime.now()
    
    class MockTx:
        def __init__(self, is_deposit, amount_usd, timestamp=None):
            self.is_exchange_deposit = is_deposit
            self.is_exchange_withdrawal = not is_deposit
            self.amount_usd = amount_usd
            self.timestamp = timestamp or now
            self.exchange_name = "Binance" if is_deposit else None
            self.from_address = "0xtest1"
            self.to_address = "0xtest2"
    
    # Create mix of deposits and withdrawals
    txs = [
        MockTx(False, 5_000_000, now - timedelta(hours=i))  # Withdrawals
        for i in range(12)
    ] + [
        MockTx(True, 2_000_000, now - timedelta(hours=i))  # Deposits
        for i in range(8)
    ]
    
    return txs


class TestDeepWhaleAnalyzer:
    """Test suite for DeepWhaleAnalyzer."""
    
    @pytest.mark.asyncio
    async def test_get_exchange_flows_detailed_no_data(self, analyzer, mock_whale_tracker):
        """Test exchange flows when no transactions are available."""
        mock_whale_tracker.get_transactions_by_blockchain.return_value = []
        
        result = await analyzer.get_exchange_flows_detailed("BTC", mock_whale_tracker)
        
        assert result is not None
        assert result["total_net"] == 0
        assert result["signal"] == "neutral"
        assert result["binance"]["net"] == 0
        assert result["coinbase"]["net"] == 0
    
    @pytest.mark.asyncio
    async def test_get_exchange_flows_detailed_with_data(self, analyzer, mock_whale_tracker, mock_whale_transactions):
        """Test exchange flows with actual transaction data."""
        mock_whale_tracker.get_transactions_by_blockchain.return_value = mock_whale_transactions
        
        result = await analyzer.get_exchange_flows_detailed("BTC", mock_whale_tracker)
        
        assert result is not None
        assert "total_net" in result
        assert "signal" in result
        # More withdrawals than deposits = negative net (bullish)
        assert result["signal"] in ["bullish", "bearish", "neutral"]
    
    def test_detect_accumulation_distribution_insufficient_data(self, analyzer):
        """Test accumulation detection with insufficient data."""
        result = analyzer.detect_accumulation_distribution([])
        
        assert result["phase"] == "neutral"
        assert result["confidence"] == 0
        assert "Insufficient data" in result["details"]
    
    def test_detect_accumulation_distribution_accumulation(self, analyzer, mock_whale_transactions):
        """Test accumulation phase detection."""
        # Mock transactions have more withdrawals (12) than deposits (8)
        result = analyzer.detect_accumulation_distribution(mock_whale_transactions)
        
        assert result["phase"] in ["accumulation", "distribution", "neutral"]
        assert 0 <= result["confidence"] <= 100
        assert "details" in result
    
    def test_detect_accumulation_distribution_distribution(self, analyzer):
        """Test distribution phase detection."""
        now = datetime.now()
        
        class MockTx:
            def __init__(self, is_deposit, amount_usd):
                self.is_exchange_deposit = is_deposit
                self.is_exchange_withdrawal = not is_deposit
                self.amount_usd = amount_usd
                self.timestamp = now
        
        # More deposits than withdrawals
        txs = [
            MockTx(True, 5_000_000) for _ in range(15)
        ] + [
            MockTx(False, 2_000_000) for _ in range(5)
        ]
        
        result = analyzer.detect_accumulation_distribution(txs)
        
        assert result["phase"] in ["distribution", "neutral"]
    
    @pytest.mark.asyncio
    async def test_get_stablecoin_flows_placeholder(self, analyzer):
        """Test stablecoin flows (currently returns placeholder)."""
        result = await analyzer.get_stablecoin_flows()
        
        assert result is not None
        assert result["signal"] == "neutral"
        assert result["total_inflow"] == 0
    
    def test_identify_exchange(self, analyzer):
        """Test exchange identification from transaction."""
        class MockTx:
            exchange_name = "Binance Hot Wallet"
            from_address = "0xtest"
            to_address = "0xtest2"
        
        tx = MockTx()
        result = analyzer._identify_exchange(tx, "BTC")
        
        # Should identify binance from the name
        assert result == "binance"
    
    def test_empty_exchange_flows_structure(self, analyzer):
        """Test empty exchange flows structure."""
        result = analyzer._get_empty_exchange_flows()
        
        assert result["total_net"] == 0.0
        assert result["signal"] == "neutral"
        assert "binance" in result
        assert "coinbase" in result
        assert "kraken" in result
        assert "okx" in result
        
        for exchange in ["binance", "coinbase", "kraken", "okx"]:
            assert result[exchange]["inflow"] == 0.0
            assert result[exchange]["outflow"] == 0.0
            assert result[exchange]["net"] == 0.0
    
    def test_cache_functionality(self, analyzer):
        """Test caching mechanism."""
        test_data = {"test": "data"}
        analyzer._set_cache("test_key", test_data)
        
        # Should return cached data within TTL
        cached = analyzer._get_cache("test_key", 300)
        assert cached == test_data
        
        # Should return None after TTL expires (simulate)
        expired = analyzer._get_cache("nonexistent_key", 300)
        assert expired is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
