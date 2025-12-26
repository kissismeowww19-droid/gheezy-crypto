"""
Test for SuperSignals improvements - new indicators.
Tests RSI 4h, EMA 20/50, and Stochastic RSI functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch


def test_calculate_ema():
    """Test EMA calculation method."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Create test candles
    candles = [
        {"close": 100},
        {"close": 102},
        {"close": 101},
        {"close": 103},
        {"close": 105},
        {"close": 104},
        {"close": 106},
        {"close": 108},
        {"close": 107},
        {"close": 109},
        {"close": 110},
        {"close": 112},
        {"close": 111},
        {"close": 113},
        {"close": 115},
        {"close": 114},
        {"close": 116},
        {"close": 118},
        {"close": 117},
        {"close": 119},
    ]
    
    # Calculate EMA 20
    ema_20 = ss._calculate_ema(candles, 20)
    
    # EMA should be a positive number close to recent prices
    assert ema_20 > 0
    assert 100 < ema_20 < 120  # Should be in range of prices
    
    # Test with insufficient data
    short_candles = [{"close": 100}, {"close": 102}]
    ema = ss._calculate_ema(short_candles, 20)
    assert ema == 0  # Should return 0 for insufficient data


def test_calculate_stoch_rsi():
    """Test Stochastic RSI calculation method."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Create test candles with a trend
    candles = []
    for i in range(50):
        candles.append({"close": 100 + i * 0.5})  # Upward trend
    
    stoch_rsi = ss._calculate_stoch_rsi(candles, period=14)
    
    # Should return dict with k and d
    assert isinstance(stoch_rsi, dict)
    assert "k" in stoch_rsi
    assert "d" in stoch_rsi
    
    # Values should be between 0 and 100
    assert 0 <= stoch_rsi["k"] <= 100
    assert 0 <= stoch_rsi["d"] <= 100
    
    # Test with insufficient data
    short_candles = [{"close": 100 + i} for i in range(10)]
    stoch_rsi = ss._calculate_stoch_rsi(short_candles)
    assert stoch_rsi == {"k": 50, "d": 50}  # Should return neutral values


def test_calculate_indicators_includes_new_indicators():
    """Test that _calculate_indicators includes RSI 4h, EMA, and Stochastic RSI."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Create test candles
    candles_1h = [{"close": 100 + i, "high": 102 + i, "low": 98 + i, "volume": 1000} for i in range(50)]
    candles_4h = [{"close": 100 + i * 2, "high": 102 + i * 2, "low": 98 + i * 2, "volume": 4000} for i in range(30)]
    
    result = ss._calculate_indicators(candles_1h, candles_4h, 150)
    
    # Check new indicators are present
    assert "rsi_4h" in result
    assert "ema_20" in result
    assert "ema_50" in result
    assert "ema_trend" in result
    assert "price_vs_ema" in result
    assert "stoch_rsi" in result
    
    # Check types and values
    assert result["rsi_4h"] is not None
    assert result["rsi_4h"] > 0
    assert result["ema_20"] > 0
    assert result["ema_50"] > 0
    assert result["ema_trend"] in ["bullish", "bearish"]
    assert result["price_vs_ema"] in ["above", "below"]
    assert isinstance(result["stoch_rsi"], dict)
    assert "k" in result["stoch_rsi"]


def test_calculate_probability_with_rsi_4h_long():
    """Test that RSI 4h adds appropriate points for LONG signals."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Base analysis with minimal score
    base_analysis = {
        "symbol": "TEST",
        "direction": "long",
        "rsi": 50,
        "macd": {"crossover": None, "histogram": 0, "prev_histogram": 0},
        "funding_rate": 0,
        "volume_ratio": 1.0,
        "bb_position": 0.5,
        "price_to_support": 10.0,
        "price_to_resistance": 10.0,
        "change_24h": 0,
    }
    
    # Test with RSI 4h < 30 (should add 2 points)
    analysis_strong = base_analysis.copy()
    analysis_strong["rsi_4h"] = 25
    prob_strong = ss.calculate_probability(analysis_strong)
    
    # Test with RSI 4h < 40 (should add 1 point)
    analysis_medium = base_analysis.copy()
    analysis_medium["rsi_4h"] = 35
    prob_medium = ss.calculate_probability(analysis_medium)
    
    # Test without RSI 4h
    prob_base = ss.calculate_probability(base_analysis)
    
    # RSI 4h should increase probability
    assert prob_strong >= prob_medium
    assert prob_medium >= prob_base


def test_calculate_probability_with_rsi_4h_short():
    """Test that RSI 4h adds appropriate points for SHORT signals."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Base analysis with minimal score
    base_analysis = {
        "symbol": "TEST",
        "direction": "short",
        "rsi": 50,
        "macd": {"crossover": None, "histogram": 0, "prev_histogram": 0},
        "funding_rate": 0,
        "volume_ratio": 1.0,
        "bb_position": 0.5,
        "price_to_support": 10.0,
        "price_to_resistance": 10.0,
        "change_24h": 0,
    }
    
    # Test with RSI 4h > 70 (should add 2 points)
    analysis_strong = base_analysis.copy()
    analysis_strong["rsi_4h"] = 75
    prob_strong = ss.calculate_probability(analysis_strong)
    
    # Test with RSI 4h > 60 (should add 1 point)
    analysis_medium = base_analysis.copy()
    analysis_medium["rsi_4h"] = 65
    prob_medium = ss.calculate_probability(analysis_medium)
    
    # Test without RSI 4h
    prob_base = ss.calculate_probability(base_analysis)
    
    # RSI 4h should increase probability
    assert prob_strong >= prob_medium
    assert prob_medium >= prob_base


