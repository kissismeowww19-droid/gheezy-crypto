# Fix Summary: Dynamic SCAN_LIMIT Loading

## Problem
The `SCAN_LIMIT` class variable was being initialized at module import time:
```python
SCAN_LIMIT = getattr(settings, 'smart_signals_scan_limit', 500)
```

This could cause issues because:
1. The settings might not be fully loaded when the module is imported
2. The class variable would cache the initial value and not reflect any changes
3. Logs showed only 100 coins being scanned instead of the expected 500

## Solution
Modified the `scan_all_coins()` method to read `scan_limit` dynamically from settings:

```python
async def scan_all_coins(self) -> List[Dict]:
    await self._ensure_session()
    
    all_coins = []
    # Читаем лимит динамически из settings (не из class variable)
    scan_limit = getattr(settings, 'smart_signals_scan_limit', 500)
    max_per_page = 250
    # ...
```

### Changes Made
1. **Line 243-244**: Added dynamic reading of `scan_limit` from settings
2. **Line 253**: Changed `self.SCAN_LIMIT` to `scan_limit` in total_pages calculation
3. **Line 254**: Added logging to show scan parameters: `logger.info(f"Starting scan with limit={scan_limit}, max_per_page={max_per_page}, total_pages={total_pages}")`
4. **Line 263**: Changed `self.SCAN_LIMIT` to `scan_limit` in remaining calculation
5. **Line 404**: Added debug logging for invalid symbols: `logger.debug(f"Symbol {symbol} not found on {exchange_name}, caching as invalid")`

## Expected Behavior After Fix

### Before
```
INFO:signals.smart_signals:Scanned page 1: 100 coins (total: 100)
```

### After
```
INFO:signals.smart_signals:Starting scan with limit=500, max_per_page=250, total_pages=2
INFO:signals.smart_signals:Scanned page 1: 250 coins (total: 250)
INFO:signals.smart_signals:Scanned page 2: 250 coins (total: 500)
INFO:signals.smart_signals:Scanned 500 coins from CoinGecko
INFO:signals.smart_signals:Filtered ~280 coins from 500
```

## Files Modified
- `src/signals/smart_signals.py`: 6 insertions, 2 deletions

## Testing
- ✅ Python syntax validation passed
- ✅ Source code inspection confirmed changes are correct
- ✅ No self.SCAN_LIMIT references remain in scan_all_coins method
- ✅ Code review completed
- ✅ Security scan (CodeQL) passed with 0 alerts

## Notes
- The class variable `SCAN_LIMIT` at line 36 remains for backward compatibility and other potential uses
- The fallback value of 500 matches the default in `config.py` (line 148)
- Russian comments are used consistently with the rest of the codebase
- Debug logging helps troubleshoot API issues without cluttering info logs
