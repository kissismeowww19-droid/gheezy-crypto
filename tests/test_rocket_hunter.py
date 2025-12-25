"""
Test for Rocket Hunter functionality.
"""
import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.rocket_hunter import RocketHunterAnalyzer


@pytest.mark.asyncio
async def test_rocket_hunter_initialization():
    """Test RocketHunterAnalyzer initialization."""
    analyzer = RocketHunterAnalyzer()
    
    assert analyzer.SCAN_LIMIT == 500
    assert analyzer.MIN_SCORE == 7.0
    assert analyzer.MIN_POTENTIAL == 10.0
    assert len(analyzer.EXCLUDED_SYMBOLS) > 0
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_is_valid_symbol():
    """Test symbol validation."""
    analyzer = RocketHunterAnalyzer()
    
    # Valid symbols
    assert analyzer._is_valid_symbol("BTC")
    assert analyzer._is_valid_symbol("ETH")
    assert analyzer._is_valid_symbol("NEWCOIN")
    
    # Invalid symbols
    assert not analyzer._is_valid_symbol("USDT")  # Stablecoin
    assert not analyzer._is_valid_symbol("WBTC")  # Wrapped
    assert not analyzer._is_valid_symbol("BTC.B")  # Has dot
    assert not analyzer._is_valid_symbol("币安人生")  # Non-ASCII
    assert not analyzer._is_valid_symbol("TOO_LONG")  # Has underscore
    assert not analyzer._is_valid_symbol("")  # Empty
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_calculate_volume_ratio():
    """Test volume ratio calculation."""
    analyzer = RocketHunterAnalyzer()
    
    # Normal volume
    candles = [
        {"volume": 100},
        {"volume": 100},
        {"volume": 100},
        {"volume": 100},
    ]
    ratio = analyzer._calculate_volume_ratio(candles)
    assert ratio == pytest.approx(1.0, rel=0.1)
    
    # High volume (10x)
    candles = [
        {"volume": 100},
        {"volume": 100},
        {"volume": 100},
        {"volume": 1000},  # 10x volume
    ]
    ratio = analyzer._calculate_volume_ratio(candles)
    assert ratio == pytest.approx(10.0, rel=0.1)
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_check_bollinger_breakout():
    """Test Bollinger Bands breakout detection."""
    analyzer = RocketHunterAnalyzer()
    
    # Normal prices within bands
    candles = [{"close": 100 + i} for i in range(20)]
    assert not analyzer._check_bollinger_breakout(candles)
    
    # Breakout above upper band
    candles = [{"close": 100} for _ in range(19)]
    candles.append({"close": 200})  # Sudden spike
    assert analyzer._check_bollinger_breakout(candles)
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_calculate_rsi():
    """Test RSI calculation."""
    analyzer = RocketHunterAnalyzer()
    
    # Trending up - should have high RSI
    candles = [{"close": 100 + i * 2} for i in range(20)]
    rsi = analyzer._calculate_rsi(candles)
    assert rsi > 60  # Should be overbought
    
    # Trending down - should have low RSI
    candles = [{"close": 100 - i * 2} for i in range(20)]
    rsi = analyzer._calculate_rsi(candles)
    assert rsi < 40  # Should be oversold
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_check_oi_growing():
    """Test Open Interest growth detection."""
    analyzer = RocketHunterAnalyzer()
    
    # Growing volume (proxy for OI)
    candles = [{"volume": 100} for _ in range(5)]
    candles.extend([{"volume": 150} for _ in range(5)])
    assert analyzer._check_oi_growing(candles)
    
    # Declining volume
    candles = [{"volume": 150} for _ in range(5)]
    candles.extend([{"volume": 100} for _ in range(5)])
    assert not analyzer._check_oi_growing(candles)
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_format_price():
    """Test price formatting."""
    analyzer = RocketHunterAnalyzer()
    
    assert analyzer._format_price(0.00001234) == "$0.00001234"
    assert analyzer._format_price(0.001234) == "$0.001234"
    assert analyzer._format_price(0.1234) == "$0.1234"
    assert analyzer._format_price(12.34) == "$12.34"
    assert analyzer._format_price(1234.56) == "$1,234.56"
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_filter_coins():
    """Test coin filtering."""
    analyzer = RocketHunterAnalyzer()
    
    coins = [
        {
            "symbol": "btc",
            "total_volume": 50000000000,
            "price_change_percentage_24h": 5.0,
        },
        {
            "symbol": "usdt",  # Should be filtered (stablecoin)
            "total_volume": 50000000000,
            "price_change_percentage_24h": 0.1,
        },
        {
            "symbol": "newcoin",
            "total_volume": 500000,  # High enough volume
            "price_change_percentage_24h": 25.0,
        },
        {
            "symbol": "lowvol",
            "total_volume": 50000,  # Too low volume
            "price_change_percentage_24h": 15.0,
        },
    ]
    
    filtered = await analyzer.filter_coins(coins)
    
    # Should keep BTC and NEWCOIN, filter out USDT and LOWVOL
    assert len(filtered) == 2
    symbols = [c["symbol"].upper() for c in filtered]
    assert "BTC" in symbols
    assert "NEWCOIN" in symbols
    assert "USDT" not in symbols
    assert "LOWVOL" not in symbols
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_format_message_no_rockets():
    """Test message formatting when no rockets found."""
    analyzer = RocketHunterAnalyzer()
    
    message = analyzer.format_message([], 500, 250, 60.5)
    
    assert "🚀 *ОХОТНИК ЗА РАКЕТАМИ*" in message
    assert "Просканировано: 500 монет" in message
    assert "Найдено ракет: 0" in message
    assert "Время скана: 1 мин 0 сек" in message
    assert "😔 *Ракет не найдено*" in message
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_format_message_with_rockets():
    """Test message formatting with rockets."""
    analyzer = RocketHunterAnalyzer()
    
    rockets = [
        {
            "symbol": "NEWCOIN",
            "name": "NewCoin",
            "price": 0.0234,
            "change_1h": 8.2,
            "change_24h": 47.2,
            "volume_24h": 47_000_000,
            "market_cap": 50_000_000,
            "funding_rate": 0.00015,
            "oi_growing": True,
            "score": 9.2,
            "direction": "ЛОНГ",
            "direction_emoji": "📈",
            "factors": ["🚀 Огромное движение (+47.2%)", "📊 Высокий объём ($47.0M)"],
            "potential_min": 23,
            "potential_max": 47,
            "exchange": "okx",
        }
    ]
    
    message = analyzer.format_message(rockets, 500, 250, 128.5)
    
    assert "🚀 *ОХОТНИК ЗА РАКЕТАМИ*" in message
    assert "Просканировано: 500 монет" in message
    assert "Найдено ракет: 1" in message
    assert "Время скана: 2 мин 8 сек" in message
    assert "NEWCOIN/USDT" in message
    assert "ЛОНГ" in message
    assert "Score: 9.2/10" in message
    assert "Потенциал: \\+23\\-47%" in message
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_scan_all_coins_retry_logic():
    """Test scan_all_coins retry logic with 401/429 errors."""
    analyzer = RocketHunterAnalyzer()
    
    # Mock response that simulates 401 error then success
    mock_responses = []
    
    # First call: 401 error
    mock_401_resp = AsyncMock()
    mock_401_resp.status = 401
    mock_401_resp.__aenter__ = AsyncMock(return_value=mock_401_resp)
    mock_401_resp.__aexit__ = AsyncMock(return_value=None)
    
    # Second call: success with coins
    mock_200_resp = AsyncMock()
    mock_200_resp.status = 200
    mock_200_resp.json = AsyncMock(return_value=[
        {"symbol": "btc", "total_volume": 50000000000, "price_change_percentage_24h": 5.0, "current_price": 50000}
    ])
    mock_200_resp.__aenter__ = AsyncMock(return_value=mock_200_resp)
    mock_200_resp.__aexit__ = AsyncMock(return_value=None)
    
    # Track which call we're on
    call_count = [0]
    
    def mock_get(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_401_resp
        return mock_200_resp
    
    # Mock the session to limit to 1 page for testing
    with patch.object(analyzer, '_ensure_session', new_callable=AsyncMock):
        analyzer.session = AsyncMock()
        analyzer.session.get = mock_get
        analyzer.session.closed = False
        
        # Temporarily reduce SCAN_LIMIT for faster test
        original_limit = analyzer.SCAN_LIMIT
        analyzer.SCAN_LIMIT = 250
        
        # Mock asyncio.sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            coins = await analyzer.scan_all_coins()
        
        analyzer.SCAN_LIMIT = original_limit
    
    # Should have retried once after 401 and got coins on second attempt
    assert len(coins) == 1
    assert coins[0]["symbol"] == "btc"
    assert call_count[0] == 2  # One failed, one success
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_scan_all_coins_max_retries():
    """Test scan_all_coins stops after max retries."""
    analyzer = RocketHunterAnalyzer()
    
    # Mock response that always returns 401
    mock_401_resp = AsyncMock()
    mock_401_resp.status = 401
    mock_401_resp.__aenter__ = AsyncMock(return_value=mock_401_resp)
    mock_401_resp.__aexit__ = AsyncMock(return_value=None)
    
    call_count = [0]
    
    def mock_get(*args, **kwargs):
        call_count[0] += 1
        return mock_401_resp
    
    # Mock the session
    with patch.object(analyzer, '_ensure_session', new_callable=AsyncMock):
        analyzer.session = AsyncMock()
        analyzer.session.get = mock_get
        analyzer.session.closed = False
        
        # Temporarily reduce SCAN_LIMIT for faster test
        original_limit = analyzer.SCAN_LIMIT
        analyzer.SCAN_LIMIT = 250
        
        # Mock asyncio.sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            coins = await analyzer.scan_all_coins()
        
        analyzer.SCAN_LIMIT = original_limit
    
    # Should have tried max 3 times (initial + 3 retries)
    assert call_count[0] == 4  # 1 initial + 3 retries
    assert len(coins) == 0  # No coins fetched
    
    await analyzer.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
