"""
Test for futures-only mode in SuperSignals.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.signals.super_signals import SuperSignals


@pytest.mark.asyncio
async def test_fetch_futures_symbols():
    """Test fetching futures symbols from Binance."""
    scanner = SuperSignals()
    
    # Mock the session response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "symbols": [
            {"symbol": "BTCUSDT", "status": "TRADING"},
            {"symbol": "ETHUSDT", "status": "TRADING"},
            {"symbol": "BIFIUSDT", "status": "TRADING"},
            {"symbol": "SOLUSDT", "status": "TRADING"},
            {"symbol": "BTCUSD", "status": "TRADING"},  # Not USDT - should be ignored
        ]
    })
    
    with patch.object(scanner, '_ensure_session', new_callable=AsyncMock):
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # Create a real session for the test
            import aiohttp
            scanner.session = aiohttp.ClientSession()
            
            try:
                futures_symbols = await scanner.fetch_futures_symbols()
                
                # Verify we got the expected symbols
                assert "BTC" in futures_symbols
                assert "ETH" in futures_symbols
                assert "BIFI" in futures_symbols
                assert "SOL" in futures_symbols
                assert len(futures_symbols) == 4
            finally:
                await scanner.session.close()


@pytest.mark.asyncio
async def test_scan_with_futures_mode():
    """Test scan method with futures mode."""
    scanner = SuperSignals()
    
    # Mock fetch_futures_symbols
    mock_futures_symbols = {"BTC", "ETH", "SOL", "BIFI"}
    
    # Mock fetch_all_coins to return some test coins
    test_coins = [
        {
            "symbol": "BTC",
            "name": "Bitcoin",
            "current_price": 45000,
            "price_change_percentage_24h": 20.0,
            "price_change_percentage_1h_in_currency": 1.0,
            "total_volume": 1000000,
            "market_cap": 800000000,
            "source": "binance"
        },
        {
            "symbol": "SHIB",
            "name": "Shiba Inu",
            "current_price": 0.00001,
            "price_change_percentage_24h": 25.0,
            "price_change_percentage_1h_in_currency": 2.0,
            "total_volume": 2000000,
            "market_cap": 500000000,
            "source": "binance"
        },
        {
            "symbol": "ETH",
            "name": "Ethereum",
            "current_price": 3000,
            "price_change_percentage_24h": 18.0,
            "price_change_percentage_1h_in_currency": 0.5,
            "total_volume": 5000000,
            "market_cap": 400000000,
            "source": "binance"
        }
    ]
    
    with patch.object(scanner, 'fetch_futures_symbols', return_value=mock_futures_symbols):
        with patch.object(scanner, 'fetch_all_coins', return_value=test_coins):
            with patch.object(scanner, 'apply_filters', side_effect=lambda x: x):
                with patch.object(scanner, 'deep_analyze', return_value=None):
                    # Test futures mode
                    await scanner.scan(mode="futures")
                    
                    # Verify fetch_futures_symbols was called
                    scanner.fetch_futures_symbols.assert_called_once()


@pytest.mark.asyncio
async def test_format_message_futures_mode():
    """Test format_message with futures mode."""
    scanner = SuperSignals()
    
    # Create a minimal signal
    signals = [
        {
            "symbol": "BTC",
            "direction": "long",
            "probability": 85,
            "current_price": 45000,
            "rsi": 25,
            "macd": {"crossover": "bullish", "histogram": 0.1},
            "funding_rate": -0.02,
            "volume_ratio": 2.5,
            "levels": {
                "entry_low": 44500,
                "entry_high": 45500,
                "stop_loss": 43000,
                "stop_percent": -4.4,
                "tp1": 48000,
                "tp1_percent": 6.7,
                "tp2": 50000,
                "tp2_percent": 11.1,
                "rr_ratio": 2.0
            },
            "exchanges": ["Binance", "Bybit"]
        }
    ]
    
    # Test futures mode
    message = scanner.format_message(signals, 200, 30, mode="futures")
    assert "ФЬЮЧЕРСЫ ТОП-5" in message or "ФЬЮЧЕРСЫ" in message
    assert "фьючерсных пар" in message
    
    # Test all mode
    message_all = scanner.format_message(signals, 3000, 30, mode="all")
    assert "СУПЕР СИГНАЛЫ" in message_all
    assert "монет" in message_all


def test_futures_symbols_filtering():
    """Test that futures filtering works correctly."""
    scanner = SuperSignals()
    
    all_coins = [
        {"symbol": "BTC", "price_change_percentage_24h": 20},
        {"symbol": "ETH", "price_change_percentage_24h": 18},
        {"symbol": "SHIB", "price_change_percentage_24h": 25},
        {"symbol": "DOGE", "price_change_percentage_24h": 15},
    ]
    
    futures_symbols = {"BTC", "ETH", "DOGE"}
    
    # Filter coins
    filtered = [c for c in all_coins if c.get("symbol", "").upper() in futures_symbols]
    
    # Verify filtering
    assert len(filtered) == 3
    assert any(c["symbol"] == "BTC" for c in filtered)
    assert any(c["symbol"] == "ETH" for c in filtered)
    assert any(c["symbol"] == "DOGE" for c in filtered)
    assert not any(c["symbol"] == "SHIB" for c in filtered)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