def test_calculate_probability_with_ema_trend_long():
    """Test that EMA trend adds points for LONG signals."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    base_analysis = {
        "symbol": "TEST",
        "direction": "long",
        "rsi": 50,
        "macd": {"crossover": None, "histogram": 0, "prev_histogram": 0},
        "funding_rate": 0,
        "volume_ratio": 1.0,
        "bb_position": 0.5,
        "price_to_support": 10.0,
        "price_to_resistance": 10.0,
        "change_24h": 0,
    }
    
    # Test with bullish EMA trend
    analysis_bullish = base_analysis.copy()
    analysis_bullish["ema_trend"] = "bullish"
    prob_bullish = ss.calculate_probability(analysis_bullish)
    
    # Test with bearish EMA trend
    analysis_bearish = base_analysis.copy()
    analysis_bearish["ema_trend"] = "bearish"
    prob_bearish = ss.calculate_probability(analysis_bearish)
    
    # Test without EMA trend
    prob_base = ss.calculate_probability(base_analysis)
    
    # Bullish trend should have higher probability for LONG
    assert prob_bullish >= prob_base
    # Bearish trend shouldn't add points
    assert prob_bearish == prob_base


def test_calculate_probability_with_price_vs_ema_long():
    """Test that price vs EMA adds points for LONG signals."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    base_analysis = {
        "symbol": "TEST",
        "direction": "long",
        "rsi": 50,
        "macd": {"crossover": None, "histogram": 0, "prev_histogram": 0},
        "funding_rate": 0,
        "volume_ratio": 1.0,
        "bb_position": 0.5,
        "price_to_support": 10.0,
        "price_to_resistance": 10.0,
        "change_24h": 0,
    }
    
    # Test with price above EMA
    analysis_above = base_analysis.copy()
    analysis_above["price_vs_ema"] = "above"
    prob_above = ss.calculate_probability(analysis_above)
    
    # Test with price below EMA
    analysis_below = base_analysis.copy()
    analysis_below["price_vs_ema"] = "below"
    prob_below = ss.calculate_probability(analysis_below)
    
    # Test without price_vs_ema
    prob_base = ss.calculate_probability(base_analysis)
    
    # Price above EMA should have higher probability for LONG
    assert prob_above >= prob_base
    # Price below shouldn't add points
    assert prob_below == prob_base


def test_calculate_probability_with_stoch_rsi_long():
    """Test that Stochastic RSI adds points for LONG signals."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    base_analysis = {
        "symbol": "TEST",
        "direction": "long",
        "rsi": 50,
        "macd": {"crossover": None, "histogram": 0, "prev_histogram": 0},
        "funding_rate": 0,
        "volume_ratio": 1.0,
        "bb_position": 0.5,
        "price_to_support": 10.0,
        "price_to_resistance": 10.0,
        "change_24h": 0,
    }
    
    # Test with StochRSI < 20 (should add 2 points)
    analysis_very_low = base_analysis.copy()
    analysis_very_low["stoch_rsi"] = {"k": 15, "d": 15}
    prob_very_low = ss.calculate_probability(analysis_very_low)
    
    # Test with StochRSI < 30 (should add 1 point)
    analysis_low = base_analysis.copy()
    analysis_low["stoch_rsi"] = {"k": 25, "d": 25}
    prob_low = ss.calculate_probability(analysis_low)
    
    # Test without StochRSI
    prob_base = ss.calculate_probability(base_analysis)
    
    # Lower StochRSI should increase probability for LONG
    assert prob_very_low >= prob_low
    assert prob_low >= prob_base


def test_calculate_probability_with_stoch_rsi_short():
    """Test that Stochastic RSI adds points for SHORT signals."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    base_analysis = {
        "symbol": "TEST",
        "direction": "short",
        "rsi": 50,
        "macd": {"crossover": None, "histogram": 0, "prev_histogram": 0},
        "funding_rate": 0,
        "volume_ratio": 1.0,
        "bb_position": 0.5,
        "price_to_support": 10.0,
        "price_to_resistance": 10.0,
        "change_24h": 0,
    }
    
    # Test with StochRSI > 80 (should add 2 points)
    analysis_very_high = base_analysis.copy()
    analysis_very_high["stoch_rsi"] = {"k": 85, "d": 85}
    prob_very_high = ss.calculate_probability(analysis_very_high)
    
    # Test with StochRSI > 70 (should add 1 point)
    analysis_high = base_analysis.copy()
    analysis_high["stoch_rsi"] = {"k": 75, "d": 75}
    prob_high = ss.calculate_probability(analysis_high)
    
    # Test without StochRSI
    prob_base = ss.calculate_probability(base_analysis)
    
    # Higher StochRSI should increase probability for SHORT
    assert prob_very_high >= prob_high
    assert prob_high >= prob_base


