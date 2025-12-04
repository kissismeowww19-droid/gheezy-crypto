"""
GHEEZY CRYPTO - Multi-API Manager
Балансировка между 3 API для максимальной надежности
CoinGecko - Binance - Kraken

Работает в России БЕЗ VPN
Не требует регистрации
Не требует API ключей
100% бесплатно
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PriceCache:
    """Кэширование цен на случай если все API упали"""
    
    def __init__(self, ttl_minutes: int = 5):
        self. cache = {}
        self. ttl = ttl_minutes
        self.timestamps = {}
    
    def set(self, key: str, value: dict):
        """Сохранить в кэш"""
        self.cache[key] = value
        self.timestamps[key] = datetime. now()
    
    def get(self, key: str) -> Optional[dict]:
        """Получить из кэша если свежий"""
        if key not in self.cache:
            return None
        
        age = datetime.now() - self.timestamps[key]
        if age > timedelta(minutes=self.ttl):
            return None
        
        return self.cache[key]


class MultiAPIManager:
    """
    Менеджер для работы с несколькими API одновременно
    
    Приоритет:
    1. CoinGecko (лучшие данные)
    2. Binance (самый быстрый)
    3.  Kraken (самый надежный)
    """
    
    def __init__(self):
        self.apis = {
            "coingecko": {
                "name": "CoinGecko",
                "priority": 1,
                "url": "https://api.coingecko.com/api/v3/simple/price",
                "timeout": 10,
                "status": "active"
            },
            "binance": {
                "name": "Binance",
                "priority": 2,
                "url": "https://api.binance.com/api/v3/ticker/24hr",
                "timeout": 8,
                "status": "active"
            },
            "kraken": {
                "name": "Kraken",
                "priority": 3,
                "url": "https://api.kraken. com/0/public/Ticker",
                "timeout": 8,
                "status": "active"
            }
        }
        
        self.coin_mapping = {
            "BTC": {"id": "bitcoin", "binance": "BTCUSDT", "kraken": "XBTUSDT"},
            "ETH": {"id": "ethereum", "binance": "ETHUSDT", "kraken": "ETHUSDT"},
            "XRP": {"id": "ripple", "binance": "XRPUSDT", "kraken": "XRPUSDT"},
            "LTC": {"id": "litecoin", "binance": "LTCUSDT", "kraken": "LTCUSDT"},
            "BCH": {"id": "bitcoin-cash", "binance": "BCHUSDT", "kraken": "BCHUSDT"},
            "ADA": {"id": "cardano", "binance": "ADAUSDT", "kraken": "ADAUSDT"},
            "DOT": {"id": "polkadot", "binance": "DOTUSDT", "kraken": "DOTUSDT"},
            "LINK": {"id": "chainlink", "binance": "LINKUSDT", "kraken": "LINKUSDT"},
            "XLM": {"id": "stellar", "binance": "XLMUSDT", "kraken": "XLMUSDT"},
            "DOGE": {"id": "dogecoin", "binance": "DOGEUSDT", "kraken": "DOGEUSDT"},
            "SOL": {"id": "solana", "binance": "SOLUSDT", "kraken": "SOLUSDT"},
            "MATIC": {"id": "matic-network", "binance": "MATICUSDT", "kraken": "MATICUSDT"},
            "AVAX": {"id": "avalanche-2", "binance": "AVAXUSDT", "kraken": "AVAXUSDT"},
            "ATOM": {"id": "cosmos", "binance": "ATOMUSDT", "kraken": "ATOMUSDT"},
            "UNI": {"id": "uniswap", "binance": "UNIUSDT", "kraken": "UNIUSDT"},
            "SHIB": {"id": "shiba-inu", "binance": "SHIBUSDT", "kraken": "SHIBUSDT"},
            "TRX": {"id": "tron", "binance": "TRXUSDT", "kraken": "TRXUSDT"},
            "ETC": {"id": "ethereum-classic", "binance": "ETCUSDT", "kraken": "ETCUSDT"},
            "XMR": {"id": "monero", "binance": "XMRUSDT", "kraken": "XMRUSDT"},
            "TON": {"id": "the-open-network", "binance": "TONUSDT", "kraken": "TONUSDT"},
        }
        
        self.usd_rub_rate = 85.0
        self.usd_eur_rate = 0.92
        
        self.cache = PriceCache(ttl_minutes=5)
        
        self.stats = {
            "coingecko": {"success": 0, "failed": 0, "total_time": 0},
            "binance": {"success": 0, "failed": 0, "total_time": 0},
            "kraken": {"success": 0, "failed": 0, "total_time": 0}
        }
    
    def get_coin_info(self, symbol: str) -> dict:
        """Получить информацию о монете по символу"""
        symbol = symbol.upper()
        if symbol in self.coin_mapping:
            return self.coin_mapping[symbol]
        return {
            "id": symbol. lower(),
            "binance": f"{symbol}USDT",
            "kraken": f"{symbol}USDT"
        }
    
    async def get_from_coingecko(self, coin_id: str) -> Optional[Dict]:
        """CoinGecko API - лучшие данные о монетах"""
        start_time = datetime. now()
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "ids": coin_id. lower(),
                    "vs_currencies": "usd,rub,eur",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                }
                timeout = aiohttp. ClientTimeout(total=10)
                
                async with session. get(
                    self.apis["coingecko"]["url"],
                    params=params,
                    timeout=timeout
                ) as response:
                    if response. status == 200:
                        data = await response.json()
                        if coin_id. lower() in data:
                            coin_data = data[coin_id.lower()]
                            
                            if coin_data.get("usd") and coin_data. get("rub"):
                                self.usd_rub_rate = coin_data["rub"] / coin_data["usd"]
                            
                            self.cache.set(coin_id, coin_data)
                            
                            elapsed = (datetime.now() - start_time).total_seconds()
                            self.stats["coingecko"]["success"] += 1
                            self. stats["coingecko"]["total_time"] += elapsed
                            
                            logger.info(f"CoinGecko: {coin_id} = ${coin_data. get('usd', 0):.2f}")
                            
                            return {
                                "success": True,
                                "source": "CoinGecko",
                                "price_usd": coin_data.get("usd", 0),
                                "price_rub": coin_data.get("rub", 0),
                                "price_eur": coin_data.get("eur", 0),
                                "change_24h": coin_data. get("usd_24h_change", 0),
                                "market_cap": coin_data.get("usd_market_cap", 0),
                                "volume_24h": coin_data.get("usd_24h_vol", 0),
                            }
                    elif response.status == 429:
                        logger.warning("CoinGecko: лимит запросов")
                    else:
                        logger.warning(f"CoinGecko: статус {response.status}")
                        
        except asyncio.TimeoutError:
            self.stats["coingecko"]["failed"] += 1
            logger.warning(f"CoinGecko timeout: {coin_id}")
        except Exception as e:
            self.stats["coingecko"]["failed"] += 1
            logger.error(f"CoinGecko ошибка: {e}")
        
        return None
    
    async def get_from_binance(self, symbol: str) -> Optional[Dict]:
        """Binance API - самый быстрый"""
        start_time = datetime.now()
        
        try:
            async with aiohttp.ClientSession() as session:
                coin_info = self.get_coin_info(symbol)
                binance_symbol = coin_info. get("binance", f"{symbol. upper()}USDT")
                
                params = {"symbol": binance_symbol}
                timeout = aiohttp. ClientTimeout(total=8)
                
                async with session. get(
                    self.apis["binance"]["url"],
                    params=params,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        price_usd = float(data.get("lastPrice", 0))
                        change_24h = float(data.get("priceChangePercent", 0))
                        volume_24h = float(data.get("volume", 0)) * price_usd
                        
                        if price_usd > 0:
                            elapsed = (datetime.now() - start_time).total_seconds()
                            self. stats["binance"]["success"] += 1
                            self. stats["binance"]["total_time"] += elapsed
                            
                            logger.info(f"Binance: {symbol} = ${price_usd:.2f}")
                            
                            return {
                                "success": True,
                                "source": "Binance",
                                "price_usd": price_usd,
                                "price_rub": price_usd * self.usd_rub_rate,
                                "price_eur": price_usd * self.usd_eur_rate,
                                "change_24h": change_24h,
                                "market_cap": 0,
                                "volume_24h": volume_24h,
                            }
                            
        except asyncio.TimeoutError:
            self.stats["binance"]["failed"] += 1
            logger.warning(f"Binance timeout: {symbol}")
        except Exception as e:
            self.stats["binance"]["failed"] += 1
            logger.error(f"Binance ошибка: {e}")
        
        return None
    
    async def get_from_kraken(self, symbol: str) -> Optional[Dict]:
        """Kraken API - самый надежный"""
        start_time = datetime. now()
        
        try:
            async with aiohttp.ClientSession() as session:
                coin_info = self. get_coin_info(symbol)
                kraken_symbol = coin_info.get("kraken", f"{symbol.upper()}USDT")
                
                params = {"pair": kraken_symbol}
                timeout = aiohttp.ClientTimeout(total=8)
                
                async with session.get(
                    self.apis["kraken"]["url"],
                    params=params,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("result") and not data.get("error"):
                            ticker_data = list(data["result"]. values())[0]
                            price_usd = float(ticker_data.get("c", [0])[0])
                            
                            open_price = float(ticker_data.get("o", price_usd))
                            if open_price > 0:
                                change_24h = ((price_usd - open_price) / open_price) * 100
                            else:
                                change_24h = 0
                            
                            volume_24h = float(ticker_data.get("v", [0, 0])[1]) * price_usd
                            
                            if price_usd > 0:
                                elapsed = (datetime.now() - start_time). total_seconds()
                                self.stats["kraken"]["success"] += 1
                                self.stats["kraken"]["total_time"] += elapsed
                                
                                logger.info(f"Kraken: {symbol} = ${price_usd:.2f}")
                                
                                return {
                                    "success": True,
                                    "source": "Kraken",
                                    "price_usd": price_usd,
                                    "price_rub": price_usd * self. usd_rub_rate,
                                    "price_eur": price_usd * self. usd_eur_rate,
                                    "change_24h": change_24h,
                                    "market_cap": 0,
                                    "volume_24h": volume_24h,
                                }
                                
        except asyncio.TimeoutError:
            self.stats["kraken"]["failed"] += 1
            logger. warning(f"Kraken timeout: {symbol}")
        except Exception as e:
            self.stats["kraken"]["failed"] += 1
            logger.error(f"Kraken ошибка: {e}")
        
        return None
    
    async def get_price(self, symbol: str) -> Dict:
        """
        Получить цену монеты с автоматическим fallback
        Порядок: CoinGecko - Binance - Kraken - Кэш
        """
        symbol = symbol.upper()
        coin_info = self.get_coin_info(symbol)
        coin_id = coin_info.get("id", symbol. lower())
        
        logger.info(f"Получаю цену {symbol}...")
        
        result = await self.get_from_coingecko(coin_id)
        if result and result.get("success"):
            return result
        
        result = await self.get_from_binance(symbol)
        if result and result. get("success"):
            return result
        
        result = await self.get_from_kraken(symbol)
        if result and result.get("success"):
            return result
        
        cached = self.cache.get(coin_id)
        if cached:
            logger.warning(f"Используем кэш для {symbol}")
            return {
                "success": True,
                "source": "Cache",
                "price_usd": cached. get("usd", 0),
                "price_rub": cached.get("rub", 0),
                "price_eur": cached.get("eur", 0),
                "change_24h": cached.get("usd_24h_change", 0),
                "market_cap": cached. get("usd_market_cap", 0),
                "volume_24h": cached.get("usd_24h_vol", 0),
            }
        
        logger.error(f"Все API недоступны для {symbol}")
        return {
            "success": False,
            "error": "all_apis_failed",
            "message": "Не удалось получить данные.  Попробуйте позже.",
            "source": "None"
        }
    
    async def get_multiple_prices(self, symbols: list) -> Dict[str, Dict]:
        """Получить цены для нескольких монет одновременно"""
        tasks = [self.get_price(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, dict):
                prices[symbol] = result
            else:
                prices[symbol] = {
                    "success": False,
                    "error": str(result),
                    "source": "None"
                }
        
        return prices
    
    def get_stats(self) -> Dict:
        """Получить статистику API запросов"""
        stats_report = {}
        
        for api_name, stats in self.stats. items():
            total_requests = stats["success"] + stats["failed"]
            if total_requests > 0:
                success_rate = (stats["success"] / total_requests) * 100
                avg_time = stats["total_time"] / stats["success"] if stats["success"] > 0 else 0
            else:
                success_rate = 100
                avg_time = 0
            
            stats_report[api_name] = {
                "name": self.apis[api_name]["name"],
                "success": stats["success"],
                "failed": stats["failed"],
                "success_rate": f"{success_rate:.1f}%",
                "avg_time": f"{avg_time:.2f}s",
                "status": "Active" if stats["failed"] < stats["success"] or total_requests == 0 else "Issues"
            }
        
        return stats_report


api_manager = MultiAPIManager()


async def get_coin_price(symbol: str) -> dict:
    """Получить цену монеты"""
    return await api_manager.get_price(symbol)


async def get_multiple_prices(symbols: list) -> dict:
    """Получить цены нескольких монет"""
    return await api_manager.get_multiple_prices(symbols)


def get_api_stats() -> dict:
    """Получить статистику работы API"""
    return api_manager. get_stats()


if __name__ == "__main__":
    async def test():
        print("")
        print("=" * 50)
        print("GHEEZY CRYPTO - Test Multi-API Manager")
        print("=" * 50)
        
        coins = ["BTC", "ETH", "TON", "SOL", "XRP", "DOGE", "MATIC", "LTC", "SHIB", "AVAX"]
        
        print("")
        print("Getting prices...")
        print("")
        
        for symbol in coins:
            price_data = await get_coin_price(symbol)
            
            if price_data. get("success"):
                print(f"[OK] {symbol}")
                print(f"     USD: ${price_data['price_usd']:,.2f}")
                print(f"     RUB: {price_data['price_rub']:,.2f}")
                print(f"     24h: {price_data['change_24h']:+.2f}%")
                print(f"     Source: {price_data['source']}")
                print("")
            else:
                print(f"[FAIL] {symbol}: {price_data. get('message')}")
                print("")
        
        print("=" * 50)
        print("API STATS")
        print("=" * 50)
        
        stats = get_api_stats()
        for api_name, api_stats in stats. items():
            print(f"")
            print(f"{api_stats['name']}:")
            print(f"  Success: {api_stats['success']}")
            print(f"  Failed: {api_stats['failed']}")
            print(f"  Rate: {api_stats['success_rate']}")
            print(f"  Avg time: {api_stats['avg_time']}")
            print(f"  Status: {api_stats['status']}")
        
        print("")
        print("=" * 50)
        print("TEST COMPLETE!")
        print("=" * 50)
        print("")
    
    asyncio. run(test())