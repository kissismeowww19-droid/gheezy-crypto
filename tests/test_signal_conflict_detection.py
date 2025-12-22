"""
Tests for signal conflict detection and extreme signal handling.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer
from unittest.mock import Mock, AsyncMock


class TestSignalConflictDetection:
    """Tests for conflict detection and extreme signal enhancements."""
    
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
    
    def test_extreme_rsi_oversold_btc_example(self, analyzer):
        """
        Test BTC example from issue:
        RSI = 28 (перепродан) → должен быть ЛОНГ
        Fear & Greed = 25 (Extreme Fear) → должен быть ЛОНГ
        Buy/Sell ratio = 122:1 → должен быть ЛОНГ
        Ожидается: ЛОНГ с положительным score
        """
        whale_data = {
            "transaction_count": 5,
            "total_volume_usd": 10_000_000,
            "deposits": 1,
            "withdrawals": 4,
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 95000,
            "change_24h": -2.0,
            "volume_24h": 30_000_000_000,
            "market_cap": 1_800_000_000_000
        }
        
        technical_data = {
            "rsi": {"value": 28},
            "macd": {"signal": "bullish", "histogram": 0.5}
        }
        
        fear_greed = {
            "value": 25
        }
        
        trades_flow = {
            "flow_ratio": 122.0  # 122:1 Buy/Sell ratio
        }
        
        result = analyzer.calculate_signal(
            "BTC", 
            whale_data, 
            market_data, 
            technical_data=technical_data,
            fear_greed=fear_greed,
            trades_flow=trades_flow
        )
        
        # Should be LONG direction
        assert result["raw_direction"] == "long", f"Expected LONG but got {result['raw_direction']}"
        # Score should be positive
        assert result["total_score"] > 0, f"Expected positive score but got {result['total_score']}"
        # Check individual scores are contributing positively
        print(f"BTC Test Results:")
        print(f"  Direction: {result['direction']} (raw: {result['raw_direction']})")
        print(f"  Total Score: {result['total_score']}")
        print(f"  Momentum Score: {result.get('momentum_score', 'N/A')}")
        print(f"  Sentiment Score: {result.get('sentiment_score', 'N/A')}")
        print(f"  Trades Flow Score: {result.get('trades_flow_score', 'N/A')}")
    
    def test_extreme_rsi_oversold_eth_example(self, analyzer):
        """
        Test ETH example from issue:
        RSI = 25 (перепродан) → должен быть ЛОНГ
        Киты = +4 tx с бирж → должен быть ЛОНГ
        Консенсус = БЫЧИЙ
        Ожидается: ЛОНГ с положительным score (или хотя бы не SHORT)
        """
        whale_data = {
            "transaction_count": 10,
            "total_volume_usd": 20_000_000,
            "deposits": 1,
            "withdrawals": 9,  # 9 выводов с бирж = бычий
            "sentiment": "bullish"
        }
        
        market_data = {
            "price_usd": 3500,
            "change_24h": -1.5,
            "volume_24h": 15_000_000_000,
            "market_cap": 420_000_000_000
        }
        
        technical_data = {
            "rsi": {"value": 25},  # Очень перепродан
            "macd": {"signal": "bullish", "histogram": 0.3}
        }
        
        exchange_flows = {
            "net_flow_usd": -5_000_000  # Отток с бирж = бычий
        }
        
        fear_greed = {
            "value": 30  # Fear
        }
        
        result = analyzer.calculate_signal(
            "ETH", 
            whale_data, 
            market_data, 
            technical_data=technical_data,
            exchange_flows=exchange_flows,
            fear_greed=fear_greed
        )
        
        # With strong bullish signals, should NOT be SHORT
        assert result["raw_direction"] != "short", f"Expected NOT SHORT but got {result['raw_direction']}"
        # Score should be positive (bullish consensus)
        assert result["total_score"] > 0, f"Expected positive score but got {result['total_score']}"
        
        print(f"\nETH Test Results:")
        print(f"  Direction: {result['direction']} (raw: {result['raw_direction']})")
        print(f"  Total Score: {result['total_score']}")
        print(f"  Whale Score: {result.get('whale_score', 'N/A')}")
        print(f"  Momentum Score: {result.get('momentum_score', 'N/A')}")
    
    def test_detect_signal_conflicts_bullish_override(self, analyzer):
        """Test conflict detection with strong bullish signals overriding negative score."""
        adjusted_score, note = analyzer._detect_signal_conflicts(
            rsi=23.0,  # Strong oversold
            fear_greed=20,  # Extreme fear
            trades_flow_ratio=15.0,  # Very high buy ratio
            macd_signal="bullish",
            total_score=-30.0,  # Contradictory negative score
            bullish_count=5,
            bearish_count=15,
            neutral_count=2
        )
        
        # Should override to positive
        assert adjusted_score > 0, f"Expected positive adjusted score but got {adjusted_score}"
        assert "конфликт" in note.lower() or "conflict" in note.lower()
        print(f"\nConflict Detection Test (Bullish Override):")
        print(f"  Original Score: -30.0")
        print(f"  Adjusted Score: {adjusted_score}")
        print(f"  Note: {note}")
    
    def test_detect_signal_conflicts_two_signals_override(self, analyzer):
        """Test conflict detection with exactly 2 strong bullish signals (new threshold)."""
        adjusted_score, note = analyzer._detect_signal_conflicts(
            rsi=22.0,  # Strong oversold (< 25)
            fear_greed=24,  # Extreme fear (< 25) 
            trades_flow_ratio=1.5,  # NOT strong (< 10)
            macd_signal="neutral",  # NOT strong
            total_score=-35.0,  # Contradictory negative score
            bullish_count=3,
            bearish_count=11,
            neutral_count=8
        )
        
        # With 2 strong signals (RSI + FG), should override to positive
        assert adjusted_score > 0, f"Expected positive adjusted score with 2 signals but got {adjusted_score}"
        assert "конфликт" in note.lower() or "conflict" in note.lower()
        print(f"\nConflict Detection Test (2 Signals Override - New Threshold):")
        print(f"  Original Score: -35.0")
        print(f"  Adjusted Score: {adjusted_score}")
        print(f"  Note: {note}")
    
    def test_rsi_extreme_override_under_20(self, analyzer):
        """Test RSI < 20 extreme override (highest priority)."""
        adjusted_score, note = analyzer._detect_signal_conflicts(
            rsi=19.0,  # EXTREME oversold (< 20) - should override everything
            fear_greed=50,  # Neutral
            trades_flow_ratio=0.5,  # Bearish
            macd_signal="bearish",  # Bearish
            total_score=-65.0,  # Strong bearish score
            bullish_count=2,
            bearish_count=18,
            neutral_count=2
        )
        
        # RSI < 20 should ALWAYS override to positive, regardless of other factors
        assert adjusted_score > 0, f"Expected positive score with RSI=19 but got {adjusted_score}"
        assert "RSI" in note and "Override" in note
        print(f"\nRSI Extreme Override Test (RSI < 20):")
        print(f"  RSI: 19.0")
        print(f"  Original Score: -65.0")
        print(f"  Adjusted Score: {adjusted_score}")
        print(f"  Note: {note}")
    
    def test_rsi_extreme_override_over_80(self, analyzer):
        """Test RSI > 80 extreme override (highest priority)."""
        adjusted_score, note = analyzer._detect_signal_conflicts(
            rsi=82.0,  # EXTREME overbought (> 80) - should override everything
            fear_greed=50,  # Neutral
            trades_flow_ratio=2.0,  # Bullish
            macd_signal="bullish",  # Bullish
            total_score=70.0,  # Strong bullish score
            bullish_count=18,
            bearish_count=2,
            neutral_count=2
        )
        
        # RSI > 80 should ALWAYS override to negative, regardless of other factors
        assert adjusted_score < 0, f"Expected negative score with RSI=82 but got {adjusted_score}"
        assert "RSI" in note and "Override" in note
        print(f"\nRSI Extreme Override Test (RSI > 80):")
        print(f"  RSI: 82.0")
        print(f"  Original Score: 70.0")
        print(f"  Adjusted Score: {adjusted_score}")
        print(f"  Note: {note}")
    
    def test_detect_signal_conflicts_bearish_override(self, analyzer):
        """Test conflict detection with strong bearish signals overriding positive score."""
        adjusted_score, note = analyzer._detect_signal_conflicts(
            rsi=78.0,  # Strong overbought
            fear_greed=80,  # Extreme greed
            trades_flow_ratio=0.05,  # Very high sell ratio
            macd_signal="bearish",
            total_score=25.0,  # Contradictory positive score
            bullish_count=15,
            bearish_count=5,
            neutral_count=2
        )
        
        # Should override to negative
        assert adjusted_score < 0, f"Expected negative adjusted score but got {adjusted_score}"
        assert "конфликт" in note.lower() or "conflict" in note.lower()
        print(f"\nConflict Detection Test (Bearish Override):")
        print(f"  Original Score: 25.0")
        print(f"  Adjusted Score: {adjusted_score}")
        print(f"  Note: {note}")
    
    def test_detect_signal_conflicts_high_neutral(self, analyzer):
        """Test conflict detection with many neutral factors."""
        adjusted_score, note = analyzer._detect_signal_conflicts(
            rsi=50.0,  # Neutral
            fear_greed=50,  # Neutral
            trades_flow_ratio=1.0,  # Neutral
            macd_signal="neutral",
            total_score=15.0,
            bullish_count=5,
            bearish_count=5,
            neutral_count=12  # > 50% neutral
        )
        
        # Should smooth towards zero
        assert abs(adjusted_score) < abs(15.0), f"Expected smoothed score but got {adjusted_score}"
        print(f"\nConflict Detection Test (High Neutral):")
        print(f"  Original Score: 15.0")
        print(f"  Adjusted Score: {adjusted_score}")
        print(f"  Note: {note}")
    
    def test_calc_momentum_score_extreme_oversold(self, analyzer):
        """Test enhanced RSI scoring for extreme oversold."""
        # RSI < 20 should give +20 score
        score = analyzer._calc_momentum_score(
            rsi=18.0,
            rsi_5m=None,
            rsi_15m=None,
            price_momentum_10min=None
        )
        
        # With only RSI factor, max clamped score is 10, but internally it should be high
        # The _clamp_block_score normalizes it
        assert score > 0, f"Expected positive score for RSI=18 but got {score}"
        print(f"\nMomentum Score Test (Extreme Oversold):")
        print(f"  RSI: 18.0")
        print(f"  Score: {score}")
    
    def test_calc_momentum_score_extreme_overbought(self, analyzer):
        """Test enhanced RSI scoring for extreme overbought."""
        # RSI > 80 should give -20 score
        score = analyzer._calc_momentum_score(
            rsi=82.0,
            rsi_5m=None,
            rsi_15m=None,
            price_momentum_10min=None
        )
        
        assert score < 0, f"Expected negative score for RSI=82 but got {score}"
        print(f"\nMomentum Score Test (Extreme Overbought):")
        print(f"  RSI: 82.0")
        print(f"  Score: {score}")
    
    def test_calc_sentiment_score_extreme_fear(self, analyzer):
        """Test enhanced Fear & Greed scoring for extreme fear."""
        score = analyzer._calc_sentiment_score(
            fear_greed=12,  # < 15 = EXTREME Fear
            tradingview_rating=None
        )
        
        assert score > 0, f"Expected positive score for Fear=12 but got {score}"
        print(f"\nSentiment Score Test (Extreme Fear):")
        print(f"  Fear & Greed: 12")
        print(f"  Score: {score}")
    
    def test_calc_sentiment_score_extreme_greed(self, analyzer):
        """Test enhanced Fear & Greed scoring for extreme greed."""
        score = analyzer._calc_sentiment_score(
            fear_greed=88,  # > 85 = EXTREME Greed
            tradingview_rating=None
        )
        
        assert score < 0, f"Expected negative score for Greed=88 but got {score}"
        print(f"\nSentiment Score Test (Extreme Greed):")
        print(f"  Fear & Greed: 88")
        print(f"  Score: {score}")
    
    def test_calculate_trades_flow_score_extreme_buy(self, analyzer):
        """Test enhanced trades flow scoring for extreme buy ratio."""
        score = analyzer._calculate_trades_flow_score(
            trades_flow={"flow_ratio": 122.0}  # Like BTC example
        )
        
        assert score == 10, f"Expected score=10 for flow_ratio=122 but got {score}"
        print(f"\nTrades Flow Score Test (Extreme Buy):")
        print(f"  Flow Ratio: 122.0")
        print(f"  Score: {score}")
    
    def test_calculate_trades_flow_score_extreme_sell(self, analyzer):
        """Test enhanced trades flow scoring for extreme sell ratio."""
        score = analyzer._calculate_trades_flow_score(
            trades_flow={"flow_ratio": 0.01}  # < 0.02
        )
        
        assert score == -10, f"Expected score=-10 for flow_ratio=0.01 but got {score}"
        print(f"\nTrades Flow Score Test (Extreme Sell):")
        print(f"  Flow Ratio: 0.01")
        print(f"  Score: {score}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
