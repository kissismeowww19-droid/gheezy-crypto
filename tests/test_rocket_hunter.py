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
            "source": "binance",
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
    assert "Источник: Binance" in message  # Check source is displayed
    assert "Данные: Binance \\+ CoinLore \\+ CoinPaprika \\+ CoinGecko" in message  # Check footer
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_scan_all_coins_multi_source():
    """Test scan_all_coins fetches from all 4 sources."""
    analyzer = RocketHunterAnalyzer()
    
    # Mock all four fetch methods
    binance_coins = [
        {"symbol": "BTC", "name": "BTC", "current_price": 50000, 
         "price_change_percentage_24h": 5.0, "price_change_percentage_1h_in_currency": 1.0,
         "total_volume": 50000000000, "market_cap": 1000000000000, "source": "binance"}
    ]
    
    coinlore_coins = [
        {"symbol": "ETH", "name": "Ethereum", "current_price": 3000,
         "price_change_percentage_24h": 3.0, "price_change_percentage_1h_in_currency": 0.5,
         "total_volume": 20000000000, "market_cap": 400000000000, "source": "coinlore"}
    ]
    
    coinpaprika_coins = [
        {"symbol": "ADA", "name": "Cardano", "current_price": 0.5,
         "price_change_percentage_24h": 8.0, "price_change_percentage_1h_in_currency": 2.0,
         "total_volume": 1000000000, "market_cap": 15000000000, "source": "coinpaprika"}
    ]
    
    coingecko_coins = [
        {"symbol": "SOL", "name": "Solana", "current_price": 100,
         "price_change_percentage_24h": 10.0, "price_change_percentage_1h_in_currency": 3.0,
         "total_volume": 5000000000, "market_cap": 50000000000, "source": "coingecko"}
    ]
    
    # Mock the individual fetch methods
    with patch.object(analyzer, 'fetch_binance_gainers', new_callable=AsyncMock, return_value=binance_coins):
        with patch.object(analyzer, 'fetch_coinlore_gainers', new_callable=AsyncMock, return_value=coinlore_coins):
            with patch.object(analyzer, 'fetch_coinpaprika_gainers', new_callable=AsyncMock, return_value=coinpaprika_coins):
                with patch.object(analyzer, 'fetch_coingecko_page1', new_callable=AsyncMock, return_value=coingecko_coins):
                    coins = await analyzer.scan_all_coins()
    
    # Should have all 4 coins
    assert len(coins) == 4
    symbols = [c["symbol"] for c in coins]
    assert "BTC" in symbols
    assert "ETH" in symbols
    assert "ADA" in symbols
    assert "SOL" in symbols
    
    # Check sources are preserved
    sources = [c["source"] for c in coins]
    assert "binance" in sources
    assert "coinlore" in sources
    assert "coinpaprika" in sources
    assert "coingecko" in sources
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_scan_all_coins_deduplication():
    """Test that scan_all_coins removes duplicates with correct priority."""
    analyzer = RocketHunterAnalyzer()
    
    # Same symbol from different sources - Binance should take priority
    binance_coins = [
        {"symbol": "BTC", "name": "BTC", "current_price": 50000, 
         "price_change_percentage_24h": 5.0, "price_change_percentage_1h_in_currency": 1.0,
         "total_volume": 50000000000, "market_cap": 1000000000000, "source": "binance"}
    ]
    
    coinlore_coins = [
        {"symbol": "BTC", "name": "Bitcoin", "current_price": 49900,  # Different price
         "price_change_percentage_24h": 4.8, "price_change_percentage_1h_in_currency": 0.9,
         "total_volume": 48000000000, "market_cap": 990000000000, "source": "coinlore"}
    ]
    
    coinpaprika_coins = [
        {"symbol": "BTC", "name": "Bitcoin", "current_price": 49950,  # Different price
         "price_change_percentage_24h": 4.9, "price_change_percentage_1h_in_currency": 0.95,
         "total_volume": 49000000000, "market_cap": 995000000000, "source": "coinpaprika"}
    ]
    
    coingecko_coins = [
        {"symbol": "BTC", "name": "Bitcoin", "current_price": 50100,  # Different price
         "price_change_percentage_24h": 5.2, "price_change_percentage_1h_in_currency": 1.1,
         "total_volume": 51000000000, "market_cap": 1010000000000, "source": "coingecko"}
    ]
    
    # Mock the individual fetch methods
    with patch.object(analyzer, 'fetch_binance_gainers', new_callable=AsyncMock, return_value=binance_coins):
        with patch.object(analyzer, 'fetch_coinlore_gainers', new_callable=AsyncMock, return_value=coinlore_coins):
            with patch.object(analyzer, 'fetch_coinpaprika_gainers', new_callable=AsyncMock, return_value=coinpaprika_coins):
                with patch.object(analyzer, 'fetch_coingecko_page1', new_callable=AsyncMock, return_value=coingecko_coins):
                    coins = await analyzer.scan_all_coins()
    
    # Should have only 1 BTC (from Binance)
    assert len(coins) == 1
    assert coins[0]["symbol"] == "BTC"
    assert coins[0]["source"] == "binance"
    assert coins[0]["current_price"] == 50000  # Binance price
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_fetch_binance_gainers():
    """Test fetching coins from Binance API."""
    analyzer = RocketHunterAnalyzer()
    
    # Mock Binance API response
    mock_binance_data = [
        {
            "symbol": "BTCUSDT",
            "priceChangePercent": "5.0",
            "lastPrice": "50000.0",
            "quoteVolume": "50000000000"
        },
        {
            "symbol": "ETHUSDT",
            "priceChangePercent": "3.5",
            "lastPrice": "3000.0",
            "quoteVolume": "20000000000"
        },
        {
            "symbol": "ADABTC",  # Should be filtered out (not USDT pair)
            "priceChangePercent": "2.0",
            "lastPrice": "0.00001",
            "quoteVolume": "1000000"
        }
    ]
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_binance_data)
    
    # Create a mock that properly returns itself as a context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_resp
    mock_context_manager.__aexit__.return_value = None
    
    with patch.object(analyzer, '_ensure_session', new_callable=AsyncMock):
        analyzer.session = AsyncMock()
        analyzer.session.get = Mock(return_value=mock_context_manager)
        analyzer.session.closed = False
        
        coins = await analyzer.fetch_binance_gainers()
    
    # Should have 2 coins (ADABTC filtered out)
    assert len(coins) == 2
    assert coins[0]["symbol"] == "BTC"
    assert coins[0]["source"] == "binance"
    assert coins[0]["current_price"] == 50000.0
    assert coins[1]["symbol"] == "ETH"
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_fetch_coinlore_gainers():
    """Test fetching coins from CoinLore API."""
    analyzer = RocketHunterAnalyzer()
    
    # Mock CoinLore API response
    mock_coinlore_data = {
        "data": [
            {
                "symbol": "BTC",
                "name": "Bitcoin",
                "price_usd": "50000.0",
                "percent_change_24h": "5.0",
                "percent_change_1h": "1.0",
                "volume24": 50000000000,
                "market_cap_usd": "1000000000000"
            },
            {
                "symbol": "ETH",
                "name": "Ethereum",
                "price_usd": "3000.0",
                "percent_change_24h": "3.5",
                "percent_change_1h": "0.5",
                "volume24": 20000000000,
                "market_cap_usd": "400000000000"
            }
        ]
    }
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_coinlore_data)
    
    # Create a mock that properly returns itself as a context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_resp
    mock_context_manager.__aexit__.return_value = None
    
    with patch.object(analyzer, '_ensure_session', new_callable=AsyncMock):
        analyzer.session = AsyncMock()
        analyzer.session.get = Mock(return_value=mock_context_manager)
        analyzer.session.closed = False
        
        # Mock asyncio.sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            coins = await analyzer.fetch_coinlore_gainers()
    
    # Should have 2 coins for the first page
    assert len(coins) >= 2
    # Check first page results
    assert any(c["symbol"] == "BTC" for c in coins)
    assert any(c["symbol"] == "ETH" for c in coins)
    btc_coin = next(c for c in coins if c["symbol"] == "BTC")
    assert btc_coin["source"] == "coinlore"
    assert btc_coin["current_price"] == 50000.0
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_fetch_coinpaprika_gainers():
    """Test fetching coins from CoinPaprika API."""
    analyzer = RocketHunterAnalyzer()
    
    # Mock CoinPaprika API response
    mock_coinpaprika_data = [
        {
            "symbol": "BTC",
            "name": "Bitcoin",
            "quotes": {
                "USD": {
                    "price": 50000.0,
                    "percent_change_24h": 5.0,
                    "percent_change_1h": 1.0,
                    "volume_24h": 50000000000,
                    "market_cap": 1000000000000
                }
            }
        },
        {
            "symbol": "ETH",
            "name": "Ethereum",
            "quotes": {
                "USD": {
                    "price": 3000.0,
                    "percent_change_24h": 3.5,
                    "percent_change_1h": 0.5,
                    "volume_24h": 20000000000,
                    "market_cap": 400000000000
                }
            }
        }
    ]
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_coinpaprika_data)
    
    # Create a mock that properly returns itself as a context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_resp
    mock_context_manager.__aexit__.return_value = None
    
    with patch.object(analyzer, '_ensure_session', new_callable=AsyncMock):
        analyzer.session = AsyncMock()
        analyzer.session.get = Mock(return_value=mock_context_manager)
        analyzer.session.closed = False
        
        coins = await analyzer.fetch_coinpaprika_gainers()
    
    assert len(coins) == 2
    assert coins[0]["symbol"] == "BTC"
    assert coins[0]["source"] == "coinpaprika"
    assert coins[0]["current_price"] == 50000.0
    assert coins[1]["symbol"] == "ETH"
    
    await analyzer.close()


