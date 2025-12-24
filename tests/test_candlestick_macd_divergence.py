"""
Tests for Candlestick Patterns and MACD Divergence.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.indicators import (
    detect_candlestick_patterns,
    calculate_macd_divergence,
    CandlestickPattern,
    MACDDivergence
)


def test_hammer_pattern():
    """Test Hammer pattern detection."""
    # Hammer: small body, long lower shadow (2x+ body), small upper shadow
    ohlcv = [
        {'open': 100, 'high': 101, 'low': 95, 'close': 100.5},  # Hammer-like
    ]
    
    patterns = detect_candlestick_patterns(ohlcv)
    
    # Should detect a hammer (bullish reversal)
    assert len(patterns) >= 1
    hammer_found = any(p.name == "hammer" for p in patterns)
    assert hammer_found


def test_hanging_man_pattern():
    """Test Hanging Man pattern detection."""
    # Hanging Man: similar to hammer but bearish at top
    ohlcv = [
        {'open': 100, 'high': 100.5, 'low': 95, 'close': 99.5},  # Hanging man-like
    ]
    
    patterns = detect_candlestick_patterns(ohlcv)
    
    # Should detect a hanging man
    assert len(patterns) >= 1
    hanging_man_found = any(p.name == "hanging_man" for p in patterns)
    assert hanging_man_found


def test_doji_pattern():
    """Test Doji pattern detection."""
    # Doji: very small body (open ≈ close)
    ohlcv = [
        {'open': 100, 'high': 102, 'low': 98, 'close': 100.1},  # Doji
    ]
    
    patterns = detect_candlestick_patterns(ohlcv)
    
    # Should detect a doji
    assert len(patterns) >= 1
    doji_found = any(p.name == "doji" for p in patterns)
    assert doji_found


def test_bullish_engulfing():
    """Test Bullish Engulfing pattern detection."""
    # Bullish Engulfing: previous red, current green, current engulfs previous
    ohlcv = [
        {'open': 100, 'high': 101, 'low': 98, 'close': 99},    # Red candle
        {'open': 98.5, 'high': 102, 'low': 97, 'close': 101},  # Green engulfing
    ]
    
    patterns = detect_candlestick_patterns(ohlcv)
    
    # Should detect bullish engulfing
    assert len(patterns) >= 1
    engulfing_found = any(p.name == "engulfing_bullish" for p in patterns)
    assert engulfing_found
    
    if engulfing_found:
        pattern = [p for p in patterns if p.name == "engulfing_bullish"][0]
        assert pattern.type == "bullish"
        assert pattern.strength == 1.5


def test_bearish_engulfing():
    """Test Bearish Engulfing pattern detection."""
    # Bearish Engulfing: previous green, current red, current engulfs previous
    ohlcv = [
        {'open': 100, 'high': 102, 'low': 99, 'close': 101},   # Green candle
        {'open': 101.5, 'high': 103, 'low': 98, 'close': 99},  # Red engulfing
    ]
    
    patterns = detect_candlestick_patterns(ohlcv)
    
    # Should detect bearish engulfing
    assert len(patterns) >= 1
    engulfing_found = any(p.name == "engulfing_bearish" for p in patterns)
    assert engulfing_found
    
    if engulfing_found:
        pattern = [p for p in patterns if p.name == "engulfing_bearish"][0]
        assert pattern.type == "bearish"
        assert pattern.strength == 1.5


def test_morning_star():
    """Test Morning Star pattern detection."""
    # Morning Star: long red, small star, long green
    ohlcv = [
        {'open': 105, 'high': 106, 'low': 100, 'close': 101},  # Long red
        {'open': 100, 'high': 101, 'low': 99, 'close': 99.5},  # Small star
        {'open': 99.5, 'high': 105, 'low': 99, 'close': 106},  # Long green
    ]
    
    patterns = detect_candlestick_patterns(ohlcv)
    
    # Should detect morning star
    assert len(patterns) >= 1
    morning_star_found = any(p.name == "morning_star" for p in patterns)
    assert morning_star_found
    
    if morning_star_found:
        pattern = [p for p in patterns if p.name == "morning_star"][0]
        assert pattern.type == "bullish"


def test_evening_star():
    """Test Evening Star pattern detection."""
    # Evening Star: long green, small star, long red
    ohlcv = [
        {'open': 100, 'high': 105, 'low': 99, 'close': 104},   # Long green
        {'open': 104, 'high': 105, 'low': 103, 'close': 104.5}, # Small star
        {'open': 104.5, 'high': 105, 'low': 99, 'close': 100},  # Long red
    ]
    
    patterns = detect_candlestick_patterns(ohlcv)
    
    # Should detect evening star
    assert len(patterns) >= 1
    evening_star_found = any(p.name == "evening_star" for p in patterns)
    assert evening_star_found
    
    if evening_star_found:
        pattern = [p for p in patterns if p.name == "evening_star"][0]
        assert pattern.type == "bearish"


def test_three_white_soldiers():
    """Test Three White Soldiers pattern detection."""
    # Three White Soldiers: three consecutive bullish candles
    ohlcv = [
        {'open': 100, 'high': 102, 'low': 99, 'close': 101},   # Green 1
        {'open': 100.5, 'high': 103, 'low': 100, 'close': 102}, # Green 2
        {'open': 101.5, 'high': 104, 'low': 101, 'close': 103}, # Green 3
    ]
    
    patterns = detect_candlestick_patterns(ohlcv)
    
    # Should detect three white soldiers
    assert len(patterns) >= 1
    soldiers_found = any(p.name == "three_white_soldiers" for p in patterns)
    assert soldiers_found
    
    if soldiers_found:
        pattern = [p for p in patterns if p.name == "three_white_soldiers"][0]
        assert pattern.type == "bullish"


def test_three_black_crows():
    """Test Three Black Crows pattern detection."""
    # Three Black Crows: three consecutive bearish candles
    ohlcv = [
        {'open': 103, 'high': 104, 'low': 101, 'close': 102},  # Red 1
        {'open': 102.5, 'high': 103, 'low': 100, 'close': 101}, # Red 2
        {'open': 101.5, 'high': 102, 'low': 99, 'close': 100},  # Red 3
    ]
    
    patterns = detect_candlestick_patterns(ohlcv)
    
    # Should detect three black crows
    assert len(patterns) >= 1
    crows_found = any(p.name == "three_black_crows" for p in patterns)
    assert crows_found
    
    if crows_found:
        pattern = [p for p in patterns if p.name == "three_black_crows"][0]
        assert pattern.type == "bearish"


def test_no_patterns_with_insufficient_data():
    """Test that no patterns are detected with insufficient data."""
    ohlcv = []
    patterns = detect_candlestick_patterns(ohlcv)
    assert len(patterns) == 0
    
    ohlcv = [{'open': 100, 'high': 101, 'low': 99, 'close': 100}]
    patterns = detect_candlestick_patterns(ohlcv)
    # May have some patterns but should not crash


def test_macd_divergence_bullish():
    """Test Bullish MACD Divergence detection."""
    # Price making lower lows, MACD making higher lows
    prices = [100, 98, 97, 96, 95, 94, 93, 92, 91, 90,  # Downtrend
              91, 92, 91, 90, 89, 88.5, 88, 87.5, 87, 86.5]  # Lower low
    
    # MACD histogram making higher lows
    macd_histogram = [-1.0, -1.2, -1.3, -1.4, -1.5, -1.4, -1.3, -1.2, -1.1, -1.0,
                      -0.9, -0.8, -0.7, -0.6, -0.5, -0.4, -0.3, -0.2, -0.1, 0.0]
    
    result = calculate_macd_divergence(prices, macd_histogram, lookback=14)
    
    # Should detect bullish divergence
    assert result is not None
    assert result.type == "bullish"
    assert result.strength > 0


def test_macd_divergence_bearish():
    """Test Bearish MACD Divergence detection."""
    # Price making higher highs, MACD making lower highs
    prices = [100, 102, 103, 104, 105, 106, 107, 108, 109, 110,  # Uptrend
              111, 112, 113, 114, 115, 116, 117, 118, 119, 120]  # Higher high
    
    # MACD histogram making lower highs
    macd_histogram = [1.0, 1.2, 1.3, 1.4, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0,
                      0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0]
    
    result = calculate_macd_divergence(prices, macd_histogram, lookback=14)
    
    # Should detect bearish divergence
    assert result is not None
    assert result.type == "bearish"
    assert result.strength > 0


def test_macd_divergence_none():
    """Test when no MACD divergence is present."""
    # Price and MACD moving together (no divergence)
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
              110, 111, 112, 113, 114, 115, 116, 117, 118, 119]
    
    macd_histogram = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
                      1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]
    
    result = calculate_macd_divergence(prices, macd_histogram, lookback=14)
    
    # Should not detect divergence
    assert result is not None
    assert result.type == "none"


def test_macd_divergence_insufficient_data():
    """Test MACD divergence with insufficient data."""
    prices = [100, 101, 102]
    macd_histogram = [0.1, 0.2, 0.3]
    
    result = calculate_macd_divergence(prices, macd_histogram, lookback=14)
    
    # Should return None
    assert result is None


def test_candlestick_pattern_dataclass():
    """Test CandlestickPattern dataclass."""
    pattern = CandlestickPattern(name="hammer", type="bullish", strength=1.2)
    
    assert pattern.name == "hammer"
    assert pattern.type == "bullish"
    assert pattern.strength == 1.2


def test_macd_divergence_dataclass():
    """Test MACDDivergence dataclass."""
    div = MACDDivergence(
        type="bullish",
        strength=75.0,
        explanation="Price making lower lows but MACD making higher lows"
    )
    
    assert div.type == "bullish"
    assert div.strength == 75.0
    assert "lower lows" in div.explanation

