# BSC and Polygon Rate Limit Fix - Implementation Summary

## Overview

This implementation addresses rate limit issues on BSC, Polygon, and other Etherscan V2 chains by implementing API key rotation and transaction caching. The changes enable the whale tracker to handle 3x more requests per second and prevent duplicate transaction displays.

## What Was Changed

### 1. BSC Migration to Etherscan V2 API

**Problem**: BSC was using Blockscout API which returned 503 errors frequently.

**Solution**: Migrated to Etherscan V2 API with `chainid=56`:
- Primary method: `https://api.etherscan.io/v2/api?chainid=56`
- Fallback: RPC nodes for reliability
- Removed: Blockscout and old BscScan methods

**File**: `src/whale/bsc.py`

### 2. API Key Rotation System

**Problem**: Single API key limited to 3 requests/sec caused "Max calls per sec rate limit reached" errors.

**Solution**: Round-robin rotation of up to 3 API keys:
- Reads from: `ETHERSCAN_API_KEY`, `ETHERSCAN_API_KEY_2`, `ETHERSCAN_API_KEY_3`
- Result: 9 requests/sec (3 keys × 3 req/sec each)
- Includes retry logic for rate limit errors (max 3 attempts)

**Files**: 
- `src/whale/api_keys.py` (new)
- `src/config.py` (updated)
- `src/whale/etherscan_v2.py` (updated)

### 3. Transaction Hash Caching

**Problem**: Duplicate transactions were shown to users.

**Solution**: In-memory FIFO cache with TTL:
- Stores last 1000 transaction hashes
- TTL: 1 hour (3600 seconds)
- Auto-cleanup of expired entries
- Filters duplicates before display

**Files**:
- `src/whale/cache.py` (new)
- `src/whale/tracker.py` (updated)

### 4. Updated All EVM Chain Trackers

Applied API key rotation to all Etherscan V2 chains:
- **Ethereum** (`src/whale/ethereum.py`) - 0.35s delay per request
- **BSC** (`src/whale/bsc.py`) - Etherscan V2 with chainid=56 + 0.35s delay
- **Polygon** (`src/whale/polygon.py`) - 2s startup delay + 0.35s delay per request
- **Arbitrum** (`src/whale/arbitrum.py`) - 0.35s delay per request

**Why different delays?**
- 0.35s between requests = ~3 req/sec (respects Etherscan V2 limit per key)
- Polygon's 2s startup delay prevents collision when all chains start simultaneously

## Configuration

Add to your `.env` file:

```bash
# Primary API key (required)
ETHERSCAN_API_KEY=your_etherscan_api_key

# Optional: Additional keys for rate limit rotation
ETHERSCAN_API_KEY_2=your_second_key
ETHERSCAN_API_KEY_3=your_third_key
```

**Notes**:
- Works with 1, 2, or 3 keys
- More keys = higher rate limit (1 key=3 req/sec, 2 keys=6 req/sec, 3 keys=9 req/sec)
- All keys must be valid Etherscan V2 API keys

## How It Works

### API Key Rotation Flow

```
Request 1 → API_KEY_1
Request 2 → API_KEY_2
Request 3 → API_KEY_3
Request 4 → API_KEY_1 (rotation cycle)
```

Each key has its own 3 req/sec limit, so rotating between them effectively multiplies the throughput.

### Transaction Cache Flow

```
1. Fetch transactions from blockchain
2. Check each tx_hash against cache
3. If NOT in cache:
   - Add to cache
   - Show to user
4. If IN cache:
   - Skip (duplicate)
```

Cache automatically removes entries older than 1 hour.

### Rate Limit Retry Logic

```
1. Make API request
2. If rate limit error:
   - Wait 1 second
   - Retry (max 3 attempts)
3. If still fails:
   - Log error
   - Return empty result
```

## Testing Results

All components have been tested:

✅ **API Key Rotation**
- Round-robin rotation verified
- Correct key sequence: key1 → key2 → key3 → key1
- Works with 1, 2, or 3 keys

✅ **Transaction Cache**
- TTL expiration working (entries expire after 1 hour)
- Max size limit working (keeps last 1000 entries)
- Duplicate filtering working correctly

✅ **Code Quality**
- All files pass ruff linting
- No syntax errors
- Proper imports

## Expected Production Results

After deploying with 3 configured API keys:

1. ✅ **BSC Works** - Uses Etherscan V2 with chainid=56
2. ✅ **No Rate Limit Errors** - 9 req/sec throughput prevents "Max calls per sec" errors
3. ✅ **No Duplicates** - Cache filters out duplicate transactions
4. ✅ **Better Reliability** - Automatic retry on errors
5. ✅ **All 6 Chains Working** - ETH, BSC, BTC, Arbitrum, Polygon, AVAX

## Troubleshooting

### Still seeing rate limit errors?

1. Check that all 3 API keys are configured in `.env`
2. Verify keys are valid Etherscan V2 API keys
3. Check that delays are not being skipped in code

### Transactions not showing?

1. Check that BSC tracker is enabled in `tracker.py`
2. Verify Etherscan V2 API is accessible
3. Check logs for API errors

### Seeing duplicates?

1. Verify transaction cache is initialized in `tracker.py`
2. Check cache size and TTL settings in `cache.py`
3. Ensure `_tx_cache.contains()` is being called in `get_all_transactions()`

## Files Changed

- ✅ `src/whale/api_keys.py` - NEW: API key rotation system
- ✅ `src/whale/cache.py` - NEW: Transaction caching system
- ✅ `src/config.py` - Added 2 additional API key fields
- ✅ `src/whale/etherscan_v2.py` - Centralized key rotation, BSC support
- ✅ `src/whale/bsc.py` - Etherscan V2 migration
- ✅ `src/whale/ethereum.py` - API key rotation
- ✅ `src/whale/polygon.py` - API key rotation
- ✅ `src/whale/arbitrum.py` - API key rotation
- ✅ `src/whale/tracker.py` - Cache integration

## Support

For issues or questions about this implementation:
1. Check the logs for detailed error messages
2. Review this document for configuration guidance
3. Verify API keys are valid and properly configured
4. Check that rate limit delays are being respected

---

**Implementation Date**: December 2025  
**Testing Status**: ✅ All Tests Passed  
**Production Ready**: ✅ Yes
