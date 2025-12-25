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
    
    assert analyzer.SCAN_LIMIT == 3000
    assert analyzer.MIN_SCORE == 7.7
    assert analyzer.MIN_POTENTIAL == 20.0
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
    
    message = analyzer.format_message([], 3000, 500, 120.5)
    
    assert "🚀 *ОХОТНИК ЗА РАКЕТАМИ*" in message
    assert "Просканировано: 3,000 монет" in message
    assert "Найдено ракет: 0" in message
    assert "Время скана: 2 мин 0 сек" in message
    assert "😔 *Ракет не найдено*" in message
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_format_message_with_rockets():
    """Test message formatting with rockets."""
    analyzer = RocketHunterAnalyzer()
    
    rockets = [
        {
            "symbol": "NEWCOIN",
            "price": 0.0234,
            "change_1h": 8.2,
            "change_4h": 15.3,
            "change_24h": 47.2,
            "volume_ratio": 47.0,
            "funding_rate": 0.00015,
            "oi_growing": True,
            "score": 9.2,
            "direction": "ЛОНГ",
            "direction_emoji": "📈",
            "factors": ["📊 Объём взорвался (47x)", "📈 Пробой Bollinger Bands"],
            "potential_min": 47,
            "potential_max": 70,
            "exchange": "okx",
        }
    ]
    
    message = analyzer.format_message(rockets, 3000, 500, 512.5)
    
    assert "🚀 *ОХОТНИК ЗА РАКЕТАМИ*" in message
    assert "Просканировано: 3,000 монет" in message
    assert "Найдено ракет: 1" in message
    assert "Время скана: 8 мин 32 сек" in message
    assert "NEWCOIN/USDT" in message
    assert "ЛОНГ" in message
    assert "Score: 9.2/10" in message
    assert "Потенциал: \\+47\\-70%" in message
    
    await analyzer.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
