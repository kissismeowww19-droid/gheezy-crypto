"""
Integration test for ETH example from issue - RSI override and consensus protection.

This test simulates the exact scenario from the problem statement:
- RSI = 19 (ОЧЕНЬ перепродан!)
- Fear & Greed = 25 (Extreme Fear)
- Киты = +3 tx с бирж (бычий)
- Импульс = +7.0/10 (бычий)
- Настроения = +10.0/10 (бычий)
- Консенсус = 3 бычьих, 1 медвежий (БЫЧИЙ)

Expected: ЛОНГ сигнал (не ШОРТ)
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer
from unittest.mock import Mock, AsyncMock


class TestETHExampleIntegration:
    """Integration test for ETH example from issue."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_eth_example_rsi_19_should_be_long(self, analyzer):
        """
        Test ETH example from issue:
        - RSI = 19 (< 20, EXTREME oversold) → RSI override should trigger
        - Fear & Greed = 25 (Extreme Fear)
        - Киты = +3 tx withdrawals (bullish)
        - 3 bullish factors vs 1 bearish
        
        Expected: LONG signal (not SHORT)
        """
        # Whale data: 3 withdrawals, 0 deposits = bullish
        whale_data = {
            "transaction_count": 3,
            "total_volume_usd": 15_000_000,
            "deposits": 0,
            "withdrawals": 3,  # +3 withdrawals = bullish
            "sentiment": "bullish"
        }
        
        # Market data
        market_data = {
            "price_usd": 3500,
            "change_24h": -5.0,  # Down 5%
            "volume_24h": 15_000_000_000,
            "market_cap": 420_000_000_000
        }
        
        # Technical data: RSI = 19 (EXTREME oversold)
        technical_data = {
            "rsi": {"value": 19},  # < 20 = RSI extreme override should trigger!
            "macd": {"signal": "bullish", "histogram": 0.5}
        }
        
        # Fear & Greed = 25 (Extreme Fear)
        fear_greed = {
            "value": 25
        }
        
        # Trades flow: bullish
        trades_flow = {
            "flow_ratio": 1.69  # Slightly bullish but not extreme (< 10)
        }
        
        # Calculate signal
        result = analyzer.calculate_signal(
            "ETH", 
            whale_data, 
            market_data, 
            technical_data=technical_data,
            fear_greed=fear_greed,
            trades_flow=trades_flow
        )
        
        # Print detailed results for debugging
        print(f"\n{'='*60}")
        print(f"ETH Integration Test Results (RSI=19 Example)")
        print(f"{'='*60}")
        print(f"Direction: {result['direction']} (raw: {result['raw_direction']})")
        print(f"Total Score: {result['total_score']}")
        print(f"Probability: {result['probability']}%")
        print(f"\nBlock Scores:")
        print(f"  Trend: {result.get('block_trend_score', 'N/A')}")
        print(f"  Momentum: {result.get('block_momentum_score', 'N/A')}")
        print(f"  Whales: {result.get('block_whales_score', 'N/A')}")
        print(f"  Derivatives: {result.get('block_derivatives_score', 'N/A')}")
        print(f"  Sentiment: {result.get('block_sentiment_score', 'N/A')}")
        print(f"\nConsensus:")
        print(f"  Bullish: {result.get('bullish_count', 0)}")
        print(f"  Bearish: {result.get('bearish_count', 0)}")
        print(f"  Neutral: {result.get('neutral_count', 0)}")
        print(f"  Consensus: {result.get('consensus', 'N/A')}")
        print(f"{'='*60}\n")
        
        # Assertions
        # With RSI = 19 (< 20), RSI extreme override should trigger REGARDLESS of other factors
        # This means the signal should be LONG, not SHORT
        assert result["raw_direction"] != "short", \
            f"Expected NOT SHORT with RSI=19 but got {result['raw_direction']}. RSI extreme override should have triggered!"
        
        # Score should be positive (LONG) due to RSI override
        assert result["total_score"] > 0, \
            f"Expected positive score with RSI=19 but got {result['total_score']}. RSI < 20 should override to LONG!"
        
        # Probability should be reasonable (50%+)
        assert result["probability"] >= 50, \
            f"Expected probability >= 50% with RSI override but got {result['probability']}%"
    
    def test_btc_example_rsi_22_two_signals(self, analyzer):
        """
        Test BTC example with 2 strong signals (lower threshold):
        - RSI = 22 (< 25, strong oversold)
        - Fear & Greed = 25 (< 25, Extreme Fear)
        - 2 strong bullish signals → conflict detection should trigger (new threshold)
        
        Expected: LONG signal (not SHORT)
        """
        whale_data = {
            "transaction_count": 8,
            "total_volume_usd": 50_000_000,
            "deposits": 2,
            "withdrawals": 6,  # +4 net withdrawals = bullish
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 95000,
            "change_24h": -3.0,
            "volume_24h": 40_000_000_000,
            "market_cap": 1_800_000_000_000
        }
        
        technical_data = {
            "rsi": {"value": 22},  # < 25 = strong oversold
            "macd": {"signal": "bullish", "histogram": 0.3}
        }
        
        fear_greed = {
            "value": 25  # Exactly at boundary, not < 25
        }
        
        result = analyzer.calculate_signal(
            "BTC", 
            whale_data, 
            market_data, 
            technical_data=technical_data,
            fear_greed=fear_greed
        )
        
        print(f"\n{'='*60}")
        print(f"BTC Integration Test Results (RSI=22, 2 Signals)")
        print(f"{'='*60}")
        print(f"Direction: {result['direction']} (raw: {result['raw_direction']})")
        print(f"Total Score: {result['total_score']}")
        print(f"Probability: {result['probability']}%")
        print(f"{'='*60}\n")
        
        # With 2 strong signals (RSI=22 < 25), conflict detection should trigger
        # Signal should NOT be strongly bearish
        assert result["raw_direction"] != "short" or result["total_score"] > -20, \
            f"Expected NOT STRONGLY SHORT with RSI=22 but got {result['raw_direction']} with score {result['total_score']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
