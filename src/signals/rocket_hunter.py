"""
Rocket Hunter - система поиска "ракет" с потенциалом +20%+ роста/падения.
Сканирует 2000-3000 монет из CoinGecko и находит ТОП-5 лучших сигналов.
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
    Анализатор ракет - монет с потенциалом +20%+ роста или падения.
    
    Сканирует 2000-3000 монет из CoinGecko, анализирует их по множеству факторов
    и выбирает ТОП-5 лучших ракет.
    """
    
    # Настройки сканирования
    SCAN_LIMIT = 3000  # Сканировать 2000-3000 монет
    MIN_SCORE = 7.0  # Минимальный score для показа
    MIN_VOLUME_USD = 100_000  # Минимальный объём 24h (без жёстких ограничений)
    MIN_POTENTIAL = 10.0  # Минимальный потенциал +10%
    MAX_SPREAD_PCT = 1.0  # Максимальный спред 1%
    MAX_ANALYZE = 200  # Максимум монет для детального анализа
    
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
    
    async def scan_all_coins(self) -> List[Dict]:
        """
        Сканирует 2000-3000 монет из CoinGecko API с пагинацией.
        
        Returns:
            Список монет с базовой информацией
        """
        await self._ensure_session()
        
        all_coins = []
        max_per_page = 250  # CoinGecko limit
        
        headers = {}
        api_key = getattr(settings, 'coingecko_api_key', None)
        if api_key and len(api_key) > self.MIN_API_KEY_LENGTH:
            headers["x-cg-demo-api-key"] = api_key
            logger.info("Using CoinGecko Demo API key for Rocket Hunter")
        
        total_pages = (self.SCAN_LIMIT + max_per_page - 1) // max_per_page
        logger.info(f"Rocket Hunter: scanning {self.SCAN_LIMIT} coins, {total_pages} pages")
        
        try:
            page = 1
            retries = 0
            max_retries = 3
            
            while page <= total_pages:
                url = "https://api.coingecko.com/api/v3/coins/markets"
                
                remaining = self.SCAN_LIMIT - len(all_coins)
                per_page = min(max_per_page, remaining)
                
                if per_page <= 0:
                    break
                
                params = {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": str(per_page),
                    "page": str(page),
                    "sparkline": "false",
                    "price_change_percentage": "1h,24h",
                }
                
                async with self.session.get(
                    url, 
                    params=params, 
                    headers=headers, 
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        retries = 0  # Reset retries on success
                        coins = await resp.json()
                        all_coins.extend(coins)
                        logger.info(f"Rocket Hunter page {page}/{total_pages}: {len(coins)} coins (total: {len(all_coins)})")
                        
                        if len(coins) < per_page:
                            break
                        
                    elif resp.status in [401, 429]:
                        retries += 1
                        if retries > max_retries:
                            logger.warning(f"Max retries reached, stopping at {len(all_coins)} coins")
                            break
                        logger.warning(f"CoinGecko rate limit ({resp.status}), retry {retries}/{max_retries}, waiting 20 sec...")
                        await asyncio.sleep(20)
                        continue
                    else:
                        logger.warning(f"CoinGecko API error: {resp.status}")
                        break
                
                page += 1
                
                # Задержка между запросами
                if page <= total_pages:
                    await asyncio.sleep(6)
            
            logger.info(f"Rocket Hunter scanned {len(all_coins)} coins from CoinGecko")
            return all_coins
            
        except Exception as e:
            logger.error(f"Error scanning coins: {e}", exc_info=True)
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
        Рассчитывает score для ракеты.
        
        Args:
            coin: Данные монеты от CoinGecko
            
        Returns:
            Dict с полной информацией или None
        """
        symbol = coin.get('symbol', '').upper()
        
        try:
            # Получаем данные с бирж
            exchange_data = await self._get_exchange_data(symbol)
            if not exchange_data:
                return None
            
            candles_4h = exchange_data['candles_4h']
            candles_1h = exchange_data['candles_1h']
            
            # Базовые данные
            current_price = float(coin.get('current_price', 0))
            if current_price <= 0:
                return None
            
            price_change_1h = coin.get('price_change_percentage_1h_in_currency', 0) or 0
            price_change_24h = coin.get('price_change_percentage_24h', 0) or 0
            
            # Рассчитываем 4h change из свечей
            if len(candles_4h) >= 2:
                price_4h_ago = float(candles_4h[-2].get('close', current_price))
                price_change_4h = ((current_price - price_4h_ago) / price_4h_ago * 100) if price_4h_ago > 0 else 0
            else:
                price_change_4h = 0
            
            # === SCORE CALCULATION ===
            score = 0
            factors = []
            
            # 1. Объём (макс 3 балла)
            volume_ratio = self._calculate_volume_ratio(candles_4h)
            if volume_ratio >= 20:
                score += 3
                factors.append(f"📊 Объём взорвался ({volume_ratio:.0f}x)")
            elif volume_ratio >= 10:
                score += 2
                factors.append(f"📊 Высокий объём ({volume_ratio:.0f}x)")
            elif volume_ratio >= 5:
                score += 1
                factors.append(f"📊 Повышенный объём ({volume_ratio:.0f}x)")
            
            # 2. Движение цены (макс 3 балла)
            abs_change_24h = abs(price_change_24h)
            if abs_change_24h >= 30:
                score += 3
                factors.append(f"📈 Сильное движение ({price_change_24h:+.1f}%)")
            elif abs_change_24h >= 20:
                score += 2
                factors.append(f"📈 Заметное движение ({price_change_24h:+.1f}%)")
            elif abs_change_24h >= 10:
                score += 1
                factors.append(f"📈 Движение ({price_change_24h:+.1f}%)")
            
            # 3. Технические индикаторы (макс 2 балла)
            bb_breakout = self._check_bollinger_breakout(candles_4h)
            if bb_breakout:
                score += 1
                factors.append("📈 Пробой Bollinger Bands")
            
            rsi = self._calculate_rsi(candles_4h)
            rsi_extreme = rsi > 70 or rsi < 30
            if rsi_extreme:
                score += 1
                factors.append(f"💹 RSI экстремум ({rsi:.1f})")
            
            # 4. Тренд подтверждение (макс 2 балла)
            oi_growing = self._check_oi_growing(candles_4h)
            if oi_growing:
                score += 1
                factors.append("🐋 Рост Open Interest")
            
            funding_rate = exchange_data.get('funding_rate')
            if funding_rate:
                # Для LONG - отрицательный funding хорошо, для SHORT - положительный
                funding_confirms = False
                if price_change_24h > 0 and funding_rate < 0:
                    funding_confirms = True
                    factors.append("💹 Отрицательный funding")
                elif price_change_24h < 0 and funding_rate > 0:
                    funding_confirms = True
                    factors.append("💹 Положительный funding")
                
                if funding_confirms:
                    score += 1
            
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
            if abs_change_24h < self.MIN_POTENTIAL:
                # Недостаточно потенциала
                return None
            
            potential_min = int(abs_change_24h * 1.0)
            potential_max = int(abs_change_24h * 1.5)
            
            return {
                "symbol": symbol,
                "price": current_price,
                "change_1h": price_change_1h,
                "change_4h": price_change_4h,
                "change_24h": price_change_24h,
                "volume_ratio": volume_ratio,
                "funding_rate": funding_rate,
                "oi_growing": oi_growing,
                "score": score,
                "direction": direction,
                "direction_emoji": direction_emoji,
                "factors": factors,
                "potential_min": potential_min,
                "potential_max": potential_max,
                "exchange": exchange_data['exchange'],
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
        
        # Рассчитываем scores для монет (с ограничением)
        scored_coins = []
        
        # Увеличен лимит для лучшей производительности при сканировании 2000-3000 монет
        semaphore = asyncio.Semaphore(25)
        max_coins_to_analyze = min(len(filtered_coins), self.MAX_ANALYZE)
        
        async def score_coin_with_limit(coin):
            async with semaphore:
                return await self.calculate_rocket_score(coin)
        
        tasks = [score_coin_with_limit(coin) for coin in filtered_coins[:max_coins_to_analyze]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if result and not isinstance(result, Exception):
                scored_coins.append(result)
        
        # Сортируем по score
        scored_coins.sort(key=lambda x: x["score"], reverse=True)
        
        scan_time = time.time() - start_time
        
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
            text += "📊 Данные: CoinGecko\n"
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
            text += f"Δ4h: {rocket['change_4h']:+.1f}% \\| "
            text += f"Δ24h: {rocket['change_24h']:+.1f}%\n"
            
            # Объём
            volume_ratio = rocket['volume_ratio']
            if volume_ratio >= 20:
                text += f"📊 Объём: {volume_ratio:.0f}x от среднего\\! 🔥\n"
            else:
                text += f"📊 Объём: {volume_ratio:.1f}x от среднего\n"
            
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
            
            if idx < len(top5):
                text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "📊 Данные: CoinGecko\n"
        text += "⚠️ Высокий риск\\! Только на свои\\!"
        
        return text
