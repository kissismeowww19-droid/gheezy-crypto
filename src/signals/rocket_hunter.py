"""
Rocket Hunter - система поиска "ракет" с потенциалом +10%+ роста/падения.
Сканирует 500 монет из CoinGecko и находит ТОП-5 лучших сигналов.
Фьючерсные данные используются как бонус, но не обязательны.
"""

import logging
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import asyncio
import aiohttp

from signals.exchanges.okx import OKXClient
from signals.exchanges.bybit import BybitClient
from signals.exchanges.gate import GateClient
from config import settings

logger = logging.getLogger(__name__)


class RocketHunterAnalyzer:
    """
    Анализатор ракет - монет с потенциалом +10%+ роста или падения.
    
    Сканирует 500 монет из CoinGecko, анализирует их по множеству факторов
    и выбирает ТОП-5 лучших ракет. Фьючерсные данные - бонус, не обязательны.
    """
    
    # Настройки сканирования
    MIN_SCORE = 7.0  # Минимальный score для показа
    MIN_VOLUME_USD = 100_000  # Минимальный объём 24h (без жёстких ограничений)
    MIN_POTENTIAL = 10.0  # Минимальный потенциал +10%
    MAX_SPREAD_PCT = 1.0  # Максимальный спред 1%
    
    # Исключенные символы (стейблкоины, wrapped токены, проблемные монеты)
    EXCLUDED_SYMBOLS = {
        # === СТЕЙБЛКОИНЫ ===
        'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'FDUSD', 'PYUSD', 'USDD', 
        'USDP', 'GUSD', 'FRAX', 'LUSD', 'USDJ', 'USDS', 'CUSD', 'SUSD',
        'USDN', 'USDX', 'USDK', 'MUSD', 'HUSD', 'OUSD', 'CEUR', 'EURS',
        'EURT', 'USDQ', 'RSV', 'PAX', 'USDL', 'USDB', 'EURC', 'AUSD',
        
        # === WRAPPED ТОКЕНЫ ===
        'WETH', 'WBTC', 'WBNB', 'WSTETH', 'WBETH', 'CBBTC',
        'METH', 'EETH', 'WTRX', 'WAVAX', 'WMATIC', 'WFTM',
        'BTC.B', 'UBTC', 'WAETHUSDC', 'WAETHUSDT',
        
        # === БИРЖЕВЫЕ ТОКЕНЫ ===
        'BGB', 'WBT', 'GT', 'MX', 'KCS', 'HT', 'OKB', 'BNB', 'LEO', 'CRO',
        'BTSE', 'BMX', 'UCN', 'KOGE',
        
        # === МУСОРНЫЕ ТОКЕНЫ ===
        'WHYPE', 'TIBBIR', 'CASH', '币安人生',
    }
    
    # Приоритет бирж для fallback
    EXCHANGE_PRIORITY = ["okx", "bybit", "gate"]
    
    # Минимальная длина API ключа CoinGecko
    MIN_API_KEY_LENGTH = 5
    
    def __init__(self):
        self.exchanges = {
            "okx": OKXClient(),
            "bybit": BybitClient(),
            "gate": GateClient(),
        }
        self.session: Optional[aiohttp.ClientSession] = None
        self.invalid_symbols_cache: Dict[str, float] = {}  # {symbol: timestamp}
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close all exchange connections."""
        for exchange in self.exchanges.values():
            await exchange.close()
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _is_valid_symbol(self, symbol: str) -> bool:
        """Проверяет валидность символа."""
        if not symbol:
            return False
        
        # Исключаем символы с точкой (wrapped токены)
        if '.' in symbol:
            return False
        
        # Исключаем не-ASCII символы
        if not symbol.isascii():
            return False
        
        # Исключаем из списка
        if symbol.upper() in self.EXCLUDED_SYMBOLS:
            return False
        
        # Исключаем символы с дефисами или подчёркиваниями
        if '_' in symbol or '-' in symbol:
            return False
        
        # Исключаем слишком длинные символы
        if len(symbol) > 10:
            return False
        
        return True
    
    async def fetch_binance_gainers(self) -> List[Dict]:
        """
        Получает все торговые пары с Binance.
        1 запрос = ~600 монет, без лимита!
        """
        await self._ensure_session()
        
        url = "https://api.binance.com/api/v3/ticker/24hr"
        
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    coins = []
                    for ticker in data:
                        symbol = ticker.get('symbol', '')
                        
                        # Только USDT пары
                        if not symbol.endswith('USDT'):
                            continue
                        
                        # Убираем USDT из названия
                        base_symbol = symbol.replace('USDT', '')
                        
                        price_change_24h = float(ticker.get('priceChangePercent', 0))
                        current_price = float(ticker.get('lastPrice', 0))
                        volume_24h = float(ticker.get('quoteVolume', 0))  # В USDT
                        
                        coins.append({
                            'symbol': base_symbol,
                            'name': base_symbol,
                            'current_price': current_price,
                            'price_change_percentage_24h': price_change_24h,
                            'price_change_percentage_1h_in_currency': 0,  # Binance не даёт 1h
                            'total_volume': volume_24h,
                            'market_cap': 0,
                            'source': 'binance'
                        })
                    
                    logger.info(f"Binance: fetched {len(coins)} coins")
                    return coins
        except Exception as e:
            logger.error(f"Error fetching Binance data: {e}", exc_info=True)
        
        return []
    
    async def fetch_coincap_gainers(self) -> List[Dict]:
        """
        Получает топ-2000 монет с CoinCap.
        Лимит: 200 запросов/мин — достаточно!
        """
        await self._ensure_session()
        
        url = "https://api.coincap.io/v2/assets?limit=2000"
        
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    assets = data.get('data', [])
                    
                    coins = []
                    for asset in assets:
                        change_24h = asset.get('changePercent24Hr')
                        if change_24h is None:
                            continue
                        
                        coins.append({
                            'symbol': asset.get('symbol', '').upper(),
                            'name': asset.get('name', ''),
                            'current_price': float(asset.get('priceUsd', 0) or 0),
                            'price_change_percentage_24h': float(change_24h),
                            'price_change_percentage_1h_in_currency': 0,
                            'total_volume': float(asset.get('volumeUsd24Hr', 0) or 0),
                            'market_cap': float(asset.get('marketCapUsd', 0) or 0),
                            'source': 'coincap'
                        })
                    
                    logger.info(f"CoinCap: fetched {len(coins)} coins")
                    return coins
        except Exception as e:
            logger.error(f"Error fetching CoinCap data: {e}", exc_info=True)
        
        return []
    
    async def fetch_coingecko_page1(self) -> List[Dict]:
        """
        Получает 1 страницу с CoinGecko (250 монет).
        Дополнительный источник с 1h данными.
        """
        await self._ensure_session()
        
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": False,
            "price_change_percentage": "1h,24h"
        }
        
        headers = {}
        api_key = getattr(settings, 'coingecko_api_key', None)
        if api_key and len(api_key) > self.MIN_API_KEY_LENGTH:
            headers["x-cg-demo-api-key"] = api_key
        
        try:
            async with self.session.get(
                url, 
                params=params, 
                headers=headers, 
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    coins = []
                    for coin in data:
                        coins.append({
                            'symbol': coin.get('symbol', '').upper(),
                            'name': coin.get('name', ''),
                            'current_price': float(coin.get('current_price', 0) or 0),
                            'price_change_percentage_24h': float(coin.get('price_change_percentage_24h', 0) or 0),
                            'price_change_percentage_1h_in_currency': float(coin.get('price_change_percentage_1h_in_currency', 0) or 0),
                            'total_volume': float(coin.get('total_volume', 0) or 0),
                            'market_cap': float(coin.get('market_cap', 0) or 0),
                            'source': 'coingecko'
                        })
                    
                    logger.info(f"CoinGecko: fetched {len(coins)} coins")
                    return coins
        except Exception as e:
            logger.error(f"Error fetching CoinGecko data: {e}", exc_info=True)
        
        return []
    
    async def scan_all_coins(self) -> List[Dict]:
        """
        Сканирует монеты из всех 3 источников и объединяет.
        
        Returns:
            Список монет с базовой информацией
        """
        logger.info("Rocket Hunter: scanning from 3 sources (Binance + CoinCap + CoinGecko)")
        
        # Параллельно загружаем из всех источников
        binance_task = self.fetch_binance_gainers()
        coincap_task = self.fetch_coincap_gainers()
        coingecko_task = self.fetch_coingecko_page1()
        
        results = await asyncio.gather(
            binance_task, 
            coincap_task, 
            coingecko_task,
            return_exceptions=True
        )
        
        binance_coins = results[0] if not isinstance(results[0], Exception) else []
        coincap_coins = results[1] if not isinstance(results[1], Exception) else []
        coingecko_coins = results[2] if not isinstance(results[2], Exception) else []
        
        # Объединяем и убираем дубликаты (приоритет: Binance > CoinGecko > CoinCap)
        seen_symbols = set()
        all_coins = []
        
        # Сначала Binance (реальные биржевые данные)
        for coin in binance_coins:
            symbol = coin['symbol']
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                all_coins.append(coin)
        
        # Потом CoinGecko (есть 1h данные)
        for coin in coingecko_coins:
            symbol = coin['symbol']
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                all_coins.append(coin)
        
        # Потом CoinCap (много монет)
        for coin in coincap_coins:
            symbol = coin['symbol']
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                all_coins.append(coin)
        
        logger.info(f"Rocket Hunter: total {len(all_coins)} unique coins "
                    f"(Binance: {len(binance_coins)}, CoinCap: {len(coincap_coins)}, "
                    f"CoinGecko: {len(coingecko_coins)})")
        
        return all_coins
    
    async def filter_coins(self, coins: List[Dict]) -> List[Dict]:
        """
        Фильтрует монеты по базовым критериям.
        
        Args:
            coins: Список монет от CoinGecko
            
        Returns:
            Список монет прошедших фильтры
        """
        filtered = []
        
        for coin in coins:
            symbol = coin.get('symbol', '').upper()
            
            # Проверка валидности символа
            if not self._is_valid_symbol(symbol):
                continue
            
            # Минимальный объём (более мягкий фильтр)
            volume_24h = coin.get('total_volume', 0)
            if volume_24h < self.MIN_VOLUME_USD:
                continue
            
            # Пропускаем монеты без изменения цены
            price_change_24h = coin.get('price_change_percentage_24h')
            if price_change_24h is None:
                continue
            
            filtered.append(coin)
        
        logger.info(f"Rocket Hunter: {len(filtered)} coins passed filters")
        return filtered
    
    async def _get_exchange_data(self, symbol: str) -> Optional[Dict]:
        """Получает данные с бирж (candles, funding, OI)."""
        for exchange_name in self.EXCHANGE_PRIORITY:
            try:
                exchange = self.exchanges[exchange_name]
                
                # Получаем 4-часовые свечи
                candles_4h = await exchange.get_candles(symbol, "4h", limit=100)
                if not candles_4h or len(candles_4h) < 20:
                    continue
                
                # Получаем 1-часовые свечи
                candles_1h = await exchange.get_candles(symbol, "1h", limit=50)
                if not candles_1h or len(candles_1h) < 10:
                    continue
                
                # Получаем funding и OI
                funding = await exchange.get_funding_rate(symbol)
                oi_data = await exchange.get_open_interest(symbol)
                
                return {
                    "exchange": exchange_name,
                    "candles_4h": candles_4h,
                    "candles_1h": candles_1h,
                    "funding_rate": funding.get('funding_rate') if funding else None,
                    "open_interest": oi_data.get('open_interest') if oi_data else None,
                }
                
            except Exception as e:
                logger.debug(f"Exchange {exchange_name} failed for {symbol}: {e}")
                continue
        
        return None
    
    def _calculate_volume_ratio(self, candles: List[Dict]) -> float:
        """Рассчитывает отношение текущего объёма к среднему."""
        if not candles or len(candles) < 2:
            return 1.0
        
        try:
            current_volume = float(candles[-1].get('volume', 0))
            if current_volume == 0:
                return 1.0
            
            # Средний объём за последние N свечей (исключая текущую)
            volumes = [float(c.get('volume', 0)) for c in candles[:-1]]
            avg_volume = sum(volumes) / len(volumes) if volumes else 1
            
            if avg_volume == 0:
                return 1.0
            
            return current_volume / avg_volume
        except Exception as e:
            logger.warning(f"Error calculating volume ratio: {e}")
            return 1.0
    
    def _check_bollinger_breakout(self, candles: List[Dict]) -> bool:
        """Проверяет пробой Bollinger Bands."""
        if not candles or len(candles) < 20:
            return False
        
        try:
            # Берём последние 20 свечей
            closes = [float(c.get('close', 0)) for c in candles[-20:]]
            if not closes:
                return False
            
            # Рассчитываем MA и стандартное отклонение
            ma = sum(closes) / len(closes)
            variance = sum((x - ma) ** 2 for x in closes) / len(closes)
            std = variance ** 0.5
            
            # Bollinger Bands
            upper_band = ma + 2 * std
            lower_band = ma - 2 * std
            
            current_price = closes[-1]
            
            # Пробой вверх или вниз
            return current_price > upper_band or current_price < lower_band
            
        except Exception as e:
            logger.warning(f"Error checking BB breakout: {e}")
            return False
    
    def _calculate_rsi(self, candles: List[Dict], period: int = 14) -> float:
        """Рассчитывает RSI."""
        if not candles or len(candles) < period + 1:
            return 50.0
        
        try:
            closes = [float(c.get('close', 0)) for c in candles[-(period + 1):]]
            
            gains = []
            losses = []
            
            for i in range(1, len(closes)):
                change = closes[i] - closes[i - 1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains) / len(gains) if gains else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.warning(f"Error calculating RSI: {e}")
            return 50.0
    
    def _check_oi_growing(self, candles: List[Dict]) -> bool:
        """Проверяет рост Open Interest (упрощённо - по объёму)."""
        if not candles or len(candles) < 10:
            return False
        
        try:
            # Сравниваем объём последних 5 свечей с предыдущими 5
            recent_volumes = [float(c.get('volume', 0)) for c in candles[-5:]]
            older_volumes = [float(c.get('volume', 0)) for c in candles[-10:-5]]
            
            recent_avg = sum(recent_volumes) / len(recent_volumes)
            older_avg = sum(older_volumes) / len(older_volumes)
            
            return recent_avg > older_avg * 1.2  # Рост на 20%+
            
        except Exception as e:
            logger.warning(f"Error checking OI growth: {e}")
            return False
    
    async def calculate_rocket_score(self, coin: Dict) -> Optional[Dict]:
        """
        Рассчитывает score для ракеты используя данные CoinGecko.
        Фьючерсные данные = бонус, не обязательны.
        
        Args:
            coin: Данные монеты от CoinGecko
            
        Returns:
            Dict с полной информацией или None
        """
        symbol = coin.get('symbol', '').upper()
        
        try:
            # Базовые данные из CoinGecko (всегда есть!)
            current_price = float(coin.get('current_price', 0))
            if current_price <= 0:
                return None
            
            price_change_1h = coin.get('price_change_percentage_1h_in_currency', 0) or 0
            price_change_24h = coin.get('price_change_percentage_24h', 0) or 0
            volume_24h = coin.get('total_volume', 0) or 0
            market_cap = coin.get('market_cap', 0) or 0
            
            # Проверка минимального потенциала
            if abs(price_change_24h) < self.MIN_POTENTIAL:
                return None
            
            # === SCORE CALCULATION (на основе CoinGecko) ===
            score = 0
            factors = []
            
            # 1. Движение цены (макс 4 балла) - ГЛАВНЫЙ ФАКТОР
            abs_change_24h = abs(price_change_24h)
            if abs_change_24h >= 50:
                score += 4
                factors.append(f"🚀 Огромное движение ({price_change_24h:+.1f}%)")
            elif abs_change_24h >= 30:
                score += 3
                factors.append(f"📈 Сильное движение ({price_change_24h:+.1f}%)")
            elif abs_change_24h >= 20:
                score += 2
                factors.append(f"📈 Заметное движение ({price_change_24h:+.1f}%)")
            elif abs_change_24h >= 10:
                score += 1
                factors.append(f"📈 Движение ({price_change_24h:+.1f}%)")
            
            # 2. Объём (макс 3 балла)
            if volume_24h >= 100_000_000:  # $100M+
                score += 3
                factors.append(f"📊 Огромный объём (${volume_24h/1_000_000:.0f}M)")
            elif volume_24h >= 10_000_000:  # $10M+
                score += 2
                factors.append(f"📊 Высокий объём (${volume_24h/1_000_000:.1f}M)")
            elif volume_24h >= 1_000_000:  # $1M+
                score += 1
                factors.append(f"📊 Хороший объём (${volume_24h/1_000_000:.1f}M)")
            
            # 3. Часовое движение подтверждает направление (макс 2 балла)
            if price_change_24h > 0 and price_change_1h > 3:
                score += 2
                factors.append(f"⚡ Продолжает расти ({price_change_1h:+.1f}% за час)")
            elif price_change_24h > 0 and price_change_1h > 1:
                score += 1
                factors.append(f"⚡ Растёт ({price_change_1h:+.1f}% за час)")
            elif price_change_24h < 0 and price_change_1h < -3:
                score += 2
                factors.append(f"⚡ Продолжает падать ({price_change_1h:+.1f}% за час)")
            elif price_change_24h < 0 and price_change_1h < -1:
                score += 1
                factors.append(f"⚡ Падает ({price_change_1h:+.1f}% за час)")
            
            # 4. Market Cap (макс 1 балл) - низкий = больше потенциала
            if market_cap > 0 and market_cap < 100_000_000:  # < $100M
                score += 1
                factors.append("💎 Низкая капа (высокий потенциал)")
            
            # 5. БОНУС: Попробовать получить фьючерсные данные (необязательно)
            exchange_data = await self._get_exchange_data(symbol)
            exchange_name = None
            funding_rate = None
            oi_growing = False
            
            if exchange_data:
                exchange_name = exchange_data.get('exchange')
                funding_rate = exchange_data.get('funding_rate')
                
                candles = exchange_data.get('candles_4h', [])
                if candles:
                    oi_growing = self._check_oi_growing(candles)
                    if oi_growing:
                        score += 1
                        factors.append("🐋 Рост Open Interest")
                
                if funding_rate:
                    if price_change_24h > 0 and funding_rate < 0:
                        score += 1
                        factors.append("💹 Funding подтверждает лонг")
                    elif price_change_24h < 0 and funding_rate > 0:
                        score += 1
                        factors.append("💹 Funding подтверждает шорт")
            
            # Проверка минимального score
            if score < self.MIN_SCORE:
                return None
            
            # Определение направления
            if price_change_24h > 0:
                direction = "ЛОНГ"
                direction_emoji = "📈"
            else:
                direction = "ШОРТ"
                direction_emoji = "📉"
            
            # Расчёт потенциала
            potential_min = int(abs_change_24h * 0.5)
            potential_max = int(abs_change_24h * 1.0)
            
            return {
                "symbol": symbol,
                "name": coin.get('name', symbol),
                "price": current_price,
                "change_1h": price_change_1h,
                "change_24h": price_change_24h,
                "volume_24h": volume_24h,
                "market_cap": market_cap,
                "funding_rate": funding_rate,
                "oi_growing": oi_growing,
                "score": score,
                "direction": direction,
                "direction_emoji": direction_emoji,
                "factors": factors,
                "potential_min": potential_min,
                "potential_max": potential_max,
                "exchange": exchange_name,
                "source": coin.get('source', 'unknown'),
            }
            
        except Exception as e:
            logger.debug(f"Error calculating score for {symbol}: {e}")
            return None
    
    async def get_top5(self) -> Tuple[List[Dict], int, int, float]:
        """
        Возвращает ТОП-5 ракет.
        
        Returns:
            Tuple (top5_list, scanned_count, filtered_count, scan_time_seconds)
        """
        start_time = time.time()
        
        # Сканируем монеты
        coins = await self.scan_all_coins()
        scanned_count = len(coins)
        
        # Фильтруем
        filtered_coins = await self.filter_coins(coins)
        filtered_count = len(filtered_coins)
        
        # Рассчитываем scores
        scored_coins = []
        
        # Параллельно с ограничением
        semaphore = asyncio.Semaphore(10)  # Уменьшено для стабильности
        
        async def score_coin_with_limit(coin):
            async with semaphore:
                return await self.calculate_rocket_score(coin)
        
        # Анализируем все отфильтрованные монеты (не только первые 200)
        tasks = [score_coin_with_limit(coin) for coin in filtered_coins]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if result and not isinstance(result, Exception):
                scored_coins.append(result)
        
        # Сортируем по score
        scored_coins.sort(key=lambda x: x["score"], reverse=True)
        
        scan_time = time.time() - start_time
        
        logger.info(f"Rocket Hunter found {len(scored_coins)} rockets from {filtered_count} coins")
        
        return scored_coins[:5], scanned_count, filtered_count, scan_time
    
    def _format_price(self, price: float) -> str:
        """Форматирует цену."""
        if price <= 0:
            return "$0.00"
        elif price < 0.0001:
            return f"${price:.8f}"
        elif price < 0.01:
            return f"${price:.6f}"
        elif price < 1:
            return f"${price:.4f}"
        elif price < 1000:
            return f"${price:.2f}"
        else:
            return f"${price:,.2f}"
    
    def format_message(self, top5: List[Dict], scanned_count: int, 
                      filtered_count: int, scan_time: float) -> str:
        """
        Форматирует сообщение для Telegram.
        
        Args:
            top5: Список ТОП-5 ракет
            scanned_count: Количество отсканированных монет
            filtered_count: Количество монет прошедших фильтры
            scan_time: Время скана в секундах
            
        Returns:
            Отформатированное сообщение
        """
        now = datetime.now().strftime("%H:%M:%S")
        scan_minutes = int(scan_time // 60)
        scan_seconds = int(scan_time % 60)
        
        text = "🚀 *ОХОТНИК ЗА РАКЕТАМИ*\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📊 Просканировано: {scanned_count:,} монет\n"
        text += f"🔥 Найдено ракет: {len(top5)}\n"
        text += f"⏰ Время скана: {scan_minutes} мин {scan_seconds} сек\n"
        text += f"⏰ Обновлено: {now}\n\n"
        
        if not top5:
            text += "😔 *Ракет не найдено*\n\n"
            text += "Попробуйте позже или используйте Умные сигналы\\.\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "📊 Данные: Binance \\+ CoinCap \\+ CoinGecko\n"
            text += "⚠️ Высокий риск\\! Только на свои\\!"
            return text
        
        for idx, rocket in enumerate(top5, 1):
            text += f"🚀 *\\#{idx} {rocket['symbol']}/USDT \\| {rocket['direction_emoji']} {rocket['direction']}*\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            # Цена
            price_str = self._format_price(rocket['price']).replace("$", "\\$").replace(",", "\\,").replace(".", "\\.")
            text += f"💰 Цена: {price_str}\n"
            
            # Изменения
            text += f"📈 Δ1h: {rocket['change_1h']:+.1f}% \\| "
            text += f"Δ24h: {rocket['change_24h']:+.1f}%\n"
            
            # Объём
            volume = rocket.get('volume_24h', 0)
            if volume >= 100_000_000:
                text += f"📊 Объём: \\${volume/1_000_000:.0f}M 🔥\n"
            elif volume >= 1_000_000:
                text += f"📊 Объём: \\${volume/1_000_000:.1f}M\n"
            else:
                text += f"📊 Объём: \\${volume/1_000:.0f}K\n"
            
            # Funding и OI
            if rocket.get('funding_rate'):
                funding_pct = rocket['funding_rate'] * 100
                text += f"💹 Funding: {funding_pct:.3f}%"
                if rocket.get('oi_growing'):
                    text += " \\| OI: \\+растёт"
                text += "\n"
            
            # Score
            score = rocket['score']
            filled = int(score)
            empty = 10 - filled
            bar = "█" * filled + "░" * empty
            text += f"🎯 Score: {score:.1f}/10 {bar}\n"
            
            # Потенциал
            text += f"⚡ Потенциал: \\+{rocket['potential_min']}\\-{rocket['potential_max']}%\n\n"
            
            # Факторы
            if rocket.get('factors'):
                text += "🎯 *Почему ракета:*\n"
                for factor in rocket['factors']:
                    # Escape special characters
                    factor_escaped = (factor.replace("_", "\\_")
                                     .replace(".", "\\.")
                                     .replace("-", "\\-")
                                     .replace("+", "\\+")
                                     .replace("(", "\\(")
                                     .replace(")", "\\)")
                                     .replace("%", "\\%"))
                    text += f"• {factor_escaped}\n"
                text += "\n"
            
            # Уровни (упрощённые)
            current_price = rocket['price']
            
            # Для LONG
            if rocket['direction'] == "ЛОНГ":
                entry_low = current_price * 0.98
                entry_high = current_price * 1.02
                stop = current_price * 0.85
                tp1 = current_price * 1.28
                tp2 = current_price * 1.50
            else:  # SHORT
                entry_low = current_price * 0.98
                entry_high = current_price * 1.02
                stop = current_price * 1.15
                tp1 = current_price * 0.72
                tp2 = current_price * 0.50
            
            # Risk/Reward
            risk = abs(stop - current_price)
            reward = abs(tp1 - current_price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            text += "📍 *Уровни:*\n"
            text += f"• Вход: {self._format_price(entry_low).replace('$', '\\$').replace(',', '\\,').replace('.', '\\.')}"
            text += f"\\-{self._format_price(entry_high).replace('$', '').replace(',', '\\,').replace('.', '\\.')}\n"
            text += f"• Стоп: {self._format_price(stop).replace('$', '\\$').replace(',', '\\,').replace('.', '\\.')} "
            text += f"\\({((stop - current_price) / current_price * 100):+.1f}%\\)\n"
            text += f"• TP1: {self._format_price(tp1).replace('$', '\\$').replace(',', '\\,').replace('.', '\\.')} "
            text += f"\\({((tp1 - current_price) / current_price * 100):+.1f}%\\)\n"
            text += f"• TP2: {self._format_price(tp2).replace('$', '\\$').replace(',', '\\,').replace('.', '\\.')} "
            text += f"\\({((tp2 - current_price) / current_price * 100):+.1f}%\\)\n"
            text += f"📊 R:R = 1:{rr_ratio:.1f}\n"
            
            # Источник данных
            source = rocket.get('source', 'unknown')
            source_names = {
                'binance': 'Binance',
                'coincap': 'CoinCap',
                'coingecko': 'CoinGecko',
                'unknown': 'Unknown'
            }
            text += f"📡 Источник: {source_names.get(source, source)}\n"
            
            if idx < len(top5):
                text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "📊 Данные: Binance \\+ CoinCap \\+ CoinGecko\n"
        text += "⚠️ Высокий риск\\! Только на свои\\!"
        
        return text
