# Signal Tracking: Historical Price Check Implementation

## Problem

Previously, the system checked signal results using the **current price** at the time of checking, not the historical prices during the 4-hour signal window. This led to incorrect signal results.

### Example of the Problem:
| Time | Event |
|------|-------|
| 19:00 | LONG signal created, entry $88,000, target $89,320 |
| 19:00 - 23:00 | Price reached $90,000 ✅ (target hit!) |
| 23:00 - 09:00 | Price dropped to $85,000 |
| 09:00 | User checks signal |
| ❌ | System compared with $85,000 → showed **LOSS** |

But the signal was actually a **WIN** because the target was reached within 4 hours!

## Solution

The system now checks signal results using **historical prices** within the 4-hour window after signal creation.

### Implementation Details

#### 1. New API Method (`api_manager.py`)

Added `get_historical_prices()` method to fetch historical price data from CoinGecko:

```python
async def get_historical_prices(
    symbol: str,
    from_timestamp: int,
    to_timestamp: int
) -> Optional[Dict]
```

Uses CoinGecko API endpoint:
```
GET /coins/{id}/market_chart/range
?vs_currency=usd
&from={unix_timestamp_start}
&to={unix_timestamp_end}
```

Returns:
- `min_price`: Minimum price during the period
- `max_price`: Maximum price during the period
- `prices`: List of all price points
- `data_points`: Number of data points

#### 2. Updated Signal Checking Logic (`signal_tracker.py`)

The `check_previous_signal()` method now:

1. **Checks signal maturity**: If signal is < 4 hours old → returns "⏳ В процессе" (pending)
2. **Fetches historical data**: If signal is ≥ 4 hours old → fetches historical prices for the 4-hour window
3. **Determines result** using historical min/max prices:

**For LONG signals:**
```python
if min_price <= stop_loss:
    result = "LOSS"  # Stop was hit first
elif max_price >= target1:
    result = "WIN"   # Target reached
else:
    result = "LOSS"  # Target not reached in 4h
```

**For SHORT signals:**
```python
if max_price >= stop_loss:
    result = "LOSS"  # Stop was hit
elif min_price <= target1:
    result = "WIN"   # Target reached
else:
    result = "LOSS"  # Target not reached
```

**For SIDEWAYS signals:**
```python
# Check if ALL prices stayed within ±1% range
if min_price >= lower_bound and max_price <= upper_bound:
    result = "WIN"
else:
    result = "LOSS"
```

4. **Caches results**: Once a signal result is determined, it's saved in the database and not recalculated
5. **Fallback**: If historical API fails, falls back to current price check (old behavior)

## Key Features

### ⏳ Pending Status
Signals less than 4 hours old show "⏳ В процессе" (In Progress) status, indicating they haven't matured yet.

### 📊 Accurate Historical Checking
Once a signal matures (≥4 hours), the system:
- Fetches historical prices for the exact 4-hour window
- Checks if targets or stop-loss were reached during that period
- Determines the correct win/loss result

### 💾 Result Caching
Once a result is determined:
- Saved to database with `checked_at` timestamp
- Not recalculated on subsequent checks
- Reduces API calls and improves performance

### 🔄 Graceful Fallback
If historical price API fails:
- System falls back to checking with current price
- Logs warning for debugging
- Ensures system continues to work

## Database Changes

No schema changes required! Existing fields are used:
- `result`: Stores "pending", "win", or "loss"
- `exit_price`: Stores the price at which signal completed
- `checked_at`: Timestamp when result was determined

## Testing

### New Test Suite
Created `test_signal_tracker_historical.py` with 9 comprehensive tests:
- ✅ Signals <4 hours return pending
- ✅ Signals ≥4 hours check historical data
- ✅ LONG signal win/loss scenarios
- ✅ SHORT signal win/loss scenarios
- ✅ Stop-loss hit before target
- ✅ Target not reached in 4 hours
- ✅ Result caching
- ✅ API failure fallback
- ✅ Sideways signal checking

### Updated Existing Tests
Updated 19 existing tests to work with new logic:
- Added helper method to create "old" signals for testing
- Mock API calls appropriately
- All tests passing ✅

**Total: 28/28 tests passing**

## User Impact

### Before
```
📊 ПРЕДЫДУЩИЙ СИГНАЛ (10ч 25мин назад)
📈 Направление: LONG
💰 Вход: $88,000
🎯 Цель 1: $89,320 — ❌ Не достигнута
📊 Результат: ❌ УБЫТОК (-3.4%)
```

### After
```
📊 ПРЕДЫДУЩИЙ СИГНАЛ (10ч 25мин назад)
📈 Направление: LONG
💰 Вход: $88,000
🎯 Цель 1: $89,320 — ✅ Достигнута
📊 Результат: ✅ УСПЕХ (+1.5%)
```

The system now accurately reflects that the target was reached during the signal window, even if the current price is lower.

## Files Modified

### Core Implementation
1. **`src/api_manager.py`** - Added `get_historical_prices()` method
2. **`src/signals/signal_tracker.py`** - Completely rewrote `check_previous_signal()` logic

### Tests
3. **`tests/test_signal_tracker_historical.py`** - New comprehensive test suite (385 lines)
4. **`tests/test_signal_tracker.py`** - Updated existing tests
5. **`tests/test_signal_tracking_integration.py`** - Updated integration tests

### Documentation
6. **`HISTORICAL_PRICE_CHECK_IMPLEMENTATION.md`** - This file

## Performance Considerations

- **API Calls**: One CoinGecko API call per mature signal check
- **Caching**: Results cached after first check (no repeated API calls)
- **Rate Limiting**: CoinGecko free tier allows 10-50 calls/minute
- **Fallback**: System works even if API is unavailable

## Future Improvements

Potential enhancements (not implemented yet):
- Background job to check all pending signals periodically
- Notification when signal result is determined
- Multiple timeframe support (1h, 2h, 4h, 8h)
- Alternative historical price providers (fallback APIs)

## Conclusion

The signal tracking system now accurately checks signal results using historical price data, providing users with correct win/loss information based on what actually happened during the 4-hour signal window, not just the current price.

This resolves the issue where winning signals were incorrectly marked as losses due to price movements after the signal window ended.
