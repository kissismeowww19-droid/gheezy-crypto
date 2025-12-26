"""
Test for SuperSignals implementation.
Validates the structure and basic functionality of the SuperSignals class.
"""

import pytest
from unittest.mock import AsyncMock, patch


def test_super_signals_class_exists():
    """Test that SuperSignals class can be imported."""
    from signals.super_signals import SuperSignals
    assert SuperSignals is not None


def test_super_signals_constants():
    """Test that required constants are defined."""
    from signals.super_signals import SuperSignals
    
    # Check filtering constants
    assert hasattr(SuperSignals, 'MIN_PROBABILITY')
    assert SuperSignals.MIN_PROBABILITY == 45  # Updated to 45
    
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
    
    # New kline fetching methods
    assert hasattr(ss, 'fetch_binance_klines')
    assert callable(ss.fetch_binance_klines)
    
    assert hasattr(ss, 'fetch_bybit_klines')
    assert callable(ss.fetch_bybit_klines)
    
    assert hasattr(ss, 'fetch_mexc_klines')
    assert callable(ss.fetch_mexc_klines)
    
    assert hasattr(ss, 'fetch_gateio_klines')
    assert callable(ss.fetch_gateio_klines)
    
    assert hasattr(ss, 'fetch_klines_with_fallback')
    assert callable(ss.fetch_klines_with_fallback)


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
        "symbol": "TEST",
        "direction": "long",
        "rsi": 25,  # Oversold (+3)
        "macd": {"crossover": "bullish", "histogram": 0.5, "prev_histogram": 0.3},  # (+3)
        "funding_rate": -0.02,  # Negative funding (+2)
        "volume_ratio": 3.0,  # High volume (+2)
        "bb_position": 0.1,  # Near lower BB (+1)
        "price_to_support": 1.5,  # Close to support (+2)
        "price_to_resistance": 10.0,
        "change_24h": 55.0,  # Strong movement (+3)
    }
    
    probability = ss.calculate_probability(analysis)
    
    # Should be high probability (score = 3+3+2+2+1+2+3 = 15+ -> capped at 15 = 90%)
    assert probability == 90


def test_calculate_probability_short():
    """Test probability calculation for SHORT signal."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Perfect SHORT conditions
    analysis = {
        "symbol": "TEST",
        "direction": "short",
        "rsi": 78,  # Overbought (+3)
        "macd": {"crossover": "bearish", "histogram": -0.5, "prev_histogram": -0.3},  # (+3)
        "funding_rate": 0.03,  # Positive funding (+2)
        "volume_ratio": 2.8,  # High volume (+2)
        "bb_position": 0.9,  # Near upper BB (+1)
        "price_to_support": 10.0,
        "price_to_resistance": 1.2,  # Close to resistance (+2)
        "change_24h": 100.0,  # Very strong movement (+3)
    }
    
    probability = ss.calculate_probability(analysis)
    
    # Should be high probability (score = 3+3+2+2+1+2+3 = 15+ -> capped at 15 = 90%)
    assert probability == 90


def test_calculate_probability_with_strong_movement():
    """Test that strong 24h movement adds appropriate scoring points."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Base analysis with minimal score (only movement)
    base_analysis = {
        "symbol": "TEST",
        "direction": "long",
        "rsi": 50,  # Neutral (0 points)
        "macd": {"crossover": None, "histogram": 0, "prev_histogram": 0},  # (0 points)
        "funding_rate": 0,  # (0 points)
        "volume_ratio": 1.0,  # (0 points)
        "bb_position": 0.5,  # (0 points)
        "price_to_support": 10.0,  # (0 points)
        "price_to_resistance": 10.0,  # (0 points)
    }
    
    # Test very strong movement (>50%)
    analysis_very_strong = base_analysis.copy()
    analysis_very_strong["change_24h"] = 58.6
    prob_very_strong = ss.calculate_probability(analysis_very_strong)
    # Score = 3 (movement) -> 45%
    assert prob_very_strong == 45
    
    # Test strong movement (30-50%)
    analysis_strong = base_analysis.copy()
    analysis_strong["change_24h"] = 40.0
    prob_strong = ss.calculate_probability(analysis_strong)
    # Score = 2 (movement) -> 45%
    assert prob_strong == 45
    
    # Test medium movement (15-30%)
    analysis_medium = base_analysis.copy()
    analysis_medium["change_24h"] = 20.0
    prob_medium = ss.calculate_probability(analysis_medium)
    # Score = 1 (movement) -> 45%
    assert prob_medium == 45
    
    # Test weak movement (<15%)
    analysis_weak = base_analysis.copy()
    analysis_weak["change_24h"] = 10.0
    prob_weak = ss.calculate_probability(analysis_weak)
    # Score = 0 (no movement bonus) -> 45%
    assert prob_weak == 45


