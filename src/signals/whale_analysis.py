"""
Deep Whale Analysis Module

Provides comprehensive whale activity analysis including:
- Extended whale address tracking
- Per-exchange flow analysis
- Accumulation/Distribution detection
- Stablecoin flow tracking
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


# BTC Top Whale Addresses (Exchanges and Large Holders)
BTC_WHALE_ADDRESSES = [
    # Exchanges
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97",  # Binance Cold Wallet
    "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ",  # Bitfinex Cold Wallet
    "3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6",  # Coinbase Cold Wallet 1
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h",  # Coinbase Cold Wallet 2
    "1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF",  # Kraken Exchange
    "3Kzh9qAqVWQhEsfQz7zEQL1EuSx5tyNLNS",  # Kraken Cold Wallet
    "3FpGRYN27CKNjYSMu9R2n5tq3bWJVxJmPT",  # Huobi Cold Wallet
    "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s",  # Huobi Hot Wallet
    "3Cbq7aT1tY8kMxWLbitaG7yT6bPbKChq64",  # Bittrex Cold Wallet
    "bc1qjasf9z3h7w3jspkhtgatgpyvvzgpa2wwd2lr0eh5tx44reyn2k7sfc27a4",  # Kraken 2
    # OKX
    "1HQ3Go3ggs8pFnXuHVHRytPCq5fGG8Hbhx",  # OKX Cold Wallet
    "3LYJfcfHPXYJreMsASk2jkn69LWEYKzexb",  # OKX Hot Wallet
    # Gemini
    "bc1qxhmdufsvnuaaaer4ynz88fspdsxq2h9e9cetdj",  # Gemini
    "bc1qa5wkgaew2dkv56kfvj49j0av5nml45x9ek9hz6",  # Gemini 2
    # Large Holders
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",  # Unknown Large Holder
    "3LCGsSmfr24demGvriN4e3ft8wEcDuHFqh",  # Unknown Large Holder
    "1LQoWist8KkaUXSPKZHNvEyfrEkPHzSsCd",  # Unknown Large Holder
    "bc1qa5wkgaew2dkv56kfvj49j0av5nml45x9ek9hz6",  # Institutional Holder
    # More Exchange Wallets
    "3BMEXqGpG4FxBA1KWhRFufXfSTRgzfDBhJ",  # Bitstamp
    "38UmuUqPCrFmQo4khkomQwZ4VbY2nZMJ67",  # Bitstamp Cold
    "1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g",  # Bitfinex Hot Wallet
    "bc1qd4k5jm5dj64vj7s8vqqc6z4mtwm5sq3vk2daaa",  # Binance Hot Wallet
    # Mining Pools
    "1CK6KHY6MHgYvmRQ4PAafKYDrg1ejbH1cE",  # F2Pool
    "12tkqA9xSoowkzoERHMWNKsTey55YEBqkv",  # AntPool
    "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",  # SlushPool
]

# ETH Top Whale Addresses (Exchanges and Large Holders)
ETH_WHALE_ADDRESSES = [
    # Ethereum 2.0
    "0x00000000219ab540356cBB839Cbe05303d7705Fa",  # ETH 2.0 Deposit Contract
    # WETH
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH Contract
    # Exchanges
    "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",  # Binance Hot Wallet
    "0x28C6c06298d514Db089934071355E5743bf21d60",  # Binance Hot Wallet 2
    "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",  # Binance Hot Wallet 3
    "0xDFd5293D8e347dFe59E90eFd55b2956a1343963d",  # Binance Hot Wallet 4
    "0x56Eddb7aa87536c09CCc2793473599fD21A8b17F",  # Binance Hot Wallet 5
    "0x9696f59E4d72E237BE84fFD425DCaD154Bf96976",  # Binance Hot Wallet 6
    "0x4E9ce36E442e55EcD9025B9a6E0D88485d628A67",  # Binance Hot Wallet 7
    "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE",  # Binance Hot Wallet 8
    # Coinbase
    "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",  # Coinbase Commerce
    "0x503828976D22510aad0201ac7EC88293211D23Da",  # Coinbase Hot Wallet
    "0xddfAbCdc4D8FfC6d5beaf154f18B778f892A0740",  # Coinbase Cold Wallet
    "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",  # Coinbase Hot Wallet 2
    # Kraken
    "0xae2D4617c862309A3d75A0fFB358c7a5009c673F",  # Kraken Exchange
    "0x53d284357ec70cE289D6D64134DfAc8E511c8a3D",  # Kraken Cold Wallet
    "0x267be1C1D684F78cb4F6a176C4911b741E4Ffdc0",  # Kraken Hot Wallet
    # Bitfinex
    "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",  # Bitfinex Hot Wallet
    "0x876EabF441B2EE5B5b0554Fd502a8E0600950cFa",  # Bitfinex Cold Wallet
    # Huobi
    "0xF977814e90dA44bFA03b6295A0616a897441aceC",  # Huobi Cold Wallet
    "0x18916e1a2933Cb349145A280473A5DE8EB6630cb",  # Huobi Hot Wallet
    # OKX
    "0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b",  # OKX Hot Wallet
    "0x98ec059Dc3aDFBdd63429454aEB0c990FBA4A128",  # OKX Cold Wallet
    # Gemini
    "0xd24400ae8BfEBb18cA49Be86258a3C749cf46853",  # Gemini Hot Wallet
    "0x5f65f7b609678448494De4C87521CdF6cEf1e932",  # Gemini Cold Wallet
    # Large Holders
    "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",  # Unknown Large Holder
    "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a",  # Unknown Large Holder
    "0x06920C9fC643De77B99cB7670A944AD31eaAA260",  # Unknown Large Holder
]

# Exchange mapping for detailed flow analysis
EXCHANGE_ADDRESSES = {
    "binance": {
        "btc": ["bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97", "bc1qd4k5jm5dj64vj7s8vqqc6z4mtwm5sq3vk2daaa"],
        "eth": ["0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8", "0x28C6c06298d514Db089934071355E5743bf21d60", 
                "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549", "0xDFd5293D8e347dFe59E90eFd55b2956a1343963d"]
    },
    "coinbase": {
        "btc": ["3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6", "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h"],
        "eth": ["0x71660c4005BA85c37ccec55d0C4493E66Fe775d3", "0x503828976D22510aad0201ac7EC88293211D23Da", 
                "0xddfAbCdc4D8FfC6d5beaf154f18B778f892A0740", "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503"]
    },
    "kraken": {
        "btc": ["1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF", "3Kzh9qAqVWQhEsfQz7zEQL1EuSx5tyNLNS", 
                "bc1qjasf9z3h7w3jspkhtgatgpyvvzgpa2wwd2lr0eh5tx44reyn2k7sfc27a4"],
        "eth": ["0xae2D4617c862309A3d75A0fFB358c7a5009c673F", "0x53d284357ec70cE289D6D64134DfAc8E511c8a3D", 
                "0x267be1C1D684F78cb4F6a176C4911b741E4Ffdc0"]
    },
    "okx": {
        "btc": ["1HQ3Go3ggs8pFnXuHVHRytPCq5fGG8Hbhx", "3LYJfcfHPXYJreMsASk2jkn69LWEYKzexb"],
        "eth": ["0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b", "0x98ec059Dc3aDFBdd63429454aEB0c990FBA4A128"]
    },
}

# Stablecoin contract addresses
STABLECOIN_ADDRESSES = {
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
}


class DeepWhaleAnalyzer:
    """Deep whale analysis with extended tracking and per-exchange flows."""
    
    def __init__(self):
        self._cache = {}
        self._cache_timestamps = {}
        
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
    
    async def get_exchange_flows_detailed(self, symbol: str, whale_tracker) -> Optional[Dict]:
        """
        Get exchange flows broken down by individual exchanges.
        
        Args:
            symbol: BTC or ETH
            whale_tracker: WhaleTracker instance
            
        Returns:
            Dict with per-exchange flow data:
            {
                "binance": {"inflow": 0, "outflow": 0, "net": 0},
                "coinbase": {"inflow": 0, "outflow": 0, "net": 0},
                "kraken": {"inflow": 0, "outflow": 0, "net": 0},
                "okx": {"inflow": 0, "outflow": 0, "net": 0},
                "total_net": 0,
                "signal": "bullish" | "bearish" | "neutral"
            }
        """
        cache_key = f"exchange_flows_detailed_{symbol}"
        cached = self._get_cache(cache_key, 300)  # 5 min cache
        if cached:
            return cached
        
        try:
            # Map symbol to blockchain
            blockchain_map = {"BTC": "bitcoin", "ETH": "ethereum"}
            blockchain = blockchain_map.get(symbol.upper())
            
            if not blockchain:
                logger.warning(f"Unknown blockchain for symbol: {symbol}")
                return None
            
            # Get recent transactions
            transactions = await whale_tracker.get_transactions_by_blockchain(
                blockchain=blockchain,
                limit=100  # Get more transactions for per-exchange analysis
            )
            
            if not transactions:
                return self._get_empty_exchange_flows()
            
            # Initialize exchange flows
            exchange_flows = {
                "binance": {"inflow": 0.0, "outflow": 0.0, "net": 0.0},
                "coinbase": {"inflow": 0.0, "outflow": 0.0, "net": 0.0},
                "kraken": {"inflow": 0.0, "outflow": 0.0, "net": 0.0},
                "okx": {"inflow": 0.0, "outflow": 0.0, "net": 0.0},
            }
            
            # Process transactions
            for tx in transactions:
                exchange = self._identify_exchange(tx, symbol)
                if not exchange:
                    continue
                
                if tx.is_exchange_deposit:
                    exchange_flows[exchange]["inflow"] += tx.amount_usd
                elif tx.is_exchange_withdrawal:
                    exchange_flows[exchange]["outflow"] += tx.amount_usd
            
            # Calculate net flows and total
            total_net = 0.0
            for exchange in exchange_flows:
                net = exchange_flows[exchange]["outflow"] - exchange_flows[exchange]["inflow"]
                exchange_flows[exchange]["net"] = round(net, 2)
                total_net += net
            
            # Determine signal
            # Negative net (outflow > inflow) = bullish
            # Positive net (inflow > outflow) = bearish
            if total_net < -10_000_000:  # > $10M net outflow
                signal = "bullish"
            elif total_net > 10_000_000:  # > $10M net inflow
                signal = "bearish"
            else:
                signal = "neutral"
            
            result = {
                **exchange_flows,
                "total_net": round(total_net, 2),
                "signal": signal
            }
            
            self._set_cache(cache_key, result)
            logger.info(f"Analyzed detailed exchange flows for {symbol}: {signal}")
            return result
            
        except Exception as e:
            logger.error(f"Error in get_exchange_flows_detailed for {symbol}: {e}")
            return self._get_empty_exchange_flows()
    
    def _identify_exchange(self, tx, symbol: str) -> Optional[str]:
        """Identify which exchange a transaction belongs to."""
        # For now, use transaction metadata if available
        # This is a simplified version - in production, you'd match against address lists
        if hasattr(tx, 'exchange_name') and tx.exchange_name:
            exchange_name = tx.exchange_name.lower()
            if 'binance' in exchange_name:
                return 'binance'
            elif 'coinbase' in exchange_name:
                return 'coinbase'
            elif 'kraken' in exchange_name:
                return 'kraken'
            elif 'okx' in exchange_name or 'okex' in exchange_name:
                return 'okx'
        
        # Fallback to address matching
        address = getattr(tx, 'from_address', None) or getattr(tx, 'to_address', None)
        if not address:
            return None
        
        symbol_lower = symbol.lower()
        for exchange, addresses in EXCHANGE_ADDRESSES.items():
            if symbol_lower in addresses:
                if address in addresses[symbol_lower]:
                    return exchange
        
        return None
    
    def _get_empty_exchange_flows(self) -> Dict:
        """Return empty exchange flows structure."""
        return {
            "binance": {"inflow": 0.0, "outflow": 0.0, "net": 0.0},
            "coinbase": {"inflow": 0.0, "outflow": 0.0, "net": 0.0},
            "kraken": {"inflow": 0.0, "outflow": 0.0, "net": 0.0},
            "okx": {"inflow": 0.0, "outflow": 0.0, "net": 0.0},
            "total_net": 0.0,
            "signal": "neutral"
        }
    
    def detect_accumulation_distribution(self, whale_txs: List) -> Dict:
        """
        Detect accumulation or distribution phase based on whale transaction patterns.
        
        Args:
            whale_txs: List of whale transactions
            
        Returns:
            Dict with phase detection:
            {
                "phase": "accumulation" | "distribution" | "neutral",
                "confidence": 0-100,
                "details": str
            }
        """
        if not whale_txs or len(whale_txs) < 10:
            return {
                "phase": "neutral",
                "confidence": 0,
                "details": "Insufficient data"
            }
        
        # Analyze recent transactions (last 24h)
        now = datetime.now()
        recent_txs = [
            tx for tx in whale_txs 
            if hasattr(tx, 'timestamp') and (now - tx.timestamp) < timedelta(hours=24)
        ]
        
        if not recent_txs:
            recent_txs = whale_txs[:20]  # Fallback to latest 20
        
        # Count deposits vs withdrawals
        deposits = sum(1 for tx in recent_txs if tx.is_exchange_deposit)
        withdrawals = sum(1 for tx in recent_txs if tx.is_exchange_withdrawal)
        
        # Calculate volumes
        deposit_volume = sum(tx.amount_usd for tx in recent_txs if tx.is_exchange_deposit)
        withdrawal_volume = sum(tx.amount_usd for tx in recent_txs if tx.is_exchange_withdrawal)
        
        total_txs = deposits + withdrawals
        total_volume = deposit_volume + withdrawal_volume
        
        if total_txs == 0 or total_volume == 0:
            return {
                "phase": "neutral",
                "confidence": 0,
                "details": "No significant activity"
            }
        
        # Calculate ratios
        withdrawal_ratio = withdrawals / total_txs
        withdrawal_volume_ratio = withdrawal_volume / total_volume
        
        # Accumulation: whales buying and withdrawing from exchanges
        # Strong accumulation: >60% withdrawals by count AND >65% by volume
        # Moderate accumulation: >55% withdrawals by count OR >60% by volume
        if withdrawal_ratio > 0.60 and withdrawal_volume_ratio > 0.65:
            confidence = min(95, int((withdrawal_ratio + withdrawal_volume_ratio) / 2 * 100))
            return {
                "phase": "accumulation",
                "confidence": confidence,
                "details": f"Strong accumulation: {withdrawals}/{total_txs} txs, ${withdrawal_volume/1e6:.1f}M withdrawn"
            }
        elif withdrawal_ratio > 0.55 or withdrawal_volume_ratio > 0.60:
            confidence = min(75, int((withdrawal_ratio + withdrawal_volume_ratio) / 2 * 100))
            return {
                "phase": "accumulation",
                "confidence": confidence,
                "details": f"Moderate accumulation: {withdrawals}/{total_txs} txs, ${withdrawal_volume/1e6:.1f}M withdrawn"
            }
        
        # Distribution: whales selling and depositing to exchanges
        # Strong distribution: >60% deposits by count AND >65% by volume
        # Moderate distribution: >55% deposits by count OR >60% by volume
        deposit_ratio = deposits / total_txs
        deposit_volume_ratio = deposit_volume / total_volume
        
        if deposit_ratio > 0.60 and deposit_volume_ratio > 0.65:
            confidence = min(95, int((deposit_ratio + deposit_volume_ratio) / 2 * 100))
            return {
                "phase": "distribution",
                "confidence": confidence,
                "details": f"Strong distribution: {deposits}/{total_txs} txs, ${deposit_volume/1e6:.1f}M deposited"
            }
        elif deposit_ratio > 0.55 or deposit_volume_ratio > 0.60:
            confidence = min(75, int((deposit_ratio + deposit_volume_ratio) / 2 * 100))
            return {
                "phase": "distribution",
                "confidence": confidence,
                "details": f"Moderate distribution: {deposits}/{total_txs} txs, ${deposit_volume/1e6:.1f}M deposited"
            }
        
        # Neutral: balanced activity
        return {
            "phase": "neutral",
            "confidence": 50,
            "details": f"Balanced activity: {deposits}D/{withdrawals}W txs"
        }
    
    async def get_stablecoin_flows(self) -> Optional[Dict]:
        """
        Track USDT/USDC flows to/from exchanges via Etherscan.
        
        Stablecoins flowing TO exchanges = readiness to buy = bullish
        Stablecoins flowing FROM exchanges = not ready to buy = bearish
        
        Returns:
            Dict:
            {
                "usdt_inflow": 0,
                "usdc_inflow": 0,
                "total_inflow": 0,
                "signal": "bullish" | "bearish" | "neutral"
            }
        """
        cache_key = "stablecoin_flows"
        cached = self._get_cache(cache_key, 600)  # 10 min cache
        if cached:
            return cached
        
        try:
            # This is a placeholder implementation
            # In production, you would:
            # 1. Use Etherscan API to get recent USDT/USDC transfers
            # 2. Filter transfers to/from known exchange addresses
            # 3. Calculate net inflows
            
            # For now, return neutral with explanation
            result = {
                "usdt_inflow": 0.0,
                "usdc_inflow": 0.0,
                "total_inflow": 0.0,
                "signal": "neutral",
                "note": "Etherscan API integration pending"
            }
            
            self._set_cache(cache_key, result)
            logger.info("Stablecoin flow analysis: neutral (not implemented)")
            return result
            
        except Exception as e:
            logger.error(f"Error in get_stablecoin_flows: {e}")
            return {
                "usdt_inflow": 0.0,
                "usdc_inflow": 0.0,
                "total_inflow": 0.0,
                "signal": "neutral",
                "error": str(e)
            }
