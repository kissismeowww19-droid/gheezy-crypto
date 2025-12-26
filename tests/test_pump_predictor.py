"""
Test for Pump Predictor (Accumulation Detection) functionality.
Tests detect_accumulation() method and integration with probability calculation.
"""

import pytest
from signals.super_signals import SuperSignals


def test_detect_accumulation_strong():
    """Test strong accumulation detection: volume > 300%, price < 5%."""
    ss = SuperSignals()
    
    # Create mock candles (not used in current implementation, but required)
    candles = [{"close": 100, "volume": 1000} for _ in range(50)]
    
    # Strong accumulation: volume x4 (400%), price change 3%
    result = ss.detect_accumulation(candles, 4.0, 3.0)
    
    assert result["detected"] is True
    assert result["strength"] == "strong"
    assert result["signal"] == "🟢 Сильное накопление"
    assert result["volume_increase"] == 400.0
    assert result["price_change"] == 3.0


def test_detect_accumulation_moderate():
    """Test moderate accumulation detection: volume > 200%, price < 10%."""
    ss = SuperSignals()
    
    candles = [{"close": 100, "volume": 1000} for _ in range(50)]
    
    # Moderate accumulation: volume x2.5 (250%), price change 8%
    result = ss.detect_accumulation(candles, 2.5, 8.0)
    
    assert result["detected"] is True
    assert result["strength"] == "moderate"
    assert result["signal"] == "🟢 Накопление"
    assert result["volume_increase"] == 250.0
    assert result["price_change"] == 8.0


def test_detect_accumulation_weak():
    """Test weak accumulation detection: volume > 150%, price < 15%."""
    ss = SuperSignals()
    
    candles = [{"close": 100, "volume": 1000} for _ in range(50)]
    
    # Weak accumulation: volume x1.8 (180%), price change 12%
    result = ss.detect_accumulation(candles, 1.8, 12.0)
    
    assert result["detected"] is True
    assert result["strength"] == "weak"
    assert result["signal"] == "🟡 Слабое накопление"
    assert result["volume_increase"] == 180.0
    assert result["price_change"] == 12.0


def test_detect_accumulation_not_detected():
    """Test no accumulation when conditions aren't met."""
    ss = SuperSignals()
    
    candles = [{"close": 100, "volume": 1000} for _ in range(50)]
    
    # No accumulation: low volume, high price change
    result = ss.detect_accumulation(candles, 1.2, 20.0)
    
    assert result["detected"] is False
    assert result["strength"] is None
    assert result["signal"] is None
    assert result["volume_increase"] == 120.0
    assert result["price_change"] == 20.0


def test_detect_accumulation_negative_price_change():
    """Test accumulation with negative price change (absolute value used)."""
    ss = SuperSignals()
    
    candles = [{"close": 100, "volume": 1000} for _ in range(50)]
    
    # Strong accumulation with negative price change
    result = ss.detect_accumulation(candles, 3.5, -4.0)
    
    assert result["detected"] is True
    assert result["strength"] == "strong"
    assert result["price_change"] == 4.0  # Absolute value


def test_detect_accumulation_none_values():
    """Test accumulation with None values."""
    ss = SuperSignals()
    
    candles = [{"close": 100, "volume": 1000} for _ in range(50)]
    
    # None volume_ratio
    result = ss.detect_accumulation(candles, None, 5.0)
    assert result["detected"] is False
    
    # None price_change
    result = ss.detect_accumulation(candles, 3.0, None)
    assert result["detected"] is False


def test_calculate_probability_with_accumulation_long():
    """Test that accumulation adds points to probability for LONG signals."""
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
    
    # Test without accumulation
    prob_base = ss.calculate_probability(base_analysis)
    
    # Test with strong accumulation (should add 4 points)
    analysis_strong = base_analysis.copy()
    analysis_strong["accumulation"] = {
        "detected": True,
        "strength": "strong",
        "signal": "🟢 Сильное накопление",
        "volume_increase": 400,
        "price_change": 3
    }
    prob_strong = ss.calculate_probability(analysis_strong)
    
    # Test with moderate accumulation (should add 3 points)
    analysis_moderate = base_analysis.copy()
    analysis_moderate["accumulation"] = {
        "detected": True,
        "strength": "moderate",
        "signal": "🟢 Накопление",
        "volume_increase": 250,
        "price_change": 8
    }
    prob_moderate = ss.calculate_probability(analysis_moderate)
    
    # Test with weak accumulation (should add 1 point)
    analysis_weak = base_analysis.copy()
    analysis_weak["accumulation"] = {
        "detected": True,
        "strength": "weak",
        "signal": "🟡 Слабое накопление",
        "volume_increase": 180,
        "price_change": 12
    }
    prob_weak = ss.calculate_probability(analysis_weak)
    
    # Accumulation should increase probability
    assert prob_strong >= prob_moderate
    assert prob_moderate >= prob_weak
    assert prob_weak >= prob_base


