"""
Test for SuperSignals logging improvements.
Validates that logging is working correctly for all the new log statements.
"""

import pytest
import logging
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_fetch_klines_with_fallback_logs_binance_success(caplog):
    """Test that fetch_klines_with_fallback logs when Binance succeeds."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Mock Binance to return valid data
    mock_candles = [
        {"timestamp": i, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000}
        for i in range(30)
    ]
    
    with patch.object(ss, 'fetch_binance_klines', new_callable=AsyncMock) as mock_binance:
        mock_binance.return_value = mock_candles
        
        with caplog.at_level(logging.DEBUG):
            candles, exchange = await ss.fetch_klines_with_fallback("BTC", "1h", 100)
            
            # Should log success from Binance
            assert any("BTC: got 30 candles from Binance" in record.message for record in caplog.records)
            assert exchange == "binance"
    
    await ss.close()


@pytest.mark.asyncio
async def test_fetch_klines_with_fallback_logs_all_failed(caplog):
    """Test that fetch_klines_with_fallback logs when all sources fail."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Mock all sources to fail
    with patch.object(ss, 'fetch_binance_klines', new_callable=AsyncMock) as mock_binance:
        with patch.object(ss, 'fetch_bybit_klines', new_callable=AsyncMock) as mock_bybit:
            with patch.object(ss, 'fetch_mexc_klines', new_callable=AsyncMock) as mock_mexc:
                with patch.object(ss, 'fetch_gateio_klines', new_callable=AsyncMock) as mock_gateio:
                    mock_binance.return_value = []
                    mock_bybit.return_value = []
                    mock_mexc.return_value = []
                    mock_gateio.return_value = []
                    
                    with caplog.at_level(logging.WARNING):
                        candles, exchange = await ss.fetch_klines_with_fallback("XYZ", "1h", 100)
                        
                        # Should log warning when all fail
                        assert any("XYZ: ALL kline sources failed!" in record.message for record in caplog.records)
                        assert candles == []
                        assert exchange == ""
    
    await ss.close()


@pytest.mark.asyncio
async def test_deep_analyze_logs_indicators(caplog):
    """Test that deep_analyze logs indicator values."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    coin = {
        "symbol": "TEST",
        "name": "Test Coin",
        "current_price": 100,
        "price_change_percentage_24h": 20,
        "price_change_percentage_1h_in_currency": 2,
        "total_volume": 1000000,
        "market_cap": 10000000,
        "source": "test"
    }
    
    mock_candles = [
        {"timestamp": i, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000}
        for i in range(100)
    ]
    
    with patch.object(ss, 'fetch_klines_with_fallback', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (mock_candles, "binance")
        
        with caplog.at_level(logging.DEBUG):
            result = await ss.deep_analyze(coin)
            
            # Should log indicator values
            assert any(
                "TEST: RSI=" in record.message and 
                "MACD=" in record.message and 
                "Volume=" in record.message
                for record in caplog.records
            )
    
    await ss.close()


@pytest.mark.asyncio
async def test_deep_analyze_logs_rejection(caplog):
    """Test that deep_analyze logs when a coin is rejected."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Create a coin that will fail probability check
    coin = {
        "symbol": "REJECT",
        "name": "Reject Coin",
        "current_price": 100,
        "price_change_percentage_24h": 20,
        "price_change_percentage_1h_in_currency": 0,
        "total_volume": 1000000,
        "market_cap": 10000000,
        "source": "test"
    }
    
    # Mock candles with neutral indicators (will result in low probability)
    mock_candles = [
        {"timestamp": i, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000}
        for i in range(100)
    ]
    
    with patch.object(ss, 'fetch_klines_with_fallback', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (mock_candles, "binance")
        
        with caplog.at_level(logging.INFO):
            result = await ss.deep_analyze(coin)
            
            # Should log rejection with probability and RSI
            rejection_logs = [
                record for record in caplog.records 
                if "probability" in record.message and "skipped" in record.message and "RSI=" in record.message
            ]
            
            # If rejected, should have rejection log
            if result is None:
                assert len(rejection_logs) > 0
    
    await ss.close()


@pytest.mark.asyncio
async def test_scan_logs_summary(caplog):
    """Test that scan() logs analysis summary."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Mock the main methods
    with patch.object(ss, 'fetch_all_coins', new_callable=AsyncMock) as mock_fetch_all:
        with patch.object(ss, 'deep_analyze', new_callable=AsyncMock) as mock_analyze:
            # Return some filtered coins
            mock_fetch_all.return_value = [
                {
                    "symbol": f"COIN{i}",
                    "price_change_percentage_24h": 20 + i,
                    "total_volume": 1000000,
                    "market_cap": 10000000,
                    "current_price": 100
                }
                for i in range(30)
            ]
            
            # Mock analyze to return results for some coins
            def analyze_side_effect(coin):
                if int(coin['symbol'].replace('COIN', '')) % 2 == 0:
                    return {
                        "symbol": coin["symbol"],
                        "probability": 60,
                        "direction": "long"
                    }
                return None
            
            mock_analyze.side_effect = analyze_side_effect
            
            with caplog.at_level(logging.INFO):
                signals = await ss.scan()
                
                # Should log the summary
                summary_logs = [
                    record for record in caplog.records
                    if "Analyzed" in record.message and "coins, accepted" in record.message
                ]
                assert len(summary_logs) > 0
                
                # Check the log message format
                log_message = summary_logs[0].message
                assert "Analyzed 30 coins" in log_message
                assert "accepted" in log_message
    
    await ss.close()


def test_funding_rate_is_not_called():
    """Test that funding rate is not called (removed to avoid blocking)."""
    from signals.super_signals import SuperSignals
    
    ss = SuperSignals()
    
    # Check that the funding rate code has been removed/commented out
    import inspect
    source = inspect.getsource(ss.deep_analyze)
    
    # Should not contain the loop that calls funding rate
    # (the loop would have "for exch_name in" with "okx" somewhere)
    has_funding_loop = "for exch_name in" in source and "okx" in source
    assert not has_funding_loop, "Funding rate loop should be removed"
    
    # Should contain the TODO comment about future implementation
    assert "TODO" in source and "funding" in source.lower()
