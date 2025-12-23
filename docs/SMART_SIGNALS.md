# Smart Signals (Умные Сигналы)

## Overview

Smart Signals is an automated trading signal system that scans 500+ cryptocurrencies from CoinGecko, analyzes them using multiple technical factors, and presents the TOP-3 best opportunities to users.

## Features

### 1. Multi-Exchange Support with Fallback
- **Primary**: OKX (stable from Russia)
- **Fallback #1**: Bybit (good futures data)
- **Fallback #2**: Gate.io (additional fallback)

### 2. Comprehensive Filtering
- Minimum 24h volume: $5M
- Maximum spread: 0.5%
- Minimum market cap: $10M
- Must have trading pair on supported exchanges

### 3. Advanced Scoring System
The scoring algorithm uses a weighted formula:

```
score = (
    0.30 * momentum_4h +      # 4-hour price change (normalized)
    0.20 * momentum_1h +      # 1-hour price change
    0.20 * volume_ratio +     # 24h volume / 20-day average
    0.15 * trend_score +      # EMA crossovers + ADX
    0.15 * volatility_score   # ATR% + Bollinger Bands width
)
```

**Bonuses/Penalties**:
- `-1.0` if funding rate is extreme (overheated market)
- `+0.5` if Open Interest is increasing with price (trend confirmation)
- `-0.5` if BTC correlation < 0.3 (independent movement risk)

All scores are normalized to [0, 10] range.

### 4. Hysteresis Mechanism
Prevents "flickering" in the TOP-3 list:
- Coins stay in TOP-3 for minimum 15 minutes
- New coin must be 10%+ better to replace current one
- Maintains history of last 3-5 updates

### 5. Derivatives Data
- **Funding Rate**: Current and historical
- **Open Interest**: Percentage change
- **Long/Short Ratio**: Market sentiment
- **Liquidations**: If available from exchange

## Usage

### In Telegram Bot

1. Go to main menu
2. Select **🎯 Сигналы** (Signals)
3. Choose **🧠 Умные сигналы (ТОП-3)** (Smart Signals TOP-3)
4. Wait 20-30 seconds for scanning to complete
5. View TOP-3 coins with detailed analysis

### Message Format

For each TOP-3 coin, you'll see:
- Current price and changes (1h, 4h, 24h)
- Volume ratio compared to average
- ATR and Bollinger Bands width (volatility)
- Funding rate and Open Interest change
- Overall score (0-10 with progress bar)
- Key factors contributing to the signal
- Entry, stop-loss, and take-profit levels

## Configuration

Settings in `src/config.py`:

```python
smart_signals_scan_limit = 500           # Number of coins to scan
smart_signals_min_volume = 5_000_000    # Minimum 24h volume (USD)
smart_signals_min_mcap = 10_000_000     # Minimum market cap (USD)
smart_signals_max_spread = 0.005        # Maximum spread (0.5%)
smart_signals_hysteresis_time = 900     # 15 minutes
smart_signals_hysteresis_threshold = 0.10  # 10% difference for replacement
```

## Architecture

### Modules

1. **`src/signals/rate_limiter.py`**
   - Token bucket algorithm for API rate limiting
   - 10 requests/second per exchange

2. **`src/signals/exchanges/`**
   - `okx.py` - OKX exchange client
   - `bybit.py` - Bybit exchange client
   - `gate.py` - Gate.io exchange client
   - Each implements: `get_ohlcv()`, `get_ticker()`, `get_funding_rate()`, `get_open_interest()`, `get_orderbook()`

3. **`src/signals/scoring.py`**
   - Momentum score calculation
   - Volume ratio score
   - Trend score (EMA + ADX)
   - Volatility score (ATR + BB width)
   - Total score aggregation
   - Bonus/penalty application

4. **`src/signals/smart_signals.py`**
   - `SmartSignalAnalyzer` class
   - CoinGecko coin scanning
   - Filtering and scoring
   - TOP-3 selection with hysteresis
   - Message formatting for Telegram

## Error Handling

- **Exchange Unavailable**: Automatically falls back to next exchange in priority list
- **All Exchanges Down**: Shows error message to user
- **API Rate Limits**: Managed by rate limiter to prevent errors
- **Parsing Errors**: Logged with warnings, skips problematic data

## Performance

- **Scan Time**: 20-30 seconds for 500+ coins
- **Parallelism**: Up to 5 concurrent API requests (controlled by semaphore)
- **Caching**: Planned for future optimization
- **Rate Limiting**: 10 req/sec per exchange

## Security

- No API keys required (uses public endpoints)
- All user inputs are escaped for Telegram Markdown
- Rate limiting prevents abuse
- Error messages don't expose sensitive information

## Future Improvements

1. Redis caching for faster subsequent requests
2. WebSocket connections for real-time updates
3. More exchanges (Binance, Coinbase, etc.)
4. Machine learning for score optimization
5. Historical backtesting of signals
6. User preferences (risk tolerance, preferred coins, etc.)
7. Alert system for new signals

## Disclaimer

⚠️ **Not Financial Advice**: Smart Signals is an analytical tool for educational and informational purposes only. It does not constitute financial advice. Always do your own research and consult with financial professionals before making investment decisions.

## License

Part of Gheezy Crypto project. See main LICENSE file for details.
