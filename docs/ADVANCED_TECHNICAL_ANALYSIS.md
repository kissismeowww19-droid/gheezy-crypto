# Advanced Technical Analysis - Documentation

## Overview

This implementation adds advanced technical analysis capabilities to the Gheezy Crypto AI signal system, upgrading from 1-hour to 4-hour forecast predictions with multi-timeframe consensus and professional-grade indicators.

## New Features

### 1. Multi-Timeframe Analysis (`src/signals/multi_timeframe.py`)

Analyzes price action across three timeframes simultaneously:
- **15 minutes** - Short-term momentum
- **1 hour** - Medium-term trend
- **4 hours** - Long-term direction

**Key Features:**
- Fetches OHLCV candles from Bybit API (free, works in Russia)
- Calculates RSI, MACD, and EMA for each timeframe
- Determines consensus direction (2/3 or 3/3 agreement)
- Built-in caching to reduce API calls

**Usage Example:**
```python
from signals.multi_timeframe import MultiTimeframeAnalyzer

analyzer = MultiTimeframeAnalyzer()
result = await analyzer.analyze_multi_timeframe("BTCUSDT")

# Result structure:
# {
#     "timeframes": {
#         "15m": {"rsi": 65, "direction": "bullish", ...},
#         "1h": {"rsi": 58, "direction": "bullish", ...},
#         "4h": {"rsi": 52, "direction": "neutral", ...}
#     },
#     "consensus": {
#         "direction": "bullish",
#         "strength": 0.66,
#         "text": "2/3 согласие"
#     }
# }
```

### 2. Advanced Technical Indicators (`src/signals/technical_analysis.py`)

Seven professional-grade indicators used by institutional traders:

#### Ichimoku Cloud
- **Tenkan-sen** (Conversion Line): (9-period high + low) / 2
- **Kijun-sen** (Base Line): (26-period high + low) / 2
- **Senkou Span A & B**: Cloud boundaries
- **Signal**: Price position relative to cloud

#### Volume Profile
- **POC** (Point of Control): Price level with maximum volume
- **Value Area High/Low**: 70% volume concentration zone
- **Position**: Current price relative to value area

#### CVD (Cumulative Volume Delta)
- Tracks buy vs sell pressure over time
- Delta = Buy Volume - Sell Volume (based on candle close vs open)
- Identifies accumulation/distribution patterns

#### Market Structure
- **HH** (Higher High) + **HL** (Higher Low) = Bullish trend
- **LH** (Lower High) + **LL** (Lower Low) = Bearish trend
- Detects swing points automatically

#### Order Blocks
- **Bullish OB**: Last bearish candle before upward impulse
- **Bearish OB**: Last bullish candle before downward impulse
- Key institutional entry zones

#### Fair Value Gaps (FVG)
- **Bullish FVG**: low[i] > high[i-2] (gap up)
- **Bearish FVG**: high[i] < low[i-2] (gap down)
- Imbalance zones that may get filled

#### Fibonacci Levels
- Auto-calculated based on swing high/low
- Levels: 0.236, 0.382, 0.5, 0.618, 0.786

**Usage Example:**
```python
from signals.technical_analysis import (
    calculate_ichimoku,
    calculate_volume_profile,
    calculate_cvd
)

# Ichimoku
ichimoku = calculate_ichimoku(highs, lows, closes, current_price)
print(f"Cloud: {ichimoku.cloud_color}, Signal: {ichimoku.signal}")

# Volume Profile
vp = calculate_volume_profile(closes, volumes)
print(f"POC: ${vp.poc}, Position: {vp.get_position(current_price)}")

# CVD
cvd = calculate_cvd(opens, closes, volumes)
print(f"Trend: {cvd.trend}, Signal: {cvd.signal}")
```

### 3. 4-Hour Price Forecast (`src/signals/price_forecast.py`)

Professional risk-reward analysis for 4-hour predictions:

#### ATR-Based Targets
- **Target 1**: Current price ± (ATR × 1.5)
- **Target 2**: Current price ± (ATR × 2.25)
- **Stop Loss**: Current price ∓ (ATR × 1.0)
- **R:R Ratio**: Automatic risk-reward calculation

#### Pivot Points
- **Pivot**: (High + Low + Close) / 3
- **R1**: (2 × Pivot) - Low
- **R2**: Pivot + (High - Low)
- **S1**: (2 × Pivot) - High
- **S2**: Pivot - (High - Low)