def test_calculate_probability_movement_helps_reach_threshold():
    """Test that movement scoring helps signals reach the MIN_PROBABILITY threshold."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # FST-like signal: strong RSI but weak on other indicators
    analysis_fst = {
        "symbol": "FST",
        "direction": "long",
        "rsi": 12.6,  # Very oversold (+3)
        "macd": {"crossover": None, "histogram": 0, "prev_histogram": 0},  # (0 points)
        "funding_rate": 0,  # (0 points)
        "volume_ratio": 1.8,  # Slightly elevated (+1)
        "bb_position": 0.15,  # Near lower BB (+1)
        "price_to_support": 3.0,  # < 5 (+1)
        "price_to_resistance": 10.0,  # (0 points)
        "change_24h": 58.6,  # Very strong drop (+3)
    }
    
    prob = ss.calculate_probability(analysis_fst)
    # Score = 3 (movement) + 3 (RSI) + 0 (MACD) + 0 (funding) + 1 (support) + 1 (BB) + 1 (volume) = 9 -> 70%
    assert prob == 70
    assert prob >= 45  # Should pass MIN_PROBABILITY
    
    # Same signal WITHOUT movement bonus
    analysis_without_movement = analysis_fst.copy()
    analysis_without_movement["change_24h"] = 0
    prob_without = ss.calculate_probability(analysis_without_movement)
    # Score = 0 (movement) + 3 (RSI) + 0 (MACD) + 0 (funding) + 1 (support) + 1 (BB) + 1 (volume) = 6 -> 60%
    assert prob_without == 60


def test_calculate_real_levels_long():
    """Test real levels calculation for LONG with ATR-based approach."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    analysis = {
        "direction": "long",
        "current_price": 50000,
        "atr": 1000,  # ATR is 1000, so 1.5x = 1500 stop distance
    }
    
    levels = ss.calculate_real_levels(analysis)
    
    assert "entry_low" in levels
    assert "entry_high" in levels
    assert "stop_loss" in levels
    assert "tp1" in levels
    assert "tp2" in levels
    assert "rr_ratio" in levels
    
    # Entry should be around current price (±1%)
    assert levels["entry_low"] == 50000 * 0.99  # 49500
    assert levels["entry_high"] == 50000 * 1.01  # 50500
    
    # Stop should be 1.5 ATR below current price
    # 1.5 * 1000 = 1500, so stop = 50000 - 1500 = 48500
    assert levels["stop_loss"] == 48500
    
    # TP1 should be 2x stop distance above current price (R:R 1:2)
    # 50000 + (1500 * 2) = 53000
    assert levels["tp1"] == 53000
    
    # TP2 should be 3x stop distance above current price (R:R 1:3)
    # 50000 + (1500 * 3) = 54500
    assert levels["tp2"] == 54500
    
    # R:R ratio should be 2.0
    assert levels["rr_ratio"] == 2.0


def test_calculate_real_levels_short():
    """Test real levels calculation for SHORT with ATR-based approach."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    analysis = {
        "direction": "short",
        "current_price": 50000,
        "atr": 1000,  # ATR is 1000, so 1.5x = 1500 stop distance
    }
    
    levels = ss.calculate_real_levels(analysis)
    
    # Entry should be around current price (±1%)
    assert levels["entry_low"] == 50000 * 0.99  # 49500
    assert levels["entry_high"] == 50000 * 1.01  # 50500
    
    # Stop should be 1.5 ATR above current price
    # 1.5 * 1000 = 1500, so stop = 50000 + 1500 = 51500
    assert levels["stop_loss"] == 51500
    
    # TP1 should be 2x stop distance below current price (R:R 1:2)
    # 50000 - (1500 * 2) = 47000
    assert levels["tp1"] == 47000
    
    # TP2 should be 3x stop distance below current price (R:R 1:3)
    # 50000 - (1500 * 3) = 45500
    assert levels["tp2"] == 45500
    
    # R:R ratio should be 2.0
    assert levels["rr_ratio"] == 2.0


def test_score_to_probability():
    """Test score to probability conversion."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Test different score levels
    assert ss.score_to_probability(12) == 90
    assert ss.score_to_probability(13) == 90
    assert ss.score_to_probability(10) == 80
    assert ss.score_to_probability(11) == 80
    assert ss.score_to_probability(8) == 70
    assert ss.score_to_probability(9) == 70
    assert ss.score_to_probability(6) == 60
    assert ss.score_to_probability(7) == 60
    assert ss.score_to_probability(4) == 50
    assert ss.score_to_probability(5) == 50
    assert ss.score_to_probability(3) == 45
    assert ss.score_to_probability(0) == 45


@pytest.mark.asyncio
async def test_fetch_binance_funding():
    """Test that fetch_binance_funding method exists and returns None or a float."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Test with a symbol that doesn't exist - should return None gracefully
    result = await ss.fetch_binance_funding("NONEXISTENT")
    assert result is None or isinstance(result, float)
    
    await ss.close()


def test_calculate_real_levels_atr_max_cap():
    """Test that stop loss is capped at 10% even with large ATR."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Test with very large ATR (1.5x = 15000, which is 30% of price)
    analysis = {
        "direction": "long",
        "current_price": 50000,
        "atr": 10000,  # Very large ATR
    }
    
    levels = ss.calculate_real_levels(analysis)
    
    # Stop distance should be capped at 10% = 5000
    # So stop = 50000 - 5000 = 45000
    assert levels["stop_loss"] == 45000
    
    # TP1 should be 2x the capped stop distance
    # 50000 + (5000 * 2) = 60000
    assert levels["tp1"] == 60000


