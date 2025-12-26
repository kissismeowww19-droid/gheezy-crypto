"""
GHEEZY CRYPTO - Multi-API Manager
Балансировка между 5 API для максимальной надежности
CoinGecko - CoinPaprika - MEXC - Kraken - Cache

Работает в России БЕЗ VPN
Не требует регистрации
Не требует API ключей
100% бесплатно
"""

import asyncio
import time
import aiohttp
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PriceCache:
    """Кэширование цен на случай если все API упали"""
    
    def __init__(self, ttl_minutes: int = 5):
        self.cache = {}
        self.ttl = ttl_minutes
        self.timestamps = {}
    
    def set(self, key: str, value: dict):
        """Сохранить в кэш"""
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
    
    def get(self, key: str) -> Optional[dict]:
        """Получить из кэша если свежий"""
        if key not in self.cache:
            return None
        
        age = datetime.now() - self.timestamps[key]
        if age > timedelta(minutes=self.ttl):
            return None
        
        return self.cache[key]


class CurrencyRates:
    """
    Получение реальных курсов валют.
    
    Источники (в порядке приоритета):
    1. ЦБ РФ (cbr-xml-daily.ru) — официальный курс для RUB
    2. CoinGecko — для EUR и резерв
    """
    
    CBR_API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
    
    def __init__(self):
        self.usd_rub_rate = 100.0  # Дефолт
        self.usd_eur_rate = 0.95   # Дефолт
        self._last_update = 0
        self._cache_ttl = 3600  # 1 час (курсы ЦБ обновляются раз в день)
    
    async def update_rates(self):
        """Обновить курсы валют от ЦБ РФ."""
        try:
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(self.CBR_API_URL, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        valute = data.get("Valute", {})
                        usd_data = valute.get("USD", {})
                        eur_data = valute.get("EUR", {})
                        
                        if usd_data.get("Value"):
                            self.usd_rub_rate = usd_data["Value"]
                        if eur_data.get("Value") and usd_data.get("Value"):
                            # USD/EUR = USD/RUB / EUR/RUB
                            self.usd_eur_rate = usd_data["Value"] / eur_data["Value"]
                        
                        self._last_update = time.time()
                        logger.info(f"Курсы обновлены: USD/RUB={self.usd_rub_rate:.2f}, USD/EUR={self.usd_eur_rate:.4f}")
        except Exception as e:
            logger.warning(f"Ошибка получения курсов ЦБ РФ: {e}")
    
    def needs_update(self) -> bool:
        """Проверить нужно ли обновить курсы."""
        return time.time() - self._last_update > self._cache_ttl
    
    def get_rub_price(self, usd_price: float) -> float:
        """Получить цену в рублях."""
        return usd_price * self.usd_rub_rate
    
    def get_eur_price(self, usd_price: float) -> float:
        """Получить цену в евро."""
        return usd_price * self.usd_eur_rate


class MultiAPIManager:
    """
    Менеджер для работы с несколькими API одновременно
    
    Приоритет:
    1. CoinGecko (лучшие данные, market cap, volume)
    2. CoinPaprika (бесплатный, надёжный)
    3. MEXC (замена Binance, работает в РФ)
    4. Kraken (резерв)
    5. Cache (если все API недоступны)
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
            "coinpaprika": {
                "name": "CoinPaprika",
                "priority": 2,
                "url": "https://api.coinpaprika.com/v1/tickers",
                "timeout": 10,
                "status": "active"
            },
            "mexc": {
                "name": "MEXC",
                "priority": 3,
                "url": "https://api.mexc.com/api/v3/ticker/24hr",
                "timeout": 8,
                "status": "active"
            },
            "kraken": {
                "name": "Kraken",
                "priority": 4,
                "url": "https://api.kraken.com/0/public/Ticker",
                "timeout": 8,
                "status": "active"
            }
        }
        
        # Cache for historical prices (avoid duplicate requests)
        self._historical_cache: Dict[str, Dict] = {}
        self._cache_ttl = 300  # 5 minutes
        
        # Маппинг монет (34 монеты)
        self.coin_mapping = {
            # Основные монеты (17)
            "BTC": {"id": "bitcoin", "paprika_id": "btc-bitcoin", "mexc": "BTCUSDT", "kraken": "XBTUSDT"},
            "ETH": {"id": "ethereum", "paprika_id": "eth-ethereum", "mexc": "ETHUSDT", "kraken": "ETHUSDT"},
            "TON": {"id": "the-open-network", "paprika_id": "ton-toncoin", "mexc": "TONUSDT", "kraken": "TONUSDT"},
            "SOL": {"id": "solana", "paprika_id": "sol-solana", "mexc": "SOLUSDT", "kraken": "SOLUSDT"},
            "XRP": {"id": "ripple", "paprika_id": "xrp-xrp", "mexc": "XRPUSDT", "kraken": "XRPUSDT"},
            "DOGE": {"id": "dogecoin", "paprika_id": "doge-dogecoin", "mexc": "DOGEUSDT", "kraken": "DOGEUSDT"},
            "MATIC": {"id": "matic-network", "paprika_id": "matic-polygon", "mexc": "MATICUSDT", "kraken": "MATICUSDT"},
            "LTC": {"id": "litecoin", "paprika_id": "ltc-litecoin", "mexc": "LTCUSDT", "kraken": "LTCUSDT"},
            "SHIB": {"id": "shiba-inu", "paprika_id": "shib-shiba-inu", "mexc": "SHIBUSDT", "kraken": "SHIBUSDT"},
            "AVAX": {"id": "avalanche-2", "paprika_id": "avax-avalanche", "mexc": "AVAXUSDT", "kraken": "AVAXUSDT"},
            "BNB": {"id": "binancecoin", "paprika_id": "bnb-binance-coin", "mexc": "BNBUSDT", "kraken": "BNBUSDT"},
            "ADA": {"id": "cardano", "paprika_id": "ada-cardano", "mexc": "ADAUSDT", "kraken": "ADAUSDT"},
            "DOT": {"id": "polkadot", "paprika_id": "dot-polkadot", "mexc": "DOTUSDT", "kraken": "DOTUSDT"},
            "LINK": {"id": "chainlink", "paprika_id": "link-chainlink", "mexc": "LINKUSDT", "kraken": "LINKUSDT"},
            "UNI": {"id": "uniswap", "paprika_id": "uni-uniswap", "mexc": "UNIUSDT", "kraken": "UNIUSDT"},
            "ATOM": {"id": "cosmos", "paprika_id": "atom-cosmos", "mexc": "ATOMUSDT", "kraken": "ATOMUSDT"},
            "TRX": {"id": "tron", "paprika_id": "trx-tron", "mexc": "TRXUSDT", "kraken": "TRXUSDT"},
            
            # Мем-коины (4)
            "NOT": {"id": "notcoin", "paprika_id": "not-notcoin", "mexc": "NOTUSDT", "kraken": "NOTUSDT"},
            "PEPE": {"id": "pepe", "paprika_id": "pepe-pepe", "mexc": "PEPEUSDT", "kraken": "PEPEUSDT"},
            "WIF": {"id": "dogwifcoin", "paprika_id": "wif-dogwifhat", "mexc": "WIFUSDT", "kraken": "WIFUSDT"},
            "BONK": {"id": "bonk", "paprika_id": "bonk-bonk", "mexc": "BONKUSDT", "kraken": "BONKUSDT"},
            
            # Новые L1 блокчейны (5)
            "SUI": {"id": "sui", "paprika_id": "sui-sui", "mexc": "SUIUSDT", "kraken": "SUIUSDT"},
            "APT": {"id": "aptos", "paprika_id": "apt-aptos", "mexc": "APTUSDT", "kraken": "APTUSDT"},
            "SEI": {"id": "sei-network", "paprika_id": "sei-sei", "mexc": "SEIUSDT", "kraken": "SEIUSDT"},
            "NEAR": {"id": "near", "paprika_id": "near-near-protocol", "mexc": "NEARUSDT", "kraken": "NEARUSDT"},
            "FTM": {"id": "fantom", "paprika_id": "ftm-fantom", "mexc": "FTMUSDT", "kraken": "FTMUSDT"},
            
            # L2 Ethereum (2)
            "ARB": {"id": "arbitrum", "paprika_id": "arb-arbitrum", "mexc": "ARBUSDT", "kraken": "ARBUSDT"},
            "OP": {"id": "optimism", "paprika_id": "op-optimism", "mexc": "OPUSDT", "kraken": "OPUSDT"},
            
            # DeFi и другие (6)
            "INJ": {"id": "injective-protocol", "paprika_id": "inj-injective", "mexc": "INJUSDT", "kraken": "INJUSDT"},
            "XLM": {"id": "stellar", "paprika_id": "xlm-stellar", "mexc": "XLMUSDT", "kraken": "XLMUSDT"},
            "VET": {"id": "vechain", "paprika_id": "vet-vechain", "mexc": "VETUSDT", "kraken": "VETUSDT"},
            "ALGO": {"id": "algorand", "paprika_id": "algo-algorand", "mexc": "ALGOUSDT", "kraken": "ALGOUSDT"},
            "FIL": {"id": "filecoin", "paprika_id": "fil-filecoin", "mexc": "FILUSDT", "kraken": "FILUSDT"},
            "RUNE": {"id": "thorchain", "paprika_id": "rune-thorchain", "mexc": "RUNEUSDT", "kraken": "RUNEUSDT"},
        }
        
        # Инициализация CurrencyRates
        self.currency_rates = CurrencyRates()
        
        self.cache = PriceCache(ttl_minutes=5)
        
        self.stats = {
            "coingecko": {"success": 0, "failed": 0, "total_time": 0},
            "coinpaprika": {"success": 0, "failed": 0, "total_time": 0},
            "mexc": {"success": 0, "failed": 0, "total_time": 0},
            "kraken": {"success": 0, "failed": 0, "total_time": 0}
        }
    
    def get_coin_info(self, symbol: str) -> dict:
        """Получить информацию о монете по символу"""
        symbol = symbol.upper()
        if symbol in self.coin_mapping:
            return self.coin_mapping[symbol]
        return {
            "id": symbol.lower(),
            "paprika_id": f"{symbol.lower()}-{symbol.lower()}",
            "mexc": f"{symbol}USDT",
            "kraken": f"{symbol}USDT"
        }
    
    async def get_from_coingecko(self, coin_id: str) -> Optional[Dict]:
        """CoinGecko API - лучшие данные о монетах"""
        start_time = datetime.now()
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "ids": coin_id.lower(),
                    "vs_currencies": "usd,rub,eur",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                }
                timeout = aiohttp.ClientTimeout(total=10)
                
                async with session.get(
                    self.apis["coingecko"]["url"],
                    params=params,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if coin_id.lower() in data:
                            coin_data = data[coin_id.lower()]
                            
                            # Обновляем курсы валют из данных CoinGecko
                            if coin_data.get("usd") and coin_data.get("rub"):
                                self.currency_rates.usd_rub_rate = coin_data["rub"] / coin_data["usd"]
                            if coin_data.get("usd") and coin_data.get("eur"):
                                self.currency_rates.usd_eur_rate = coin_data["eur"] / coin_data["usd"]
                            
                            self.cache.set(coin_id, coin_data)
                            
                            elapsed = (datetime.now() - start_time).total_seconds()
                            self.stats["coingecko"]["success"] += 1
                            self.stats["coingecko"]["total_time"] += elapsed
                            
                            logger.info(f"CoinGecko: {coin_id} = ${coin_data.get('usd', 0):.2f}")
                            
                            return {
                                "success": True,
                                "source": "CoinGecko",
                                "price_usd": coin_data.get("usd", 0),
                                "price_rub": coin_data.get("rub", 0),
                                "price_eur": coin_data.get("eur", 0),
                                "change_24h": coin_data.get("usd_24h_change", 0),
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
    
    async def get_from_coinpaprika(self, symbol: str) -> Optional[Dict]:
        """CoinPaprika API - бесплатный, надёжный"""
        start_time = datetime.now()
        
        try:
            async with aiohttp.ClientSession() as session:
                coin_info = self.get_coin_info(symbol)
                paprika_id = coin_info.get("paprika_id", f"{symbol.lower()}-{symbol.lower()}")
                
                url = f"https://api.coinpaprika.com/v1/tickers/{paprika_id}"
                timeout = aiohttp.ClientTimeout(total=10)
                
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        quotes = data.get("quotes", {}).get("USD", {})
                        price_usd = quotes.get("price", 0)
                        change_24h = quotes.get("percent_change_24h", 0)
                        market_cap = quotes.get("market_cap", 0)
                        volume_24h = quotes.get("volume_24h", 0)
                        
                        if price_usd > 0:
                            # Обновляем курсы валют если нужно
                            if self.currency_rates.needs_update():
                                await self.currency_rates.update_rates()
                            
                            elapsed = (datetime.now() - start_time).total_seconds()
                            self.stats["coinpaprika"]["success"] += 1
                            self.stats["coinpaprika"]["total_time"] += elapsed
                            
                            logger.info(f"CoinPaprika: {symbol} = ${price_usd:.2f}")
                            
                            return {
                                "success": True,
                                "source": "CoinPaprika",
                                "price_usd": price_usd,
                                "price_rub": self.currency_rates.get_rub_price(price_usd),
                                "price_eur": self.currency_rates.get_eur_price(price_usd),
                                "change_24h": change_24h,
                                "market_cap": market_cap,
                                "volume_24h": volume_24h,
                            }
                    elif response.status == 404:
                        logger.warning(f"CoinPaprika: монета {symbol} не найдена")
                    else:
                        logger.warning(f"CoinPaprika: статус {response.status}")
                        
        except asyncio.TimeoutError:
            self.stats["coinpaprika"]["failed"] += 1
            logger.warning(f"CoinPaprika timeout: {symbol}")
        except Exception as e:
            self.stats["coinpaprika"]["failed"] += 1
            logger.error(f"CoinPaprika ошибка: {e}")
        
        return None
    
    async def get_from_mexc(self, symbol: str) -> Optional[Dict]:
        """MEXC API - замена Binance, работает в РФ"""
        start_time = datetime.now()
        
        try:
            async with aiohttp.ClientSession() as session:
                coin_info = self.get_coin_info(symbol)
                mexc_symbol = coin_info.get("mexc", f"{symbol.upper()}USDT")
                
                params = {"symbol": mexc_symbol}
                timeout = aiohttp.ClientTimeout(total=8)
                
                async with session.get(
                    self.apis["mexc"]["url"],
                    params=params,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        price_usd = float(data.get("lastPrice", 0))
                        change_24h = float(data.get("priceChangePercent", 0))
                        volume_24h = float(data.get("volume", 0)) * price_usd
                        
                        if price_usd > 0:
                            # Обновляем курсы валют если нужно
                            if self.currency_rates.needs_update():
                                await self.currency_rates.update_rates()
                            
                            elapsed = (datetime.now() - start_time).total_seconds()
                            self.stats["mexc"]["success"] += 1
                            self.stats["mexc"]["total_time"] += elapsed
                            
                            logger.info(f"MEXC: {symbol} = ${price_usd:.2f}")
                            
                            return {
                                "success": True,
                                "source": "MEXC",
                                "price_usd": price_usd,
                                "price_rub": self.currency_rates.get_rub_price(price_usd),
                                "price_eur": self.currency_rates.get_eur_price(price_usd),
                                "change_24h": change_24h,
                                "market_cap": 0,
                                "volume_24h": volume_24h,
                            }
                            
        except asyncio.TimeoutError:
            self.stats["mexc"]["failed"] += 1
            logger.warning(f"MEXC timeout: {symbol}")
        except Exception as e:
            self.stats["mexc"]["failed"] += 1
            logger.error(f"MEXC ошибка: {e}")
        
        return None
    
    async def get_from_kraken(self, symbol: str) -> Optional[Dict]:
        """Kraken API - резервный источник"""
        start_time = datetime.now()
        
        try:
            async with aiohttp.ClientSession() as session:
                coin_info = self.get_coin_info(symbol)
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
                            ticker_data = list(data["result"].values())[0]
                            price_usd = float(ticker_data.get("c", [0])[0])
                            
                            open_price = float(ticker_data.get("o", price_usd))
                            if open_price > 0:
                                change_24h = ((price_usd - open_price) / open_price) * 100
                            else:
                                change_24h = 0
                            
                            volume_24h = float(ticker_data.get("v", [0, 0])[1]) * price_usd
                            
                            if price_usd > 0:
                                # Обновляем курсы валют если нужно
                                if self.currency_rates.needs_update():
                                    await self.currency_rates.update_rates()
                                
                                elapsed = (datetime.now() - start_time).total_seconds()
                                self.stats["kraken"]["success"] += 1
                                self.stats["kraken"]["total_time"] += elapsed
                                
                                logger.info(f"Kraken: {symbol} = ${price_usd:.2f}")
                                
                                return {
                                    "success": True,
                                    "source": "Kraken",
                                    "price_usd": price_usd,
                                    "price_rub": self.currency_rates.get_rub_price(price_usd),
                                    "price_eur": self.currency_rates.get_eur_price(price_usd),
                                    "change_24h": change_24h,
                                    "market_cap": 0,
                                    "volume_24h": volume_24h,
                                }
                                
        except asyncio.TimeoutError:
            self.stats["kraken"]["failed"] += 1
            logger.warning(f"Kraken timeout: {symbol}")
        except Exception as e:
            self.stats["kraken"]["failed"] += 1
            logger.error(f"Kraken ошибка: {e}")
        
        return None
    
    async def get_price(self, symbol: str) -> Dict:
        """
        Получить цену монеты с автоматическим fallback
        Порядок: CoinGecko - CoinPaprika - MEXC - Kraken - Кэш
        """
        symbol = symbol.upper()
        coin_info = self.get_coin_info(symbol)
        coin_id = coin_info.get("id", symbol.lower())
        
        logger.info(f"Получаю цену {symbol}...")
        
        # 1. CoinGecko (лучшие данные, market cap, volume)
        result = await self.get_from_coingecko(coin_id)
        if result and result.get("success"):
            return result
        
        # 2. CoinPaprika (бесплатный, надёжный)
        result = await self.get_from_coinpaprika(symbol)
        if result and result.get("success"):
            return result
        
        # 3. MEXC (замена Binance, работает в РФ)
        result = await self.get_from_mexc(symbol)
        if result and result.get("success"):
            return result
        
        # 4. Kraken (резерв)
        result = await self.get_from_kraken(symbol)
        if result and result.get("success"):
            return result
        
        # 5. Cache (если все API недоступны)
        cached = self.cache.get(coin_id)
        if cached:
            logger.warning(f"Используем кэш для {symbol}")
            return {
                "success": True,
                "source": "Cache",
                "price_usd": cached.get("usd", 0),
                "price_rub": cached.get("rub", 0),
                "price_eur": cached.get("eur", 0),
                "change_24h": cached.get("usd_24h_change", 0),
                "market_cap": cached.get("usd_market_cap", 0),
                "volume_24h": cached.get("usd_24h_vol", 0),
            }
        
        logger.error(f"Все API недоступны для {symbol}")
        return {
            "success": False,
            "error": "all_apis_failed",
            "message": "Не удалось получить данные. Попробуйте позже.",
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
        
        for api_name, stats in self.stats.items():
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
    
    def _get_cache_key(self, symbol: str, start_time: int, end_time: int) -> str:
        """Generate cache key for historical prices."""
        # Round to 5-minute intervals for better cache hits
        start_rounded = (start_time // 300) * 300
        end_rounded = (end_time // 300) * 300
        return f"{symbol}_{start_rounded}_{end_rounded}"
    
    async def get_historical_prices_binance(
        self, 
        symbol: str, 
        start_time: int, 
        end_time: int
    ) -> Optional[Dict]:
        """
        Get historical prices from Binance Klines API.
        
        Endpoint: GET /api/v3/klines
        Params: symbol=BTCUSDT, interval=5m, startTime=..., endTime=...
        
        Returns:
            Dict with 'min_price', 'max_price', 'prices' list
        """
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": f"{symbol}USDT",
                "interval": "5m",
                "startTime": start_time * 1000,  # Binance uses milliseconds
                "endTime": end_time * 1000,
                "limit": 1000
            }
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=15)
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data:
                            return None
                        # Klines format: [open_time, open, high, low, close, volume, ...]
                        prices = [float(candle[4]) for candle in data]  # close prices
                        highs = [float(candle[2]) for candle in data]
                        lows = [float(candle[3]) for candle in data]
                        if not prices or not highs or not lows:
                            return None
                        return {
                            "success": True,
                            "min_price": min(lows),
                            "max_price": max(highs),
                            "prices": prices,
                            "source": "binance",
                            "data_points": len(data)
                        }
        except Exception as e:
            logger.warning(f"Binance historical prices error: {e}")
        return None

    async def get_historical_prices_okx(
        self, 
        symbol: str, 
        start_time: int, 
        end_time: int
    ) -> Optional[Dict]:
        """
        Get historical prices from OKX API.
        
        Endpoint: GET /api/v5/market/history-candles
        """
        try:
            url = "https://www.okx.com/api/v5/market/history-candles"
            params = {
                "instId": f"{symbol}-USDT",
                "bar": "5m",
                "after": str(start_time * 1000),  # after = start time (older)
                "before": str(end_time * 1000),   # before = end time (more recent)
                "limit": "300"
            }
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=15)
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("data"):
                            candles = data["data"]
                            if not candles:
                                return None
                            prices = [float(c[4]) for c in candles]  # close
                            highs = [float(c[2]) for c in candles]
                            lows = [float(c[3]) for c in candles]
                            if not prices or not highs or not lows:
                                return None
                            return {
                                "success": True,
                                "min_price": min(lows),
                                "max_price": max(highs),
                                "prices": prices,
                                "source": "okx",
                                "data_points": len(candles)
                            }
        except Exception as e:
            logger.warning(f"OKX historical prices error: {e}")
        return None

    async def get_historical_prices_bybit(
        self, 
        symbol: str, 
        start_time: int, 
        end_time: int
    ) -> Optional[Dict]:
        """
        Get historical prices from Bybit API.
        
        Endpoint: GET /v5/market/kline
        """
        try:
            url = "https://api.bybit.com/v5/market/kline"
            params = {
                "category": "spot",
                "symbol": f"{symbol}USDT",
                "interval": "5",  # 5 minutes
                "start": start_time * 1000,
                "end": end_time * 1000,
                "limit": 200
            }
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=15)
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("result", {}).get("list"):
                            candles = data["result"]["list"]
                            if not candles:
                                return None
                            prices = [float(c[4]) for c in candles]  # close
                            highs = [float(c[2]) for c in candles]
                            lows = [float(c[3]) for c in candles]
                            if not prices or not highs or not lows:
                                return None
                            return {
                                "success": True,
                                "min_price": min(lows),
                                "max_price": max(highs),
                                "prices": prices,
                                "source": "bybit",
                                "data_points": len(candles)
                            }
        except Exception as e:
            logger.warning(f"Bybit historical prices error: {e}")
        return None

    async def get_historical_prices_coingecko(
        self,
        symbol: str,
        from_timestamp: int,
        to_timestamp: int
    ) -> Optional[Dict]:
        """
        Get historical prices from CoinGecko API.
        
        Args:
            symbol: Символ монеты (BTC, ETH, и т.д.)
            from_timestamp: Unix timestamp начала периода
            to_timestamp: Unix timestamp конца периода
            
        Returns:
            Dict с min_price, max_price, prices список или None при ошибке
        """
        coin_info = self.get_coin_info(symbol)
        # Add null-checking to handle case where coin_info might be None
        coin_id = (coin_info or {}).get("id", symbol.lower())
        
        logger.info(f"Получаю исторические цены {symbol} с {from_timestamp} по {to_timestamp}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
                params = {
                    "vs_currency": "usd",
                    "from": from_timestamp,
                    "to": to_timestamp
                }
                timeout = aiohttp.ClientTimeout(total=15)
                
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices = data.get("prices", [])
                        
                        if not prices:
                            logger.warning(f"Нет исторических данных для {symbol}")
                            return None
                        
                        # Извлекаем только значения цен (игнорируем временные метки)
                        price_values = [p[1] for p in prices]
                        min_price = min(price_values)
                        max_price = max(price_values)
                        
                        logger.info(
                            f"Исторические цены {symbol}: "
                            f"min=${min_price:.2f}, max=${max_price:.2f}, "
                            f"точек={len(prices)}"
                        )
                        
                        return {
                            "success": True,
                            "min_price": min_price,
                            "max_price": max_price,
                            "prices": price_values,
                            "source": "coingecko",
                            "data_points": len(prices)
                        }
                    elif response.status == 429:
                        logger.warning("CoinGecko: лимит запросов для исторических данных")
                    else:
                        logger.warning(
                            f"CoinGecko исторические данные: статус {response.status}"
                        )
                        
        except asyncio.TimeoutError:
            logger.warning(f"CoinGecko timeout для исторических данных: {symbol}")
        except Exception as e:
            logger.error(f"Ошибка получения исторических данных: {e}")
        
        return None

    async def get_historical_prices_multi(
        self,
        symbol: str,
        start_time: int,
        end_time: int
    ) -> Optional[Dict]:
        """
        Get historical prices with fallback chain.
        
        Order: Binance → OKX → Bybit → CoinGecko
        
        Args:
            symbol: Coin symbol (BTC, ETH, etc.)
            start_time: Unix timestamp (seconds)
            end_time: Unix timestamp (seconds)
            
        Returns:
            Dict with min_price, max_price, prices, source
        """
        # 1. Try Binance (primary - no rate limits)
        result = await self.get_historical_prices_binance(symbol, start_time, end_time)
        if result:
            logger.info(f"Historical prices {symbol} from Binance: min=${result['min_price']:.2f}, max=${result['max_price']:.2f}")
            return result
        
        # 2. Try OKX (fallback 1)
        result = await self.get_historical_prices_okx(symbol, start_time, end_time)
        if result:
            logger.info(f"Historical prices {symbol} from OKX: min=${result['min_price']:.2f}, max=${result['max_price']:.2f}")
            return result
        
        # 3. Try Bybit (fallback 2)
        result = await self.get_historical_prices_bybit(symbol, start_time, end_time)
        if result:
            logger.info(f"Historical prices {symbol} from Bybit: min=${result['min_price']:.2f}, max=${result['max_price']:.2f}")
            return result
        
        # 4. Try CoinGecko (fallback 3 - with delay to avoid rate limit)
        await asyncio.sleep(1.5)  # Delay before CoinGecko request
        result = await self.get_historical_prices_coingecko(symbol, start_time, end_time)
        if result:
            logger.info(f"Historical prices {symbol} from CoinGecko: min=${result['min_price']:.2f}, max=${result['max_price']:.2f}")
            return result
        
        logger.warning(f"All APIs failed for historical prices {symbol}")
        return None

    async def get_historical_prices_cached(
        self,
        symbol: str,
        start_time: int,
        end_time: int
    ) -> Optional[Dict]:
        """Get historical prices with caching."""
        cache_key = self._get_cache_key(symbol, start_time, end_time)
        
        # Check cache
        if cache_key in self._historical_cache:
            cached = self._historical_cache[cache_key]
            if time.time() - cached['timestamp'] < self._cache_ttl:
                logger.debug(f"Using cached historical prices for {symbol}")
                return cached['data']
        
        # Fetch from APIs
        result = await self.get_historical_prices_multi(symbol, start_time, end_time)
        
        # Store in cache
        if result:
            self._historical_cache[cache_key] = {
                'data': result,
                'timestamp': time.time()
            }
        
        return result

    async def get_historical_prices(
        self,
        symbol: str,
        from_timestamp: int,
        to_timestamp: int
    ) -> Optional[Dict]:
        """
        Get historical prices with multi-API fallback and caching.
        This is the main entry point for historical price data.
        """
        return await self.get_historical_prices_cached(symbol, from_timestamp, to_timestamp)


api_manager = MultiAPIManager()


async def get_coin_price(symbol: str) -> dict:
    """Получить цену монеты"""
    return await api_manager.get_price(symbol)


async def get_multiple_prices(symbols: list) -> dict:
    """Получить цены нескольких монет"""
    return await api_manager.get_multiple_prices(symbols)


def get_api_stats() -> Dict:
    """Получить статистику работы API"""
    return api_manager.get_stats()


async def get_historical_prices(symbol: str, from_timestamp: int, to_timestamp: int) -> Dict:
    """Получить исторические цены монеты за период"""
    result = await api_manager.get_historical_prices(symbol, from_timestamp, to_timestamp)
    if result is None or not result.get("success", False):
        return {
            "success": False,
            "error": "failed_to_fetch_historical_data",
            "message": "Не удалось получить исторические данные"
        }
    return result


if __name__ == "__main__":
    async def test():
        print("")
        print("=" * 50)
        print("GHEEZY CRYPTO - Test Multi-API Manager")
        print("5 API: CoinGecko + CoinPaprika + MEXC + Kraken + Cache")
        print("=" * 50)
        
        # Тестируем несколько монет, включая новые
        coins = ["BTC", "ETH", "TON", "SOL", "XRP", "NOT", "PEPE", "SUI", "ARB"]
        
        print("")
        print("Getting prices...")
        print("")
        
        for symbol in coins:
            price_data = await get_coin_price(symbol)
            
            if price_data.get("success"):
                print(f"[OK] {symbol}")
                print(f"     USD: ${price_data['price_usd']:,.2f}")
                print(f"     RUB: {price_data['price_rub']:,.2f}")
                print(f"     24h: {price_data['change_24h']:+.2f}%")
                print(f"     Source: {price_data['source']}")
                print("")
            else:
                print(f"[FAIL] {symbol}: {price_data.get('message')}")
                print("")
        
        print("=" * 50)
        print("API STATS")
        print("=" * 50)
        
        stats = get_api_stats()
        for api_name, api_stats in stats.items():
            print("")
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
    
    asyncio.run(test())