#### Scenario Generation
Three probability-weighted scenarios:
- **Bullish**: Target price and trigger level
- **Bearish**: Target price and trigger level
- **Sideways**: Range boundaries

**Usage Example:**
```python
from signals.price_forecast import PriceForecastAnalyzer

analyzer = PriceForecastAnalyzer()

# Calculate ATR targets
targets = analyzer.calculate_atr_targets(
    highs, lows, closes, current_price, "long"
)
print(f"Target 1: ${targets['target1']}, R:R = {targets['risk_reward']}")

# Generate scenarios
scenarios = analyzer.generate_scenarios(
    current_price, "long", signal_strength=75,
    targets, pivot_levels
)
print(f"Bullish: {scenarios['bullish']['probability']}%")
```

## Integration with AI Signals

The new features are fully integrated into `src/signals/ai_signals.py`:

1. **Data Gathering**: Multi-timeframe and advanced indicators are fetched during signal generation
2. **Signal Calculation**: New indicators contribute to the overall signal strength
3. **Message Formatting**: New 4-hour forecast format displays all analysis

### New Message Format

```
🤖 AI СИГНАЛ: BTC (4ч прогноз)
━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 НАПРАВЛЕНИЕ
📈 ЛОНГ (75% вероятность)
Сила: ████████░░ 80%

🎯 ПРОГНОЗ НА 4 ЧАСА
Текущая: $97,500
Цель 1: $98,200 (+0.7%)
Цель 2: $98,650 (+1.2%)
Стоп: $96,900 (-0.6%)
R:R = 1.5

📊 МУЛЬТИ-ТАЙМФРЕЙМ
• 15м: 🟢 bullish (RSI 65)
• 1ч: 🟢 bullish (RSI 58)
• 4ч: 🟡 neutral (RSI 52)
Консенсус: 2/3 согласие

📈 ТЕХНИЧЕСКИЙ АНАЛИЗ
• Ichimoku: bullish (облако bullish)
• VWAP: выше VWAP
• Market Structure: bullish
• Volume Profile: POC $97,300
• CVD: rising
• Order Blocks: bullish OB

🎯 КЛЮЧЕВЫЕ УРОВНИ
📈 R1: $98,100 | R2: $98,900
📉 S1: $96,800 | S2: $96,000

📈 СЦЕНАРИИ
🟢 Бычий: 65% → $98,200
🟡 Боковик: 20% → $96,900-$98,100
🔴 Медвежий: 15% → $96,900

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ Прогноз действителен: 4 часа
📡 Факторов: 22
```

## Technical Specifications

### Data Sources
- **Bybit API**: Free, unlimited, works in Russia
- **Endpoints**:
  - Klines: `https://api.bybit.com/v5/market/kline`
  - Category: `spot`
  - Intervals: 15, 60, 240 (minutes)

### Performance
- **Caching**: 5-minute TTL for candle data
- **API Rate Limit**: 600 requests/minute (Bybit)
- **Calculation Time**: ~200-300ms for all indicators

### Requirements
- Python 3.11+
- aiohttp (async HTTP requests)
- numpy (mathematical calculations)

## Testing

Comprehensive test coverage in `tests/test_advanced_indicators.py`:
- Ichimoku Cloud calculation
- Volume Profile POC detection
- CVD trend analysis
- Market Structure identification
- Order Blocks detection
- FVG detection
- Multi-timeframe consensus
- Price forecast scenarios

Run tests:
```bash
pytest tests/test_advanced_indicators.py -v
```

## Benefits

1. **Higher Quality Signals**: Multi-timeframe consensus reduces false signals
2. **Better Risk Management**: ATR-based targets with R:R ratios
3. **Institutional Indicators**: Professional tools used by large traders
4. **Longer Timeframe**: 4-hour predictions more reliable than 1-hour
5. **Comprehensive Analysis**: 7 new indicators + existing 22 factors = 29 total data points

## Future Enhancements

Potential additions:
- Liquidity heatmaps
- Volume delta analysis
- Smart money concepts (SMC)
- Wyckoff distribution patterns
- Elliott Wave analysis

## References

- Ichimoku: Traditional Japanese chart analysis
- Volume Profile: Market Profile methodology
- Order Blocks: Smart Money Concepts (SMC)
- Fair Value Gaps: ICT (Inner Circle Trader) methodology
