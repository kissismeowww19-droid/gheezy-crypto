"""
Data Sources for AI Signals.

8 data sources:
1. WhaleTracker (existing)
2. CoinGecko market_chart (existing)
3. CryptoCompare OHLCV
4. Bybit Spot (Order Book + Trades)
5. Bybit Futures (OI + Long/Short)
6. Alternative.me Fear & Greed (existing)
7. Blockchain.info On-Chain
8. Exchange Flows from WhaleTracker
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class DataSourceManager:
    """Manager for all data sources."""
    
    # Cache TTL for each data source
    CACHE_TTL = {
        "price_history": 300,    # 5 min
        "ohlcv": 300,            # 5 min
        "order_book": 10,        # 10 sec
        "trades": 30,            # 30 sec
        "futures": 60,           # 1 min
        "onchain": 600,          # 10 min
        "fear_greed": 1800,      # 30 min
        "exchange_flows": 300,   # 5 min
    }
    
    # Rate limits (requests per minute)
    RATE_LIMITS = {
        "bybit": 600,
        "coingecko": 10,
        "cryptocompare": 100,
        "blockchain_info": 30,
    }
    
    # Bybit symbol mapping
    BYBIT_MAPPING = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "TON": "TONUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT",
    }
    
    # Threshold for "large" trade in USD
    LARGE_TRADE_THRESHOLD_USD = 100000
    
    def __init__(self):
        """Initialize data source manager."""
        self._cache = {}
        self._cache_timestamps = {}
        self._rate_limit_timestamps = {}
        
    def _get_cache(self, key: str, ttl_seconds: int) -> Optional[Dict]:
        """Get data from cache if still valid."""
        if key not in self._cache:
            return None
        
        age = datetime.now() - self._cache_timestamps.get(key, datetime.min)
        if age > timedelta(seconds=ttl_seconds):
            return None
        
        return self._cache[key]
    
    def _set_cache(self, key: str, value: Dict):
        """Set data in cache."""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()
    
    async def get_ohlcv_data(self, symbol: str, limit: int = 48) -> Optional[List[Dict]]:
        """
        Get OHLCV candles from CryptoCompare.
        API: https://min-api.cryptocompare.com/data/v2/histohour
        
        Args:
            symbol: BTC, ETH, etc.
            limit: Number of hourly candles (default 48)
            
        Returns:
            List[Dict]: [{"open": 97000, "high": 98000, "low": 96500, "close": 97500, 
                         "volumefrom": 1234, "volumeto": 120000000}, ...]
        """
        cache_key = f"ohlcv_{symbol}_{limit}"
        cached_data = self._get_cache(cache_key, self.CACHE_TTL["ohlcv"])
        if cached_data is not None:
            return cached_data
        
        try:
            url = "https://min-api.cryptocompare.com/data/v2/histohour"
            params = {
                "fsym": symbol,
                "tsym": "USD",
                "limit": limit
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("Response") == "Success":
                            candles = data.get("Data", {}).get("Data", [])
                            result = [
                                {
                                    "open": c["open"],
                                    "high": c["high"],
                                    "low": c["low"],
                                    "close": c["close"],
                                    "volumefrom": c["volumefrom"],
                                    "volumeto": c["volumeto"],
                                    "time": c["time"]
                                }
                                for c in candles
                            ]
                            self._set_cache(cache_key, result)
                            logger.info(f"Fetched {len(result)} OHLCV candles for {symbol}")
                            return result
                    
                    logger.warning(f"Failed to fetch OHLCV data for {symbol}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting OHLCV data for {symbol}: {e}")
            return None
    
    async def get_order_book_analysis(self, symbol: str) -> Optional[Dict]:
        """
        Analyze Order Book from Bybit.
        API: https://api.bybit.com/v5/market/orderbook?category=spot&symbol=BTCUSDT&limit=50
        
        Args:
            symbol: BTCUSDT, ETHUSDT, etc.
            
        Returns:
            Dict: {
                "bid_volume": 150.5,
                "ask_volume": 120.3,
                "imbalance": 0.11,
                "spread": 0.01,
                "top_bid": 97500,
                "top_ask": 97510,
                "support_level": 97000,
                "resistance_level": 98000
            }
        """
        cache_key = f"order_book_{symbol}"
        cached_data = self._get_cache(cache_key, self.CACHE_TTL["order_book"])
        if cached_data is not None:
            return cached_data
        
        try:
            url = "https://api.bybit.com/v5/market/orderbook"
            params = {
                "category": "spot",
                "symbol": symbol,
                "limit": 50
            }
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Bybit V5 API structure: result.b (bids) and result.a (asks)
                        result_data = data.get("result", {})
                        bids = result_data.get("b", [])
                        asks = result_data.get("a", [])
                        
                        if not bids or not asks:
                            return None
                        
                        # Calculate volumes (Bybit format: [price, quantity])
                        bid_volume = sum(float(b[1]) for b in bids)
                        ask_volume = sum(float(a[1]) for a in asks)
                        
                        # Calculate imbalance
                        total_volume = bid_volume + ask_volume
                        imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
                        
                        # Calculate spread
                        top_bid = float(bids[0][0])
                        top_ask = float(asks[0][0])
                        spread = ((top_ask - top_bid) / top_bid) * 100
                        
                        # Find support and resistance levels (weighted by volume)
                        support_level = top_bid
                        resistance_level = top_ask
                        
                        result = {
                            "bid_volume": round(bid_volume, 2),
                            "ask_volume": round(ask_volume, 2),
                            "imbalance": round(imbalance, 4),
                            "spread": round(spread, 4),
                            "top_bid": top_bid,
                            "top_ask": top_ask,
                            "support_level": support_level,
                            "resistance_level": resistance_level
                        }
                        
                        self._set_cache(cache_key, result)
                        logger.info(f"Analyzed order book for {symbol}")
                        return result
                    
                    logger.warning(f"Failed to fetch order book for {symbol}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error analyzing order book for {symbol}: {e}")
            return None
    
    async def get_recent_trades_analysis(self, symbol: str) -> Optional[Dict]:
        """
        Analyze recent trades from Bybit.
        API: https://api.bybit.com/v5/market/recent-trade?category=spot&symbol=BTCUSDT&limit=500
        
        Args:
            symbol: BTCUSDT, ETHUSDT, etc.
            
        Returns:
            Dict: {
                "buy_volume": 45.2,
                "sell_volume": 38.1,
                "buy_count": 280,
                "sell_count": 220,
                "large_buys": 5,
                "large_sells": 3
            }
        """
        cache_key = f"trades_{symbol}"
        cached_data = self._get_cache(cache_key, self.CACHE_TTL["trades"])
        if cached_data is not None:
            return cached_data
        
        try:
            url = "https://api.bybit.com/v5/market/recent-trade"
            params = {
                "category": "spot",
                "symbol": symbol,
                "limit": 500
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit trades error: {data.get('retMsg')}")
                            return None
                        
                        trades = data.get("result", {}).get("list", [])
                        
                        if not trades:
                            return None
                        
                        buy_volume = 0.0
                        sell_volume = 0.0
                        buy_count = 0
                        sell_count = 0
                        large_buys = 0
                        large_sells = 0
                        
                        for trade in trades:
                            price = float(trade.get("price", 0))
                            size = float(trade.get("size", 0))
                            side = trade.get("side", "")
                            
                            # Skip invalid trades
                            if price <= 0 or size <= 0 or not side:
                                continue
                            
                            volume_usd = price * size
                            
                            if side == "Buy":
                                buy_volume += size
                                buy_count += 1
                                if volume_usd >= self.LARGE_TRADE_THRESHOLD_USD:
                                    large_buys += 1
                            elif side == "Sell":
                                sell_volume += size
                                sell_count += 1
                                if volume_usd >= self.LARGE_TRADE_THRESHOLD_USD:
                                    large_sells += 1
                            else:
                                # Log unexpected side values for debugging
                                logger.debug(f"Unexpected trade side value: {side} for {symbol}")
                        
                        result = {
                            "buy_volume": round(buy_volume, 4),
                            "sell_volume": round(sell_volume, 4),
                            "buy_count": buy_count,
                            "sell_count": sell_count,
                            "large_buys": large_buys,
                            "large_sells": large_sells
                        }
                        
                        self._set_cache(cache_key, result)
                        logger.info(f"Analyzed {len(trades)} trades for {symbol}")
                        return result
                    
                    logger.warning(f"Failed to fetch trades for {symbol}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error analyzing trades for {symbol}: {e}")
            return None
    
    async def get_futures_data(self, symbol: str) -> Optional[Dict]:
        """
        Get futures data from Bybit.
        APIs:
        - Open Interest: https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=1h
        - Long/Short Ratio: https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=1h
        
        Args:
            symbol: BTCUSDT, ETHUSDT, etc.
            
        Returns:
            Dict: {
                "open_interest": 450000000,
                "open_interest_change": 2.5,
                "long_ratio": 55.2,
                "short_ratio": 44.8,
                "long_short_ratio": 1.23
            }
        """
        cache_key = f"futures_{symbol}"
        cached_data = self._get_cache(cache_key, self.CACHE_TTL["futures"])
        if cached_data is not None:
            return cached_data
        
        try:
            # Get Open Interest
            oi_url = "https://api.bybit.com/v5/market/open-interest"
            oi_params = {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": "1h"
            }
            
            # Get Long/Short Ratio
            ls_url = "https://api.bybit.com/v5/market/account-ratio"
            ls_params = {
                "category": "linear",
                "symbol": symbol,
                "period": "1h",
                "limit": 2
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                # Fetch both in parallel
                oi_task = session.get(oi_url, params=oi_params, timeout=timeout)
                ls_task = session.get(ls_url, params=ls_params, timeout=timeout)
                
                oi_response, ls_response = await asyncio.gather(oi_task, ls_task, return_exceptions=True)
                
                result = {}
                
                # Process Open Interest
                if isinstance(oi_response, aiohttp.ClientResponse) and oi_response.status == 200:
                    oi_data = await oi_response.json()
                    oi_result = oi_data.get("result", {})
                    oi_list = oi_result.get("list", [])
                    if oi_list and len(oi_list) > 0:
                        latest_oi = oi_list[0]
                        oi_value = float(latest_oi.get("openInterest", 0))
                        result["open_interest"] = oi_value
                        
                        # Calculate change if we have multiple data points
                        if len(oi_list) > 1:
                            prev_oi = float(oi_list[1].get("openInterest", 0))
                            if prev_oi > 0:
                                oi_change = ((oi_value - prev_oi) / prev_oi) * 100
                                result["open_interest_change"] = round(oi_change, 2)
                            else:
                                result["open_interest_change"] = 0.0
                        else:
                            result["open_interest_change"] = 0.0
                    else:
                        result["open_interest"] = 0.0
                        result["open_interest_change"] = 0.0
                else:
                    logger.warning(f"Failed to fetch OI for {symbol}")
                    result["open_interest"] = 0.0
                    result["open_interest_change"] = 0.0
                
                # Process Long/Short Ratio
                if isinstance(ls_response, aiohttp.ClientResponse) and ls_response.status == 200:
                    ls_data = await ls_response.json()
                    ls_result = ls_data.get("result", {})
                    ls_list = ls_result.get("list", [])
                    if ls_list and len(ls_list) > 0:
                        latest_ratio_data = ls_list[0]
                        # Bybit returns buyRatio and sellRatio
                        long_ratio = float(latest_ratio_data.get("buyRatio", 0.5))
                        short_ratio = float(latest_ratio_data.get("sellRatio", 0.5))
                        
                        if short_ratio > 0:
                            ls_ratio = long_ratio / short_ratio
                        else:
                            ls_ratio = 1.0
                        
                        result["long_ratio"] = round(long_ratio * 100, 1)
                        result["short_ratio"] = round(short_ratio * 100, 1)
                        result["long_short_ratio"] = round(ls_ratio, 2)
                    else:
                        result["long_ratio"] = 50.0
                        result["short_ratio"] = 50.0
                        result["long_short_ratio"] = 1.0
                else:
                    logger.warning(f"Failed to fetch L/S ratio for {symbol}")
                    result["long_ratio"] = 50.0
                    result["short_ratio"] = 50.0
                    result["long_short_ratio"] = 1.0
                
                self._set_cache(cache_key, result)
                logger.info(f"Fetched futures data for {symbol}")
                return result
        except Exception as e:
            logger.error(f"Error getting futures data for {symbol}: {e}")
            return None
    
    async def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """
        Get Open Interest from Bybit.
        API: https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=1h
        
        Args:
            symbol: BTCUSDT, ETHUSDT, etc.
            
        Returns:
            Dict: {
                "open_interest": 450000000,  # in USD
                "open_interest_change": 2.5  # % change
            }
        """
        cache_key = f"open_interest_{symbol}"
        cached_data = self._get_cache(cache_key, self.CACHE_TTL["futures"])
        if cached_data is not None:
            return cached_data
        
        try:
            url = "https://api.bybit.com/v5/market/open-interest"
            params = {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": "1h"
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        result_data = data.get("result", {})
                        oi_list = result_data.get("list", [])
                        
                        if oi_list and len(oi_list) > 0:
                            latest_oi = oi_list[0]
                            oi_value = float(latest_oi.get("openInterest", 0))
                            
                            # Calculate change if we have multiple data points
                            oi_change = 0.0
                            if len(oi_list) > 1:
                                prev_oi = float(oi_list[1].get("openInterest", 0))
                                if prev_oi > 0:
                                    oi_change = ((oi_value - prev_oi) / prev_oi) * 100
                            
                            result = {
                                "open_interest": oi_value,
                                "open_interest_change": round(oi_change, 2)
                            }
                            
                            self._set_cache(cache_key, result)
                            logger.info(f"Fetched open interest for {symbol}")
                            return result
                    
                    logger.warning(f"Failed to fetch open interest for {symbol}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting open interest for {symbol}: {e}")
            return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        Get Funding Rate from Bybit.
        API: https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1
        
        Args:
            symbol: BTCUSDT, ETHUSDT, etc.
            
        Returns:
            Dict: {
                "rate": 0.0001,
                "rate_percent": 0.01
            }
        """
        cache_key = f"funding_rate_{symbol}"
        cached_data = self._get_cache(cache_key, self.CACHE_TTL["futures"])
        if cached_data is not None:
            return cached_data
        
        try:
            url = "https://api.bybit.com/v5/market/funding/history"
            params = {
                "category": "linear",
                "symbol": symbol,
                "limit": 1
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        result_data = data.get("result", {})
                        funding_list = result_data.get("list", [])
                        
                        if funding_list and len(funding_list) > 0:
                            latest_funding = funding_list[0]
                            funding_rate = float(latest_funding.get("fundingRate", 0))
                            rate_percent = funding_rate * 100
                            
                            result = {
                                "rate": funding_rate,
                                "rate_percent": rate_percent
                            }
                            
                            self._set_cache(cache_key, result)
                            logger.info(f"Fetched funding rate for {symbol}: {rate_percent:.4f}%")
                            return result
                    
                    logger.warning(f"Failed to fetch funding rate for {symbol}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            return None
    
    async def get_long_short_ratio(self, symbol: str) -> Optional[Dict]:
        """
        Get Long/Short Ratio from Bybit.
        API: https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=1h
        
        Args:
            symbol: BTCUSDT, ETHUSDT, etc.
            
        Returns:
            Dict: {
                "long_ratio": 55.2,
                "short_ratio": 44.8,
                "long_short_ratio": 1.23
            }
        """
        cache_key = f"long_short_ratio_{symbol}"
        cached_data = self._get_cache(cache_key, self.CACHE_TTL["futures"])
        if cached_data is not None:
            return cached_data
        
        try:
            url = "https://api.bybit.com/v5/market/account-ratio"
            params = {
                "category": "linear",
                "symbol": symbol,
                "period": "1h",
                "limit": 1
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        result_data = data.get("result", {})
                        ratio_list = result_data.get("list", [])
                        
                        if ratio_list and len(ratio_list) > 0:
                            latest_ratio = ratio_list[0]
                            long_ratio = float(latest_ratio.get("buyRatio", 0.5))
                            short_ratio = float(latest_ratio.get("sellRatio", 0.5))
                            
                            if short_ratio > 0:
                                ls_ratio = long_ratio / short_ratio
                            else:
                                ls_ratio = 1.0
                            
                            result = {
                                "long_ratio": round(long_ratio * 100, 1),
                                "short_ratio": round(short_ratio * 100, 1),
                                "long_short_ratio": round(ls_ratio, 2)
                            }
                            
                            self._set_cache(cache_key, result)
                            logger.info(f"Fetched long/short ratio for {symbol}")
                            return result
                    
                    logger.warning(f"Failed to fetch long/short ratio for {symbol}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting long/short ratio for {symbol}: {e}")
            return None
    
    async def get_btc_onchain_data(self) -> Optional[Dict]:
        """
        Get Bitcoin on-chain data from Blockchain.info.
        APIs:
        - Mempool: https://blockchain.info/q/unconfirmedcount
        - Hashrate: https://blockchain.info/q/hashrate
        
        Returns:
            Dict: {
                "mempool_size": 15000,
                "mempool_status": "normal",
                "hashrate": 550000000000000000000,
                "hashrate_eh": 550.0
            }
        """
        cache_key = "btc_onchain"
        cached_data = self._get_cache(cache_key, self.CACHE_TTL["onchain"])
        if cached_data is not None:
            return cached_data
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                # Fetch mempool and hashrate in parallel
                mempool_task = session.get("https://blockchain.info/q/unconfirmedcount", timeout=timeout)
                hashrate_task = session.get("https://blockchain.info/q/hashrate", timeout=timeout)
                
                mempool_response, hashrate_response = await asyncio.gather(
                    mempool_task, hashrate_task, return_exceptions=True
                )
                
                result = {}
                
                # Process mempool
                if isinstance(mempool_response, aiohttp.ClientResponse) and mempool_response.status == 200:
                    mempool_text = await mempool_response.text()
                    mempool_size = int(mempool_text.strip())
                    result["mempool_size"] = mempool_size
                    
                    # Determine status
                    if mempool_size < 5000:
                        status = "low"
                    elif mempool_size < 20000:
                        status = "normal"
                    else:
                        status = "congested"
                    result["mempool_status"] = status
                else:
                    logger.warning("Failed to fetch mempool size")
                    result["mempool_size"] = 0
                    result["mempool_status"] = "unknown"
                
                # Process hashrate
                if isinstance(hashrate_response, aiohttp.ClientResponse) and hashrate_response.status == 200:
                    hashrate_text = await hashrate_response.text()
                    hashrate = float(hashrate_text.strip())
                    result["hashrate"] = hashrate
                    result["hashrate_eh"] = round(hashrate / 1e18, 2)  # Convert to EH/s
                else:
                    logger.warning("Failed to fetch hashrate")
                    result["hashrate"] = 0
                    result["hashrate_eh"] = 0
                
                self._set_cache(cache_key, result)
                logger.info("Fetched BTC on-chain data")
                return result
        except Exception as e:
            logger.error(f"Error getting BTC on-chain data: {e}")
            return None
    
    async def get_exchange_flows(self, whale_tracker, symbol: str) -> Optional[Dict]:
        """
        Get exchange flows from whale tracker.
        
        Args:
            whale_tracker: WhaleTracker instance
            symbol: BTC, ETH, etc.
            
        Returns:
            Dict: {
                "inflow_count": 5,
                "outflow_count": 10,
                "inflow_volume_usd": 25000000,
                "outflow_volume_usd": 75000000,
                "net_flow_usd": -50000000,
                "flow_trend": "outflow"
            }
        """
        cache_key = f"exchange_flows_{symbol}"
        cached_data = self._get_cache(cache_key, self.CACHE_TTL["exchange_flows"])
        if cached_data is not None:
            return cached_data
        
        try:
            # Map symbol to blockchain
            blockchain_mapping = {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "SOL": "solana",
                "XRP": "ripple",
                "TON": "ton",
            }
            
            blockchain = blockchain_mapping.get(symbol.upper())
            if not blockchain:
                logger.warning(f"Unknown blockchain for symbol: {symbol}")
                return None
            
            # Get transactions
            transactions = await whale_tracker.get_transactions_by_blockchain(
                blockchain=blockchain,
                limit=50
            )
            
            if not transactions:
                return {
                    "inflow_count": 0,
                    "outflow_count": 0,
                    "inflow_volume_usd": 0,
                    "outflow_volume_usd": 0,
                    "net_flow_usd": 0,
                    "flow_trend": "neutral"
                }
            
            inflow_count = 0
            outflow_count = 0
            inflow_volume = 0.0
            outflow_volume = 0.0
            
            for tx in transactions:
                if tx.is_exchange_deposit:
                    inflow_count += 1
                    inflow_volume += tx.amount_usd
                elif tx.is_exchange_withdrawal:
                    outflow_count += 1
                    outflow_volume += tx.amount_usd
            
            net_flow = outflow_volume - inflow_volume
            
            # Determine trend
            if net_flow > inflow_volume * 0.2:  # Net outflow > 20% of inflow
                trend = "outflow"
            elif net_flow < -outflow_volume * 0.2:  # Net inflow > 20% of outflow
                trend = "inflow"
            else:
                trend = "neutral"
            
            result = {
                "inflow_count": inflow_count,
                "outflow_count": outflow_count,
                "inflow_volume_usd": round(inflow_volume, 2),
                "outflow_volume_usd": round(outflow_volume, 2),
                "net_flow_usd": round(net_flow, 2),
                "flow_trend": trend
            }
            
            self._set_cache(cache_key, result)
            logger.info(f"Analyzed exchange flows for {symbol}")
            return result
        except Exception as e:
            logger.error(f"Error getting exchange flows for {symbol}: {e}")
            return None
    
    async def gather_all_data(self, whale_tracker, symbol: str, bybit_symbol: str = None) -> Dict:
        """
        Gather all data sources in parallel.
        
        Args:
            whale_tracker: WhaleTracker instance
            symbol: Coin symbol (BTC, ETH)
            bybit_symbol: Bybit symbol (BTCUSDT, ETHUSDT), auto-mapped if not provided
            
        Returns:
            Dict with all data sources
        """
        try:
            # Auto-map symbol if not provided
            if bybit_symbol is None:
                bybit_symbol = self.BYBIT_MAPPING.get(symbol, f"{symbol}USDT")
            
            # Gather all data sources in parallel
            # Create coroutine for on-chain data (BTC only) or return None
            async def get_onchain_if_btc():
                if symbol == "BTC":
                    return await self.get_btc_onchain_data()
                return None
            
            results = await asyncio.gather(
                self.get_ohlcv_data(symbol),
                self.get_order_book_analysis(bybit_symbol),
                self.get_recent_trades_analysis(bybit_symbol),
                self.get_futures_data(bybit_symbol),
                get_onchain_if_btc(),
                self.get_exchange_flows(whale_tracker, symbol),
                return_exceptions=True
            )
            
            # Process results
            data = {
                "ohlcv": results[0] if not isinstance(results[0], Exception) else None,
                "order_book": results[1] if not isinstance(results[1], Exception) else None,
                "trades": results[2] if not isinstance(results[2], Exception) else None,
                "futures": results[3] if not isinstance(results[3], Exception) else None,
                "onchain": results[4] if not isinstance(results[4], Exception) else None,
                "exchange_flows": results[5] if not isinstance(results[5], Exception) else None,
            }
            
            # Log which data sources succeeded
            success_count = sum(1 for v in data.values() if v is not None)
            logger.info(f"Gathered {success_count}/6 data sources for {symbol}")
            
            return data
        except Exception as e:
            logger.error(f"Error gathering all data for {symbol}: {e}")
            return {}