def test_format_message_includes_new_indicators():
    """Test that format_message includes RSI 4h, EMA, and Stochastic RSI."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Create a signal with all new indicators
    signal = {
        "symbol": "TEST",
        "direction": "long",
        "current_price": 100,
        "probability": 85,
        "rsi": 25,
        "rsi_4h": 28,
        "ema_trend": "bullish",
        "stoch_rsi": {"k": 15, "d": 15},
        "macd": {"crossover": "bullish", "histogram": 0.5},
        "funding_rate": -0.02,
        "volume_ratio": 2.5,
        "exchanges": ["Binance", "Bybit"],
        "levels": {
            "entry_low": 99,
            "entry_high": 101,
            "stop_loss": 95,
            "stop_percent": -5,
            "tp1": 110,
            "tp1_percent": 10,
            "tp2": 115,
            "tp2_percent": 15,
            "rr_ratio": 2.0,
        },
    }
    
    message = ss.format_message([signal], 3000, 30)
    
    # Check that new indicators are in the message
    assert "RSI(4h)" in message or "RSI\\(4h\\)" in message
    assert "EMA 20/50" in message
    assert "StochRSI" in message
    
    # Check that the indicators have proper formatting
    assert "28" in message  # RSI 4h value
    assert "бычий" in message or "медвежий" in message  # EMA trend
    assert "15" in message  # StochRSI K value


def test_complete_signal_with_all_indicators():
    """Test complete probability calculation with all indicators (integration test)."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Perfect LONG signal with all new indicators
    analysis_perfect_long = {
        "symbol": "TEST",
        "direction": "long",
        "rsi": 20,  # Oversold 1h (+3)
        "rsi_4h": 25,  # Oversold 4h (+2)
        "macd": {"crossover": "bullish", "histogram": 0.5, "prev_histogram": 0.3},  # (+3)
        "funding_rate": -0.02,  # Negative funding (+2)
        "volume_ratio": 3.0,  # High volume (+2)
        "bb_position": 0.1,  # Near lower BB (+1)
        "price_to_support": 1.5,  # Close to support (+2)
        "price_to_resistance": 10.0,
        "change_24h": 60.0,  # Very strong drop (+3)
        "ema_trend": "bullish",  # Bullish trend (+1)
        "price_vs_ema": "above",  # Above EMA (+1)
        "stoch_rsi": {"k": 15, "d": 15},  # Very oversold (+2)
    }
    
    probability = ss.calculate_probability(analysis_perfect_long)
    
    # With all these positive indicators, should have very high probability
    # Score = 3+2+3+2+2+1+2+3+1+1+2 = 22, capped at 15 = 90%
    assert probability == 90
    
    # Perfect SHORT signal with all new indicators
    analysis_perfect_short = {
        "symbol": "TEST",
        "direction": "short",
        "rsi": 80,  # Overbought 1h (+3)
        "rsi_4h": 75,  # Overbought 4h (+2)
        "macd": {"crossover": "bearish", "histogram": -0.5, "prev_histogram": -0.3},  # (+3)
        "funding_rate": 0.03,  # Positive funding (+2)
        "volume_ratio": 2.8,  # High volume (+2)
        "bb_position": 0.9,  # Near upper BB (+1)
        "price_to_support": 10.0,
        "price_to_resistance": 1.2,  # Close to resistance (+2)
        "change_24h": 70.0,  # Very strong rise (+3)
        "ema_trend": "bearish",  # Bearish trend (+1)
        "price_vs_ema": "below",  # Below EMA (+1)
        "stoch_rsi": {"k": 85, "d": 85},  # Very overbought (+2)
    }
    
    probability = ss.calculate_probability(analysis_perfect_short)
    
    # With all these positive indicators, should have very high probability
    assert probability == 90