def test_calculate_probability_with_accumulation_short():
    """Test that accumulation adds points to probability for SHORT signals."""
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
    
    # Test without accumulation
    prob_base = ss.calculate_probability(base_analysis)
    
    # Test with strong accumulation
    analysis_strong = base_analysis.copy()
    analysis_strong["accumulation"] = {
        "detected": True,
        "strength": "strong",
        "signal": "🟢 Сильное накопление",
        "volume_increase": 400,
        "price_change": 3
    }
    prob_strong = ss.calculate_probability(analysis_strong)
    
    # Accumulation should increase probability for shorts too
    assert prob_strong >= prob_base


def test_calculate_probability_with_breakdown():
    """Test calculate_probability_with_breakdown method."""
    ss = SuperSignals()
    
    # Perfect LONG signal
    analysis = {
        "symbol": "TEST",
        "direction": "long",
        "rsi": 25,  # Oversold
        "rsi_4h": 28,  # Oversold on 4h
        "macd": {"crossover": "bullish", "histogram": 0.5, "prev_histogram": 0.3},
        "funding_rate": -0.02,  # Negative funding
        "volume_ratio": 3.5,  # High volume
        "ema_trend": "bullish",
        "stoch_rsi": {"k": 15, "d": 15},
        "accumulation": {
            "detected": True,
            "strength": "strong",
            "volume_increase": 400,
            "price_change": 3
        }
    }
    
    result = ss.calculate_probability_with_breakdown(analysis, "long")
    
    # Check structure
    assert "probability" in result
    assert "breakdown" in result
    assert "total_score" in result
    assert "max_score" in result
    
    # Check breakdown categories
    assert "technical" in result["breakdown"]
    assert "volume" in result["breakdown"]
    assert "funding" in result["breakdown"]
    assert "trend" in result["breakdown"]
    
    # Each category should have score, max, details
    for category in result["breakdown"].values():
        assert "score" in category
        assert "max" in category
        assert "details" in category
        assert isinstance(category["details"], str)
    
    # With strong indicators, should have high probability
    assert result["probability"] >= 70
    assert result["total_score"] > 0
    assert result["max_score"] == 110  # 40 + 30 + 20 + 20


def test_calculate_probability_with_breakdown_short():
    """Test calculate_probability_with_breakdown for SHORT signals."""
    ss = SuperSignals()
    
    # Perfect SHORT signal
    analysis = {
        "symbol": "TEST",
        "direction": "short",
        "rsi": 75,  # Overbought
        "rsi_4h": 72,  # Overbought on 4h
        "macd": {"crossover": "bearish", "histogram": -0.5, "prev_histogram": -0.3},
        "funding_rate": 0.03,  # Positive funding
        "volume_ratio": 3.2,  # High volume
        "ema_trend": "bearish",
        "stoch_rsi": {"k": 85, "d": 85},
        "accumulation": {
            "detected": True,
            "strength": "moderate",
            "volume_increase": 250,
            "price_change": 7
        }
    }
    
    result = ss.calculate_probability_with_breakdown(analysis, "short")
    
    # Check that it works for short signals
    assert result["probability"] >= 70
    assert result["breakdown"]["technical"]["score"] > 0
    assert result["breakdown"]["volume"]["score"] > 0
    assert result["breakdown"]["funding"]["score"] > 0
    assert result["breakdown"]["trend"]["score"] > 0


def test_format_message_includes_accumulation():
    """Test that format_message includes accumulation information."""
    ss = SuperSignals()
    
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
        "volume_ratio": 3.5,
        "accumulation": {
            "detected": True,
            "strength": "strong",
            "signal": "🟢 Сильное накопление",
            "volume_increase": 400,
            "price_change": 3
        },
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
    
    # Check that accumulation is in the message
    assert "Накопление" in message
    assert "400" in message  # volume_increase
    assert "Сильное накопление" in message or "🟢" in message


def test_format_message_includes_breakdown():
    """Test that format_message includes breakdown information."""
    ss = SuperSignals()
    
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
        "volume_ratio": 3.5,
        "accumulation": {
            "detected": True,
            "strength": "strong",
            "signal": "🟢 Сильное накопление",
            "volume_increase": 400,
            "price_change": 3
        },
        "breakdown": {
            "technical": {"score": 30, "max": 40, "details": "RSI=25, MACD bullish"},
            "volume": {"score": 25, "max": 30, "details": "x3.5 всплеск, сильное накопление"},
            "funding": {"score": 15, "max": 20, "details": "-0.020% сквиз шортов"},
            "trend": {"score": 15, "max": 20, "details": "RSI_4h=28, 1h+4h совпадают"},
        },
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
    
    # Check that breakdown is in the message
    assert "Breakdown" in message or "breakdown" in message.lower()
    assert "Технический" in message or "technical" in message.lower()
    assert "Объём" in message or "volume" in message.lower()
    assert "Funding" in message
    assert "Тренд" in message or "trend" in message.lower()