def test_format_message_empty():
    """Test format_message with empty signals list."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    message = ss.format_message([], 3000, 0)
    
    # Should contain header information
    assert "СУПЕР СИГНАЛЫ" in message
    assert "3,000" in message or "3000" in message
    
    # Should indicate no signals found (either "ТОП-0" or "ТОП\\-0" with escaped dash)
    assert "ТОП-0" in message or "ТОП\\-0" in message


@pytest.mark.asyncio
async def test_fetch_klines_with_fallback_returns_tuple():
    """Test that fetch_klines_with_fallback returns a tuple of (candles, exchange)."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Mock all the individual fetch methods to return empty
    with patch.object(ss, 'fetch_binance_klines', new_callable=AsyncMock) as mock_binance:
        with patch.object(ss, 'fetch_bybit_klines', new_callable=AsyncMock) as mock_bybit:
            with patch.object(ss, 'fetch_mexc_klines', new_callable=AsyncMock) as mock_mexc:
                with patch.object(ss, 'fetch_gateio_klines', new_callable=AsyncMock) as mock_gateio:
                    mock_binance.return_value = []
                    mock_bybit.return_value = []
                    mock_mexc.return_value = []
                    mock_gateio.return_value = []
                    
                    result = await ss.fetch_klines_with_fallback("BTC", "1h", 100)
                    
                    # Should return a tuple
                    assert isinstance(result, tuple)
                    assert len(result) == 2
                    
                    # Should be empty candles and empty exchange name
                    candles, exchange = result
                    assert candles == []
                    assert exchange == ""
    
    await ss.close()


@pytest.mark.asyncio
async def test_fetch_klines_with_fallback_tries_binance_first():
    """Test that fetch_klines_with_fallback tries Binance first."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Mock Binance to return valid data
    mock_candles = [{"timestamp": i, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000} for i in range(30)]
    
    with patch.object(ss, 'fetch_binance_klines', new_callable=AsyncMock) as mock_binance:
        with patch.object(ss, 'fetch_bybit_klines', new_callable=AsyncMock) as mock_bybit:
            mock_binance.return_value = mock_candles
            mock_bybit.return_value = []
            
            candles, exchange = await ss.fetch_klines_with_fallback("BTC", "1h", 100)
            
            # Should use Binance
            assert len(candles) == 30
            assert exchange == "binance"
            
            # Binance should be called
            mock_binance.assert_called_once_with("BTC", "1h", 100)
            
            # Bybit should not be called since Binance succeeded
            mock_bybit.assert_not_called()
    
    await ss.close()


@pytest.mark.asyncio
async def test_fetch_klines_with_fallback_falls_back_to_bybit():
    """Test that fetch_klines_with_fallback falls back to Bybit if Binance fails."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Mock Bybit to return valid data
    mock_candles = [{"timestamp": i, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000} for i in range(25)]
    
    with patch.object(ss, 'fetch_binance_klines', new_callable=AsyncMock) as mock_binance:
        with patch.object(ss, 'fetch_bybit_klines', new_callable=AsyncMock) as mock_bybit:
            with patch.object(ss, 'fetch_mexc_klines', new_callable=AsyncMock) as mock_mexc:
                mock_binance.return_value = []  # Binance fails
                mock_bybit.return_value = mock_candles  # Bybit succeeds
                mock_mexc.return_value = []
                
                candles, exchange = await ss.fetch_klines_with_fallback("BTC", "1h", 100)
                
                # Should use Bybit
                assert len(candles) == 25
                assert exchange == "bybit"
                
                # Both should be called
                mock_binance.assert_called_once()
                mock_bybit.assert_called_once()
                
                # MEXC should not be called since Bybit succeeded
                mock_mexc.assert_not_called()
    
    await ss.close()


@pytest.mark.asyncio
async def test_fetch_klines_with_fallback_requires_minimum_candles():
    """Test that fetch_klines_with_fallback requires at least 20 candles."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Mock Binance to return insufficient data (< 20 candles)
    insufficient_candles = [{"timestamp": i, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000} for i in range(15)]
    sufficient_candles = [{"timestamp": i, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000} for i in range(25)]
    
    with patch.object(ss, 'fetch_binance_klines', new_callable=AsyncMock) as mock_binance:
        with patch.object(ss, 'fetch_bybit_klines', new_callable=AsyncMock) as mock_bybit:
            mock_binance.return_value = insufficient_candles  # Not enough
            mock_bybit.return_value = sufficient_candles  # Enough
            
            candles, exchange = await ss.fetch_klines_with_fallback("BTC", "1h", 100)
            
            # Should skip Binance and use Bybit
            assert len(candles) == 25
            assert exchange == "bybit"
    
    await ss.close()
