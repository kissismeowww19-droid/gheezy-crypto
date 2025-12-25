"""
Test for SuperSignals implementation.
Validates the structure and basic functionality of the SuperSignals class.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_super_signals_class_exists():
    """Test that SuperSignals class can be imported."""
    from signals.super_signals import SuperSignals
    assert SuperSignals is not None


def test_super_signals_constants():
    """Test that required constants are defined."""
    from signals.super_signals import SuperSignals
    
    # Check filtering constants
    assert hasattr(SuperSignals, 'MIN_PROBABILITY')
    assert SuperSignals.MIN_PROBABILITY == 60
    
    assert hasattr(SuperSignals, 'TOP_CANDIDATES')
    assert SuperSignals.TOP_CANDIDATES == 30
    
    assert hasattr(SuperSignals, 'TOP_SIGNALS')
    assert SuperSignals.TOP_SIGNALS == 5
    
    assert hasattr(SuperSignals, 'MIN_CHANGE_24H')
    assert SuperSignals.MIN_CHANGE_24H == 15
    
    assert hasattr(SuperSignals, 'MIN_VOLUME')
    assert SuperSignals.MIN_VOLUME == 500000
    
    assert hasattr(SuperSignals, 'MAX_MCAP')
    assert SuperSignals.MAX_MCAP == 1000000000


def test_super_signals_methods_exist():
    """Test that required methods are defined."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Main methods
    assert hasattr(ss, 'scan')
    assert callable(ss.scan)
    
    assert hasattr(ss, 'apply_filters')
    assert callable(ss.apply_filters)
    
    assert hasattr(ss, 'deep_analyze')
    assert callable(ss.deep_analyze)
    
    assert hasattr(ss, 'calculate_probability')
    assert callable(ss.calculate_probability)
    
    assert hasattr(ss, 'calculate_real_levels')
    assert callable(ss.calculate_real_levels)
    
    assert hasattr(ss, 'format_message')
    assert callable(ss.format_message)
    
    assert hasattr(ss, 'close')
    assert callable(ss.close)


def test_apply_filters():
    """Test the apply_filters method."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Create test data
    coins = [
        {
            "symbol": "BTC",
            "current_price": 50000,
            "price_change_percentage_24h": 20.0,  # > 15%
            "total_volume": 1000000,  # > 500K
            "market_cap": 500000000,  # < 1B
        },
        {
            "symbol": "USDT",  # Stablecoin - should be excluded
            "current_price": 1.0,
            "price_change_percentage_24h": 0.1,
            "total_volume": 10000000,
            "market_cap": 100000000,
        },
        {
            "symbol": "ETH",
            "current_price": 3000,
            "price_change_percentage_24h": 10.0,  # < 15% - should be excluded
            "total_volume": 2000000,
            "market_cap": 400000000,
        },
        {
            "symbol": "SOL",
            "current_price": 100,
            "price_change_percentage_24h": -18.0,  # Negative but > 15% abs
            "total_volume": 800000,
            "market_cap": 600000000,
        },
    ]
    
    filtered = ss.apply_filters(coins)
    
    # Should include BTC and SOL, exclude USDT and ETH
    assert len(filtered) == 2
    symbols = [c["symbol"] for c in filtered]
    assert "BTC" in symbols
    assert "SOL" in symbols
    assert "USDT" not in symbols
    assert "ETH" not in symbols


def test_calculate_probability_long():
    """Test probability calculation for LONG signal."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Perfect LONG conditions
    analysis = {
        "direction": "long",
        "rsi": 25,  # Oversold
        "macd": {"crossover": "bullish", "histogram": 0.5, "prev_histogram": 0.3},
        "funding_rate": -0.02,  # Negative funding
        "volume_ratio": 3.0,  # High volume
        "bb_position": 0.1,  # Near lower BB
        "price_to_support": 1.5,  # Close to support
        "price_to_resistance": 10.0,
    }
    
    probability = ss.calculate_probability(analysis)
    
    # Should be high probability (>= 65%)
    assert probability >= 65
    assert probability <= 85


def test_calculate_probability_short():
    """Test probability calculation for SHORT signal."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Perfect SHORT conditions
    analysis = {
        "direction": "short",
        "rsi": 78,  # Overbought
        "macd": {"crossover": "bearish", "histogram": -0.5, "prev_histogram": -0.3},
        "funding_rate": 0.03,  # Positive funding
        "volume_ratio": 2.8,  # High volume
        "bb_position": 0.9,  # Near upper BB
        "price_to_support": 10.0,
        "price_to_resistance": 1.2,  # Close to resistance
    }
    
    probability = ss.calculate_probability(analysis)
    
    # Should be high probability (>= 65%)
    assert probability >= 65
    assert probability <= 85


def test_calculate_real_levels_long():
    """Test real levels calculation for LONG."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    analysis = {
        "direction": "long",
        "current_price": 50000,
        "support": 49000,
        "resistance": 52000,
        "atr": 500,
    }
    
    levels = ss.calculate_real_levels(analysis)
    
    assert "entry_low" in levels
    assert "entry_high" in levels
    assert "stop_loss" in levels
    assert "tp1" in levels
    assert "tp2" in levels
    assert "rr_ratio" in levels
    
    # Entry should be around current price
    assert levels["entry_low"] < 50000
    assert levels["entry_high"] > 50000
    
    # Stop should be below support
    assert levels["stop_loss"] < 49000
    
    # TP1 should be near resistance
    assert levels["tp1"] < 52000
    assert levels["tp1"] > 50000
    
    # TP2 should be above resistance
    assert levels["tp2"] > 52000


def test_calculate_real_levels_short():
    """Test real levels calculation for SHORT."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    analysis = {
        "direction": "short",
        "current_price": 50000,
        "support": 48000,
        "resistance": 51000,
        "atr": 500,
    }
    
    levels = ss.calculate_real_levels(analysis)
    
    # Stop should be above resistance
    assert levels["stop_loss"] > 51000
    
    # TP1 should be near support
    assert levels["tp1"] > 48000
    assert levels["tp1"] < 50000
    
    # TP2 should be below support
    assert levels["tp2"] < 48000


def test_score_to_probability():
    """Test score to probability conversion."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Test different score levels
    assert ss.score_to_probability(12) == 85
    assert ss.score_to_probability(13) == 85
    assert ss.score_to_probability(10) == 75
    assert ss.score_to_probability(11) == 75
    assert ss.score_to_probability(8) == 65
    assert ss.score_to_probability(9) == 65
    assert ss.score_to_probability(6) == 55
    assert ss.score_to_probability(7) == 55
    assert ss.score_to_probability(5) == 45
    assert ss.score_to_probability(0) == 45


def test_format_message_empty():
    """Test format_message with empty signals list."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    message = ss.format_message([], 3000, 0)
    
    # Should contain header information
    assert "СУПЕР СИГНАЛЫ" in message
    assert "3,000" in message or "3000" in message
    
    # Should indicate no signals found (implicitly by having 0 signals)
    assert "ТОП-0" in message
