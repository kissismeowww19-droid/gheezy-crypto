"""
Tests for 5-block score calculation and real probability system.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_calc_trend_score():
    """Test _calc_trend_score method with various inputs."""
    from signals.ai_signals import AISignalAnalyzer
    
    # Mock whale tracker
    class MockWhaleTracker:
        pass
    
    analyzer = AISignalAnalyzer(MockWhaleTracker())
    
    # Test with all data available
    ema_data = {
        "ema_50": 50000,
        "ema_200": 48000,
        "current_price": 51000,
    }
    macd_data = {"signal": "bullish"}
    score = analyzer._calc_trend_score(ema_data, macd_data, 3.0, 7.0)
    assert -10 <= score <= 10, f"Score {score} out of range"
    assert score > 0, "Should be bullish with current_price > ema_50 > ema_200"
    
    # Test with bearish data
    ema_data_bearish = {
        "ema_50": 50000,
        "ema_200": 52000,
        "current_price": 49000,
    }
    macd_data_bearish = {"signal": "bearish"}
    score_bearish = analyzer._calc_trend_score(ema_data_bearish, macd_data_bearish, -3.0, -7.0)
    assert score_bearish < 0, "Should be bearish"
    
    # Test with no data
    score_empty = analyzer._calc_trend_score(None, None, None, None)
    assert score_empty == 0.0, "Should return 0 with no data"
    
    print("✓ test_calc_trend_score passed")


def test_calc_momentum_score():
    """Test _calc_momentum_score method."""
    from signals.ai_signals import AISignalAnalyzer
    
    class MockWhaleTracker:
        pass
    
    analyzer = AISignalAnalyzer(MockWhaleTracker())
    
    # Test oversold conditions (bullish)
    score = analyzer._calc_momentum_score(rsi=25, rsi_5m=28, rsi_15m=29, price_momentum_10min=1.5)
    assert score > 0, "Should be bullish with oversold RSI"
    
    # Test overbought conditions (bearish)
    score_bear = analyzer._calc_momentum_score(rsi=75, rsi_5m=72, rsi_15m=73, price_momentum_10min=-1.5)
    assert score_bear < 0, "Should be bearish with overbought RSI"
    
    # Test with no data
    score_empty = analyzer._calc_momentum_score(None, None, None, None)
    assert score_empty == 0.0, "Should return 0 with no data"
    
    print("✓ test_calc_momentum_score passed")


def test_calc_whales_score():
    """Test _calc_whales_score method."""
    from signals.ai_signals import AISignalAnalyzer
    
    class MockWhaleTracker:
        pass
    
    analyzer = AISignalAnalyzer(MockWhaleTracker())
    
    # Test bullish whale activity (more withdrawals than deposits)
    whale_data = {
        "deposits": 10,
        "withdrawals": 20,
    }
    score = analyzer._calc_whales_score(whale_data, -2000000)
    assert score > 0, "Should be bullish with more withdrawals"
    
    # Test bearish whale activity (more deposits than withdrawals)
    whale_data_bear = {
        "deposits": 20,
        "withdrawals": 10,
    }
    score_bear = analyzer._calc_whales_score(whale_data_bear, 2000000)
    assert score_bear < 0, "Should be bearish with more deposits"
    
    # Test with no data
    score_empty = analyzer._calc_whales_score(None, None)
    assert score_empty == 0.0, "Should return 0 with no data"
    
    print("✓ test_calc_whales_score passed")


def test_calc_derivatives_score():
    """Test _calc_derivatives_score method with composite rules."""
    from signals.ai_signals import AISignalAnalyzer
    
    class MockWhaleTracker:
        pass
    
    analyzer = AISignalAnalyzer(MockWhaleTracker())
    
    # Test composite rule: OI up + price up + normal funding = bullish
    score = analyzer._calc_derivatives_score(
        oi_change=5.0,
        funding_rate=0.01,
        long_short_ratio=1.2,
        liquidations={"long_liquidations": 100, "short_liquidations": 300},
        price_change=2.0
    )
    assert score > 0, "Should be bullish with OI up, price up, normal funding"
    
    # Test bearish scenario
    score_bear = analyzer._calc_derivatives_score(
        oi_change=-5.0,
        funding_rate=0.06,
        long_short_ratio=2.0,
        liquidations={"long_liquidations": 300, "short_liquidations": 100},
        price_change=-2.0
    )
    assert score_bear < 0, "Should be bearish"
    
    # Test with no data
    score_empty = analyzer._calc_derivatives_score(None, None, None, None, None)
    assert score_empty == 0.0, "Should return 0 with no data"
    
    print("✓ test_calc_derivatives_score passed")


def test_calc_sentiment_score():
    """Test _calc_sentiment_score method."""
    from signals.ai_signals import AISignalAnalyzer
    
    class MockWhaleTracker:
        pass
    
    analyzer = AISignalAnalyzer(MockWhaleTracker())
    
    # Test extreme fear (bullish)
    score = analyzer._calc_sentiment_score(fear_greed=15, tradingview_rating="STRONG_BUY")
    assert score > 0, "Should be bullish with extreme fear"
    
    # Test extreme greed (bearish)
    score_bear = analyzer._calc_sentiment_score(fear_greed=85, tradingview_rating="STRONG_SELL")
    assert score_bear < 0, "Should be bearish with extreme greed"
    
    # Test with no data
    score_empty = analyzer._calc_sentiment_score(None, None)
    assert score_empty == 0.0, "Should return 0 with no data"
    
    print("✓ test_calc_sentiment_score passed")


def test_calculate_probability():
    """Test _calculate_probability method for real probability calculation."""
    from signals.ai_signals import AISignalAnalyzer
    
    class MockWhaleTracker:
        pass
    
    analyzer = AISignalAnalyzer(MockWhaleTracker())
    
    # Test strong signal with good coverage
    prob = analyzer._calculate_probability(
        total_score=50,
        direction="long",
        bullish_count=15,
        bearish_count=3,
        data_sources_count=18,
        total_sources=22,
        trend_score=7.0
    )
    assert 50 <= prob <= 85, f"Probability {prob} out of range"
    assert prob >= 65, "Strong signal with good coverage should have high probability (>=65%)"
    
    # Test weak signal with low coverage
    prob_weak = analyzer._calculate_probability(
        total_score=5,
        direction="sideways",
        bullish_count=5,
        bearish_count=5,
        data_sources_count=8,
        total_sources=22,
        trend_score=0.0
    )
    assert 50 <= prob_weak <= 60, f"Weak signal should have low probability, got {prob_weak}"
    
    # Test signal against trend
    prob_against = analyzer._calculate_probability(
        total_score=30,
        direction="long",
        bullish_count=10,
        bearish_count=5,
        data_sources_count=15,
        total_sources=22,
        trend_score=-5.0  # Bearish trend
    )
    assert prob_against < 70, "Signal against trend should have reduced probability"
    
    # Test sideways should cap at 55%
    prob_sideways = analyzer._calculate_probability(
        total_score=10,
        direction="sideways",
        bullish_count=8,
        bearish_count=8,
        data_sources_count=20,
        total_sources=22,
        trend_score=0.0
    )
    assert 50 <= prob_sideways <= 55, f"Sideways should be 50-55%, got {prob_sideways}"
    
    print("✓ test_calculate_probability passed")


def test_5block_integration():
    """Test that 5 blocks are properly integrated in calculate_signal."""
    from signals.ai_signals import AISignalAnalyzer
    
    class MockWhaleTracker:
        pass
    
    analyzer = AISignalAnalyzer(MockWhaleTracker())
    
    # Create minimal test data
    whale_data = {
        "transaction_count": 10,
        "deposits": 5,
        "withdrawals": 15,
        "total_volume_usd": 1000000
    }
    
    market_data = {
        "price_usd": 50000,
        "market_cap": 1000000000000,
        "volume_24h": 50000000000,
        "change_24h": 2.5,
        "change_7d": 5.0
    }
    
    technical_data = {
        "rsi": {"value": 45},
        "macd": {"signal": "bullish"},
        "ma_crossover": {"trend": "bullish", "crossover": None}
    }
    
    # Call calculate_signal
    result = analyzer.calculate_signal(
        symbol="BTC",
        whale_data=whale_data,
        market_data=market_data,
        technical_data=technical_data
    )
    
    # Check that 5 block scores are present in result
    assert "block_trend_score" in result, "Missing block_trend_score"
    assert "block_momentum_score" in result, "Missing block_momentum_score"
    assert "block_whales_score" in result, "Missing block_whales_score"
    assert "block_derivatives_score" in result, "Missing block_derivatives_score"
    assert "block_sentiment_score" in result, "Missing block_sentiment_score"
    
    # Check that all block scores are in valid range
    for key in ["block_trend_score", "block_momentum_score", "block_whales_score", 
                "block_derivatives_score", "block_sentiment_score"]:
        score = result[key]
        assert -10 <= score <= 10, f"{key} = {score} is out of range [-10, 10]"
    
    # Check that probability is reasonable
    prob = result["probability"]
    assert 50 <= prob <= 85, f"Probability {prob} out of range [50, 85]"
    
    print("✓ test_5block_integration passed")


if __name__ == "__main__":
    test_calc_trend_score()
    test_calc_momentum_score()
    test_calc_whales_score()
    test_calc_derivatives_score()
    test_calc_sentiment_score()
    test_calculate_probability()
    test_5block_integration()
    print("\n✅ All tests passed!")
