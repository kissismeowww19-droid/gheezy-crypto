"""
Smart Signals - система умных сигналов для ТОП-3 монет.
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
from signals.scoring import (
    calculate_momentum_score, calculate_volume_score,
    calculate_trend_score, calculate_volatility_score,
    calculate_total_score, apply_score_bonuses,
    calculate_ema, calculate_adx, clamp
)
from config import settings

logger = logging.getLogger(__name__)


class SmartSignalAnalyzer:
    """
    Анализатор умных сигналов.
    
    Сканирует 500+ монет из CoinGecko, анализирует их по множеству факторов
    и выбирает ТОП-3 лучших сигналов.
    """
    
    # Настройки из конфига
    SCAN_LIMIT = getattr(settings, 'smart_signals_scan_limit', 500)
    MIN_VOLUME_USD = getattr(settings, 'smart_signals_min_volume', 5_000_000)
    MIN_MCAP_USD = getattr(settings, 'smart_signals_min_mcap', 10_000_000)
    MAX_SPREAD_PCT = getattr(settings, 'smart_signals_max_spread', 0.005) * 100  # Convert to percentage
    HYSTERESIS_TIME = getattr(settings, 'smart_signals_hysteresis_time', 900)
    HYSTERESIS_THRESHOLD = getattr(settings, 'smart_signals_hysteresis_threshold', 0.10)
    MAX_ANALYZE = getattr(settings, 'smart_signals_max_analyze', 100)
    
    # Веса для скоринга
    SCORING_WEIGHTS = {
        "momentum_4h": 0.30,
        "momentum_1h": 0.20,
        "volume_ratio": 0.20,
        "trend_score": 0.15,
        "volatility_score": 0.15,
    }
    
    # Приоритет бирж для fallback
    EXCHANGE_PRIORITY = ["okx", "bybit", "gate"]
    
    def __init__(self):
        self.exchanges = {
            "okx": OKXClient(),
            "bybit": BybitClient(),
            "gate": GateClient(),
        }
        self.cache: Dict[str, Dict] = {}
        self.top3_history: List[Dict] = []
        self.last_update: float = 0
        self.session: Optional[aiohttp.ClientSession] = None
    
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
    
    def _normalize_symbol_for_exchange(self, symbol: str, exchange: str) -> str:
        """
        Нормализует символ для конкретной биржи.
        
        Args:
            symbol: Базовый символ (напр., "BTC")
            exchange: Название биржи
            
        Returns:
            Нормализованный символ для биржи
        """
        if exchange == "okx":
            return f"{symbol}-USDT"
        elif exchange == "bybit":
            return f"{symbol}USDT"
        elif exchange == "gate":
            return f"{symbol}_USDT"
        return symbol
    
    async def scan_all_coins(self) -> List[Dict]:
        """
        Сканирует все монеты из CoinGecko API.
        
        Returns:
            Список монет с базовой информацией
        """
        await self._ensure_session()
        
        try:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": str(self.SCAN_LIMIT),
                "page": "1",
                "sparkline": "false",
            }
            
            headers = {}
            # Add API key as header if available (CoinGecko Pro)
            if settings.coingecko_api_key:
                headers["X-CG-Pro-API-Key"] = settings.coingecko_api_key
            
            async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    coins = await resp.json()
                    logger.info(f"Scanned {len(coins)} coins from CoinGecko")
                    return coins
                else:
                    logger.warning(f"CoinGecko API error: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Error scanning coins: {e}", exc_info=True)
            return []
    
    async def filter_coins(self, coins: List[Dict]) -> List[Dict]:
        """
        Фильтрует монеты по критериям ликвидности, объёма, возраста.
        
        Args:
            coins: Список монет от CoinGecko
            
        Returns:
            Отфильтрованный список монет
        """
        filtered = []
        
        for coin in coins:
            # Проверка объёма 24h
            volume_24h = coin.get("total_volume", 0) or 0
            if volume_24h < self.MIN_VOLUME_USD:
                continue
            
            # Проверка капитализации
            market_cap = coin.get("market_cap", 0) or 0
            if market_cap < self.MIN_MCAP_USD:
                continue
            
            # Проверка наличия цены
            if not coin.get("current_price"):
                continue
            
            # Добавляем в список
            filtered.append({
                "id": coin["id"],
                "symbol": coin["symbol"].upper(),
                "name": coin["name"],
                "price": coin["current_price"],
                "volume_24h": volume_24h,
                "market_cap": market_cap,
                "change_24h": coin.get("price_change_percentage_24h", 0) or 0,
            })
        
        logger.info(f"Filtered {len(filtered)} coins from {len(coins)}")
        return filtered
    
    async def _get_exchange_data(self, symbol: str, exchange_name: str) -> Optional[Dict]:
        """
        Получает данные с биржи (OHLCV, ticker, funding, OI).
        
        Args:
            symbol: Символ монеты (напр., "BTC")
            exchange_name: Название биржи
            
        Returns:
            Dict с данными или None
        """
        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            return None
        
        normalized_symbol = self._normalize_symbol_for_exchange(symbol, exchange_name)
        
        try:
            # Получаем данные параллельно
            tasks = [
                exchange.get_ohlcv(normalized_symbol, "1H", 100),
                exchange.get_ohlcv(normalized_symbol, "4H", 30),
                exchange.get_ticker(normalized_symbol),
            ]
            
            # Для фьючерсных данных нужен SWAP формат
            if exchange_name == "okx":
                swap_symbol = f"{symbol}-USDT-SWAP"
                tasks.extend([
                    exchange.get_funding_rate(swap_symbol),
                    exchange.get_open_interest(swap_symbol),
                ])
            elif exchange_name == "bybit":
                tasks.extend([
                    exchange.get_funding_rate(normalized_symbol),
                    exchange.get_open_interest(normalized_symbol),
                ])
            else:
                # Gate.io fallback
                tasks.extend([
                    asyncio.create_task(asyncio.sleep(0)),  # Placeholder
                    asyncio.create_task(asyncio.sleep(0)),  # Placeholder
                ])
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            ohlcv_1h = results[0] if not isinstance(results[0], Exception) else []
            ohlcv_4h = results[1] if not isinstance(results[1], Exception) else []
            ticker = results[2] if not isinstance(results[2], Exception) else None
            funding_rate = results[3] if len(results) > 3 and not isinstance(results[3], Exception) else None
            open_interest = results[4] if len(results) > 4 and not isinstance(results[4], Exception) else None
            
            if not ohlcv_1h or not ticker:
                return None
            
            return {
                "ohlcv_1h": ohlcv_1h,
                "ohlcv_4h": ohlcv_4h,
                "ticker": ticker,
                "funding_rate": funding_rate,
                "open_interest": open_interest,
                "exchange": exchange_name,
            }
        except Exception as e:
            logger.warning(f"Error getting data from {exchange_name} for {symbol}: {e}")
            return None
    
    async def _get_data_with_fallback(self, symbol: str) -> Optional[Dict]:
        """
        Получает данные с приоритетом и fallback между биржами.
        
        Args:
            symbol: Символ монеты
            
        Returns:
            Dict с данными от первой доступной биржи
        """
        for exchange_name in self.EXCHANGE_PRIORITY:
            data = await self._get_exchange_data(symbol, exchange_name)
            if data:
                logger.debug(f"Got data for {symbol} from {exchange_name}")
                return data
            await asyncio.sleep(0.1)  # Небольшая задержка перед fallback
        
        logger.warning(f"Failed to get data for {symbol} from all exchanges")
        return None
    
    async def calculate_score(self, coin: Dict) -> Optional[Dict]:
        """
        Рассчитывает score для монеты.
        
        Args:
            coin: Данные монеты от CoinGecko
            
        Returns:
            Dict с score и метриками или None
        """
        symbol = coin["symbol"]
        
        # Получаем данные с биржи
        exchange_data = await self._get_data_with_fallback(symbol)
        if not exchange_data:
            return None
        
        ohlcv_1h = exchange_data["ohlcv_1h"]
        ohlcv_4h = exchange_data["ohlcv_4h"]
        ticker = exchange_data["ticker"]
        
        # Проверка спреда
        if ticker.get("spread_pct", 1.0) > self.MAX_SPREAD_PCT:
            logger.debug(f"Skipping {symbol} due to high spread")
            return None
        
        # Извлекаем цены для расчётов
        try:
            prices_1h = [c["close"] for c in ohlcv_1h]
            highs = [c["high"] for c in ohlcv_1h]
            lows = [c["low"] for c in ohlcv_1h]
            volumes = [c["volume"] for c in ohlcv_1h]
            
            if len(prices_1h) < 20:
                return None
            
            current_price = prices_1h[-1]
            price_1h_ago = prices_1h[-2] if len(prices_1h) >= 2 else current_price
            price_4h_ago = prices_1h[-5] if len(prices_1h) >= 5 else current_price
            
            # Рассчитываем изменения цены
            change_1h = ((current_price - price_1h_ago) / price_1h_ago) * 100 if price_1h_ago > 0 else 0
            change_4h = ((current_price - price_4h_ago) / price_4h_ago) * 100 if price_4h_ago > 0 else 0
            
            # Momentum score
            momentum_score_4h = calculate_momentum_score({"1h": 0, "4h": change_4h})
            momentum_score_1h = calculate_momentum_score({"1h": change_1h, "4h": 0})
            
            # Volume score
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else volumes[-1]
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            volume_score = calculate_volume_score(current_volume, avg_volume)
            
            # Trend score (EMA + ADX)
            ema_short = calculate_ema(prices_1h, 9)
            ema_long = calculate_ema(prices_1h, 21)
            adx = calculate_adx(highs, lows, prices_1h, 14)
            trend_score = calculate_trend_score(
                {"ema_short": ema_short, "ema_long": ema_long, "price": current_price},
                adx
            )
            
            # Volatility score (упрощённый ATR + BB width)
            high_low_range = [(h - l) / l * 100 for h, l in zip(highs[-14:], lows[-14:]) if l > 0]
            atr_pct = sum(high_low_range) / len(high_low_range) if high_low_range else 2.0
            
            # BB width (упрощённо через std)
            import statistics
            price_std = statistics.stdev(prices_1h[-20:]) if len(prices_1h) >= 20 else 0
            bb_width_pct = (price_std * 2 / current_price) * 100 if current_price > 0 else 5.0
            
            volatility_score = calculate_volatility_score(atr_pct, bb_width_pct)
            
            # Фильтры
            if volume_ratio < 1.0:
                logger.debug(f"Skipping {symbol} due to low volume ratio")
                return None
            
            if bb_width_pct > 15:
                logger.debug(f"Skipping {symbol} due to high volatility")
                return None
            
            # Итоговый score
            metrics = {
                "momentum_4h": momentum_score_4h,
                "momentum_1h": momentum_score_1h,
                "volume_ratio": volume_score,
                "trend_score": trend_score,
                "volatility_score": volatility_score,
            }
            
            base_score = calculate_total_score(metrics, self.SCORING_WEIGHTS)
            
            # Применяем бонусы/штрафы
            funding_rate = exchange_data.get("funding_rate") or 0
            oi_data = exchange_data.get("open_interest")
            # TODO: Calculate actual OI change - requires historical OI data
            oi_change_pct = 0  # Placeholder until we implement OI history tracking
            
            # TODO: Calculate actual BTC correlation - requires BTC price history
            # For now, we skip BTC correlation in scoring to avoid inaccurate penalties
            btc_correlation = 0.5  # Neutral value that won't trigger penalties
            
            final_score, factors = apply_score_bonuses(
                base_score,
                funding_rate,
                oi_change_pct,
                change_4h,
                btc_correlation
            )
            
            # Определяем направление
            direction = "ЛОНГ" if change_4h > 0 else "ШОРТ"
            direction_emoji = "📈" if change_4h > 0 else "📉"
            
            return {
                "symbol": symbol,
                "name": coin["name"],
                "score": final_score,
                "price": current_price,
                "change_1h": change_1h,
                "change_4h": change_4h,
                "change_24h": coin["change_24h"],
                "volume_ratio": volume_ratio,
                "atr_pct": atr_pct,
                "bb_width_pct": bb_width_pct,
                "funding_rate": funding_rate,
                "oi_change_pct": oi_change_pct,
                "direction": direction,
                "direction_emoji": direction_emoji,
                "factors": factors,
                "adx": adx,
                "exchange": exchange_data["exchange"],
            }
        except Exception as e:
            logger.error(f"Error calculating score for {symbol}: {e}", exc_info=True)
            return None
    
    async def get_top3(self) -> Tuple[List[Dict], int, int]:
        """
        Возвращает ТОП-3 монеты с гистерезисом.
        
        Returns:
            Tuple (top3_list, scanned_count, filtered_count)
        """
        # Сканируем монеты
        coins = await self.scan_all_coins()
        scanned_count = len(coins)
        
        # Фильтруем
        filtered_coins = await self.filter_coins(coins)
        filtered_count = len(filtered_coins)
        
        # Рассчитываем scores для всех монет (с ограничением параллелизма)
        scored_coins = []
        
        # Ограничиваем количество одновременных запросов
        semaphore = asyncio.Semaphore(5)
        
        # For performance, we analyze top coins by market cap first
        # Configurable via settings.smart_signals_max_analyze
        max_coins_to_analyze = min(len(filtered_coins), self.MAX_ANALYZE)
        
        async def score_coin_with_limit(coin):
            async with semaphore:
                return await self.calculate_score(coin)
        
        tasks = [score_coin_with_limit(coin) for coin in filtered_coins[:max_coins_to_analyze]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if result and not isinstance(result, Exception):
                scored_coins.append(result)
        
        # Сортируем по score
        scored_coins.sort(key=lambda x: x["score"], reverse=True)
        
        # Применяем гистерезис
        top3 = self._apply_hysteresis(scored_coins[:10])  # Берём топ-10 для гистерезиса
        
        self.last_update = time.time()
        
        return top3[:3], scanned_count, filtered_count
    
    def _apply_hysteresis(self, candidates: List[Dict]) -> List[Dict]:
        """
        Применяет гистерезис для предотвращения "мигания" списка.
        
        Args:
            candidates: Список кандидатов, отсортированных по score
            
        Returns:
            Финальный список с учётом гистерезиса
        """
        if not self.top3_history:
            # Первый запуск - просто берём топ-3
            self.top3_history = candidates[:3]
            for coin in self.top3_history:
                coin["entry_time"] = time.time()
            return self.top3_history
        
        current_time = time.time()
        result = []
        
        for historical_coin in self.top3_history:
            symbol = historical_coin["symbol"]
            entry_time = historical_coin.get("entry_time", 0)
            time_in_top = current_time - entry_time
            
            # Монета должна остаться минимум 15 минут
            if time_in_top < self.HYSTERESIS_TIME:
                result.append(historical_coin)
                continue
            
            # Ищем эту монету в новых кандидатах
            candidate_coin = next((c for c in candidates if c["symbol"] == symbol), None)
            
            if candidate_coin:
                # Монета всё ещё в топе - обновляем данные но сохраняем entry_time
                candidate_coin["entry_time"] = entry_time
                result.append(candidate_coin)
            else:
                # Монета выпала из топа - проверяем, есть ли новая монета на 10%+ лучше
                best_new = next((c for c in candidates if c["symbol"] not in [h["symbol"] for h in self.top3_history]), None)
                
                if best_new and best_new["score"] > historical_coin["score"] * (1 + self.HYSTERESIS_THRESHOLD):
                    # Новая монета значительно лучше - заменяем
                    best_new["entry_time"] = current_time
                    result.append(best_new)
                else:
                    # Оставляем старую
                    result.append(historical_coin)
        
        # Если result содержит меньше 3 монет, добавляем из кандидатов
        existing_symbols = {c["symbol"] for c in result}
        for candidate in candidates:
            if len(result) >= 3:
                break
            if candidate["symbol"] not in existing_symbols:
                candidate["entry_time"] = current_time
                result.append(candidate)
        
        self.top3_history = result[:3]
        return result[:3]
    
    def format_message(self, top3: List[Dict], scanned_count: int, filtered_count: int) -> str:
        """
        Форматирует сообщение для Telegram.
        
        Args:
            top3: Список ТОП-3 монет
            scanned_count: Количество отсканированных монет
            filtered_count: Количество монет прошедших фильтры
            
        Returns:
            Отформатированное сообщение
        """
        now = datetime.now().strftime("%H:%M:%S")
        
        text = "📡 *УМНЫЕ СИГНАЛЫ \\(ТОП\\-3\\)*\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📊 Сканирование: {scanned_count} монет\n"
        text += f"✅ Прошли фильтры: {filtered_count} монет\n"
        text += f"⏰ Обновлено: {now}\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        
        for idx, coin in enumerate(top3):
            medal = medals[idx] if idx < len(medals) else "•"
            
            text += f"{medal} *\\#{idx + 1} {coin['symbol']}/USDT \\| {coin['direction_emoji']} {coin['direction']}*\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"💰 Цена: ${coin['price']:,.2f}\n"
            text += f"📈 Δ1h: {coin['change_1h']:+.1f}% \\| Δ4h: {coin['change_4h']:+.1f}% \\| Δ24h: {coin['change_24h']:+.1f}%\n"
            text += f"📊 Объём: {coin['volume_ratio']:.1f}x от среднего\n"
            text += f"📉 ATR: {coin['atr_pct']:.1f}% \\| BB: {coin['bb_width_pct']:.1f}%\n"
            
            if coin.get('funding_rate'):
                funding_pct = coin['funding_rate'] * 100
                text += f"💹 Funding: {funding_pct:.3f}% \\| OI: {coin['oi_change_pct']:+.1f}%\n"
            
            # Progress bar для score
            score = coin['score']
            filled = int(score)
            empty = 10 - filled
            bar = "█" * filled + "░" * empty
            text += f"🎯 Score: {score:.1f}/10 {bar}\n\n"
            
            # Факторы
            if coin.get('factors'):
                text += "✅ *Факторы:*\n"
                for factor in coin['factors']:
                    # Escape special characters
                    factor_escaped = factor.replace("_", "\\_").replace(".", "\\.").replace("-", "\\-").replace("+", "\\+").replace("(", "\\(").replace(")", "\\)").replace("%", "\\%")
                    text += f"• {factor_escaped}\n"
                text += "\n"
            
            # Уровни (упрощённо)
            current_price = coin['price']
            entry_low = current_price * 0.99
            entry_high = current_price * 1.01
            stop = current_price * 0.97 if coin['direction'] == "ЛОНГ" else current_price * 1.03
            tp1 = current_price * 1.04 if coin['direction'] == "ЛОНГ" else current_price * 0.96
            tp2 = current_price * 1.08 if coin['direction'] == "ЛОНГ" else current_price * 0.92
            
            text += "📍 *Уровни:*\n"
            text += f"• Вход: ${entry_low:,.2f}\\-{entry_high:,.2f}\n"
            text += f"• Стоп: ${stop:,.2f} \\({((stop - current_price) / current_price * 100):+.1f}%\\)\n"
            text += f"• TP1: ${tp1:,.2f} \\({((tp1 - current_price) / current_price * 100):+.1f}%\\)\n"
            text += f"• TP2: ${tp2:,.2f} \\({((tp2 - current_price) / current_price * 100):+.1f}%\\)\n"
            
            if idx < len(top3) - 1:
                text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "⏱️ Следующее обновление: по запросу\n"
        text += "⚠️ Не является финансовым советом"
        
        return text