@pytest.mark.asyncio
async def test_fetch_coingecko_page1():
    """Test fetching 1 page from CoinGecko API."""
    analyzer = RocketHunterAnalyzer()
    
    # Mock CoinGecko API response
    mock_coingecko_data = [
        {
            "symbol": "btc",
            "name": "Bitcoin",
            "current_price": 50000.0,
            "price_change_percentage_24h": 5.0,
            "price_change_percentage_1h_in_currency": 1.0,
            "total_volume": 50000000000,
            "market_cap": 1000000000000
        },
        {
            "symbol": "eth",
            "name": "Ethereum",
            "current_price": 3000.0,
            "price_change_percentage_24h": 3.5,
            "price_change_percentage_1h_in_currency": 0.5,
            "total_volume": 20000000000,
            "market_cap": 400000000000
        }
    ]
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_coingecko_data)
    
    # Create a mock that properly returns itself as a context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_resp
    mock_context_manager.__aexit__.return_value = None
    
    with patch.object(analyzer, '_ensure_session', new_callable=AsyncMock):
        analyzer.session = AsyncMock()
        analyzer.session.get = Mock(return_value=mock_context_manager)
        analyzer.session.closed = False
        
        coins = await analyzer.fetch_coingecko_page1()
    
    assert len(coins) == 2
    assert coins[0]["symbol"] == "BTC"  # Should be uppercased
    assert coins[0]["source"] == "coingecko"
    assert coins[0]["current_price"] == 50000.0
    assert coins[1]["symbol"] == "ETH"
    
    await analyzer.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
