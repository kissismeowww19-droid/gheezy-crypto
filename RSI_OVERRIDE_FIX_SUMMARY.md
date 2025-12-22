# Fix Summary: Extreme RSI Override and Consensus Protection

## 🎯 Problem Statement

After PR #83 and #84, AI signals were still showing contradictions. The main issue was demonstrated with an ETH example:

### ETH Example (Real Data):
```
RSI(14): 19 (ОЧЕНЬ перепродан!)    ✅ Должен быть СИЛЬНЫЙ ЛОНГ
Fear & Greed: 25                    ✅ Extreme Fear
Киты: +3 tx с бирж                  ✅ Бычий
Импульс: +7.0/10                    ✅ Бычий
Настроения: +10.0/10                ✅ Бычий
Консенсус: 3 бычьих, 1 медвежий    ✅ БЫЧИЙ

НО итоговый сигнал: ШОРТ 63%       ❌❌❌
```

## 🔍 Root Cause Analysis

Three issues were identified:

1. **Conflict detection threshold too high**: Required 3+ signals but ETH only had 2 strong signals (RSI < 25 and Fear & Greed < 25)
2. **No RSI extreme override**: RSI < 20 is EXTREME oversold and should automatically override
3. **Consensus protection threshold**: May not have been applying correctly to all coins

## ✅ Solution Implemented

### 1. RSI Extreme Override (HIGHEST PRIORITY)

Added new RULE 0 in `_detect_signal_conflicts`:

```python
# ПРАВИЛО 0: RSI EXTREME OVERRIDE (ПРИОРИТЕТ!)
if rsi is not None:
    if rsi < 20:  # Экстремальная перепроданность
        if total_score < 0:
            adjusted_score = abs(total_score) * RSI_EXTREME_OVERRIDE_FACTOR + RSI_EXTREME_OVERRIDE_BOOST
            # Returns immediately, overriding everything else
            return adjusted_score, conflict_note
    
    elif rsi > 80:  # Экстремальная перекупленность
        if total_score > 0:
            adjusted_score = -abs(total_score) * RSI_EXTREME_OVERRIDE_FACTOR - RSI_EXTREME_OVERRIDE_BOOST
            return adjusted_score, conflict_note
```

**Constants added:**
- `RSI_EXTREME_OVERRIDE_FACTOR = 0.3` (more aggressive than normal conflicts)
- `RSI_EXTREME_OVERRIDE_BOOST = 20` (ensures positive/negative signal)

### 2. Lower Conflict Detection Threshold

Changed threshold from 3 to 2 strong signals:

```python
# БЫЛО:
if strong_bullish_signals >= 3 and total_score < 0:

# СТАЛО:
if strong_bullish_signals >= 2 and total_score < 0:
```

This allows conflict detection to trigger with:
- RSI < 25 + Fear & Greed < 25 (2 signals)
- Instead of needing a 3rd strong signal

### 3. Enhanced Consensus Protection

Updated consensus protection with better threshold:

```python
if bullish_count > bearish_count * 2:
    if total_score < -20:  # Only for STRONG bearish signals
        old_score = total_score
        total_score = total_score * 0.3  # Reduce by 70%
        logger.warning(f"Consensus override: ...")
```

**Changes:**
- Added threshold check (score < -20 instead of < 0)
- Now logs old_score for debugging
- Applies to ALL coins (BTC, ETH, TON)

### 4. Comprehensive Logging

Added logging throughout `_detect_signal_conflicts`:

```python
logger.info(f"Conflict detection inputs: rsi={rsi}, fear_greed={fear_greed}, ...")
logger.info(f"Strong signals count: bullish={strong_bullish_signals}, bearish={strong_bearish_signals}")
logger.warning(f"RSI extreme override: RSI={rsi:.1f} < 20, score {total_score:.2f} → {adjusted_score:.2f}")
```

## 📊 Results

### Before Fix:
```
ETH: RSI=19, FG=25, Киты=+3, Консенсус=БЫЧИЙ
→ Signal: ШОРТ 63% ❌
→ Score: -100 (после корреляции: -128)
```

### After Fix:
```
ETH: RSI=19, FG=25, Киты=+3, Консенсус=БЫЧИЙ
→ Signal: ЛОНГ 54% ✅
→ Score: +11.1 (positive, as expected)
```

### Test Results:
- ✅ RSI < 20 extreme override test: PASSED
- ✅ RSI > 80 extreme override test: PASSED
- ✅ 2-signal conflict detection test: PASSED
- ✅ ETH integration test (RSI=19): PASSED (LONG with score 11.1)
- ✅ BTC integration test (RSI=22): PASSED (Sideways with score 5.56)
- ✅ All 16 tests: PASSED

## 🔒 Security

- CodeQL scan: **0 alerts**
- No security vulnerabilities introduced

## 📝 Files Changed

1. `src/signals/ai_signals.py`:
   - Added RSI extreme override logic
   - Lowered conflict detection threshold
   - Enhanced consensus protection
   - Added comprehensive logging
   - Added new constants

2. `tests/test_signal_conflict_detection.py`:
   - Added test for RSI < 20 override
   - Added test for RSI > 80 override
   - Added test for 2-signal threshold

3. `tests/test_eth_example_integration.py` (NEW):
   - Integration test for ETH example (RSI=19)
   - Integration test for BTC example (RSI=22)

## 🎯 Impact

This fix ensures that:

1. **Extreme RSI conditions are always respected**: RSI < 20 or > 80 automatically overrides the signal
2. **Conflict detection is more sensitive**: Triggers with 2 strong signals instead of 3
3. **Consensus protection works consistently**: Applies to all coins (BTC, ETH, TON) with proper thresholds
4. **Better debugging**: Comprehensive logging helps identify signal generation issues

## ✨ Example Scenarios

### Scenario 1: ETH with RSI=19
- **Input**: RSI=19, Fear & Greed=25, Whales=bullish
- **Before**: SHORT 63% (incorrect)
- **After**: LONG 54% (correct) ✅

### Scenario 2: BTC with RSI=82
- **Input**: RSI=82, Strong bullish momentum
- **Before**: LONG (incorrect)
- **After**: SHORT (correct) ✅

### Scenario 3: TON with RSI=22, FG=24
- **Input**: RSI=22, Fear & Greed=24, 2 strong bullish signals
- **Before**: May not trigger conflict detection (needed 3)
- **After**: Triggers conflict detection ✅

## 🚀 Deployment

Changes are backward compatible and require no database migrations. Deploy with standard procedures.
