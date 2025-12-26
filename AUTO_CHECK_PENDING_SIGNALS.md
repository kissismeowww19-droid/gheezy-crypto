# Auto-Check Pending Signals Implementation

## Overview

This implementation adds functionality to automatically check ALL pending signals when users interact with the statistics or signal generation features. Previously, signals would remain "pending" indefinitely unless a user requested a NEW signal for the same coin. Now, pending signals are automatically checked and their results are updated.

## Problem Solved

**Before:**
- User has 14 signals in database, all showing as "pending"
- Signals are never checked because checking only happened when requesting a NEW signal for the same coin
- Statistics show inaccurate win/loss ratios

**After:**
- When user clicks "📊 Статистика" button → all pending signals for that coin are checked
- When user selects a coin to generate a signal → pending signals for that coin are checked
- Signals are checked using HISTORICAL prices for the 4-hour period after signal creation
- Statistics now show accurate win/loss ratios

## Implementation Details

### 1. New Methods in `SignalTracker` (`src/signals/signal_tracker.py`)

#### `get_pending_signals(user_id, symbol=None)`
```python
def get_pending_signals(self, user_id: int, symbol: Optional[str] = None) -> List[TrackedSignal]:
```
- Retrieves all pending signals for a user from the database
- Can optionally filter by symbol (e.g., "BTC", "ETH")
- Returns a list of `TrackedSignal` objects

#### `check_all_pending_signals(user_id)`
```python
async def check_all_pending_signals(self, user_id: int) -> Dict:
```
- Checks ALL pending signals for a user
- Only checks signals older than 4 hours
- Uses historical price data to determine win/loss
- Returns summary: `{'checked': 5, 'wins': 3, 'losses': 2, 'still_pending': 1}`

#### `check_pending_signals_for_symbol(user_id, symbol)`
```python
async def check_pending_signals_for_symbol(self, user_id: int, symbol: str) -> Dict:
```
- Same as `check_all_pending_signals` but filtered by symbol
- Used when user selects a specific coin
- Returns summary with counts

#### `_evaluate_signal_result(signal, max_price, min_price)`
```python
def _evaluate_signal_result(signal, max_price, min_price) -> Optional[str]:
```
- Helper method to evaluate signal outcome
- Checks if targets or stop losses were hit
- Updates database with result
- Returns 'win', 'loss', or None

### 2. Updated Bot Handlers (`src/bot.py`)

#### `show_coin_statistics()`
```python
@router.callback_query(lambda c: c.data.startswith("stats_"))
async def show_coin_statistics(callback: CallbackQuery):
```
**Changes:**
- Now calls `check_pending_signals_for_symbol()` before displaying statistics
- Shows alert if any signals were updated: "🔄 Проверено 5 сигналов: ✅ 3 win, ❌ 2 loss"
- Displays updated statistics with accurate win/loss ratios

#### `callback_signal_coin()`
```python
@router.callback_query(lambda c: c.data.startswith("signal_"))
async def callback_signal_coin(callback: CallbackQuery):
```
**Changes:**
- Now calls `check_pending_signals_for_symbol()` before generating new signal
- Logs the results of checked signals
- Continues with signal generation as before

## Signal Evaluation Logic

### For LONG Signals
1. Check if stop loss was hit first (min_price <= stop_loss)
   - If yes → LOSS
2. Check if target was reached (max_price >= target1)
   - If yes → WIN
3. If neither → LOSS (price didn't move enough in 4 hours)

### For SHORT Signals
1. Check if stop loss was hit first (max_price >= stop_loss)
   - If yes → LOSS
2. Check if target was reached (min_price <= target1)
   - If yes → WIN
3. If neither → LOSS (price didn't move enough in 4 hours)

### For SIDEWAYS Signals
1. Check if ALL prices stayed within ±1% range
   - If yes → WIN
   - If no → LOSS

## Example Usage Scenarios

### Scenario 1: User Clicks Statistics
```
1. User has 5 old pending signals (created 5-8 hours ago)
2. User clicks "📊 Статистика" for BTC
3. Bot fetches historical prices for each signal's 4-hour window
4. Bot evaluates results: 3 wins, 2 losses
5. Bot updates database
6. Bot shows alert: "🔄 Проверено 5 сигналов: ✅ 3 win, ❌ 2 loss"
7. Bot displays updated statistics with 60% win rate
```

### Scenario 2: User Requests New Signal
```
1. User has 2 old pending BTC signals
2. User clicks "signal_BTC" to get new signal
3. Bot checks the 2 pending signals first
4. Bot updates their results (1 win, 1 loss)
5. Bot generates new signal as usual
6. All signals are now properly tracked
```

### Scenario 3: Signal Not Old Enough
```
1. User has a signal created 2 hours ago
2. User clicks statistics
3. Bot sees signal is less than 4 hours old
4. Signal remains "pending" (too early to check)
5. Will be checked when it reaches 4 hours
```

## Test Coverage

### Comprehensive Test Suite (`tests/test_check_all_pending_signals.py`)

1. **test_get_pending_signals_all** - Tests retrieving all pending signals
2. **test_get_pending_signals_filtered_by_symbol** - Tests filtering by symbol
3. **test_get_pending_signals_excludes_completed** - Ensures completed signals are excluded
4. **test_check_all_pending_signals_wins** - Tests multiple winning signals
5. **test_check_all_pending_signals_losses** - Tests losing signals
6. **test_check_all_pending_signals_mixed_results** - Tests mixed win/loss scenarios
7. **test_check_all_pending_signals_skips_recent** - Ensures signals <4h are skipped
8. **test_check_pending_signals_for_symbol** - Tests symbol-specific checking
9. **test_check_all_pending_signals_handles_api_failure** - Tests graceful API failure handling
10. **test_check_all_pending_signals_different_users** - Tests user isolation
11. **test_evaluate_signal_result_sideways** - Tests sideways signal evaluation

### Test Results
- ✅ All 11 new tests passing
- ✅ All 9 existing tests passing (no regressions)
- ✅ Manual verification successful
- ✅ CodeQL security scan: 0 vulnerabilities

## Benefits

1. **Accurate Statistics** - Win/loss ratios now reflect actual signal performance
2. **Automatic Updates** - No manual intervention needed to check signals
3. **Historical Accuracy** - Uses actual historical prices, not just current price
4. **User-Friendly** - Shows clear notifications when signals are checked
5. **Robust** - Handles API failures gracefully, signals remain pending on error
6. **Efficient** - Only checks signals older than 4 hours
7. **Scalable** - Works for any number of pending signals

## Technical Notes

- Uses SQLite for persistent storage
- Integrates with existing `api_manager.get_historical_prices()` function
- Backward compatible with existing signal tracking code
- No changes required to database schema
- All datetime operations use ISO format for consistency
- Proper error handling and logging throughout

## Future Enhancements (Not in This PR)

- Add configuration for the 4-hour threshold
- Add background job to check all users' pending signals periodically
- Add email/notification when signals are automatically checked
- Add more detailed analytics on signal performance over time
