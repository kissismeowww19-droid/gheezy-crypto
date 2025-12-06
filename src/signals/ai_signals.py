"""
AI Signals - анализ и прогнозирование движения цен на основе данных китов и рынка.

Анализирует активность китов и рыночные данные для прогнозирования движения цены на ближайший час.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import aiohttp

from api_manager import get_coin_price
from signals.indicators import calculate_rsi, calculate_macd, calculate_bollinger_bands

logger = logging.getLogger(__name__)


class AISignalAnalyzer:
    """
    Анализатор AI сигналов для криптовалют.
    
    Использует данные китов и рыночные данные для прогнозирования движения цены.
    """
    
    # Константы для расчёта сигнала
    WHALE_SCORE_WEIGHT = 40  # Максимальный вес whale score
    PRICE_SCORE_WEIGHT = 30  # Максимальный вес price score
    VOLUME_SCORE_VALUE = 10  # Значение volume score
    HIGH_VOLUME_THRESHOLD = 10_000_000_000  # Порог высокого объёма ($10B)
    
    # Константы для нормализации score в проценты (диапазон -80 до +80)
    MIN_SCORE = -80  # Минимальный возможный score
    MAX_SCORE = 80   # Максимальный возможный score
    SCORE_RANGE = MAX_SCORE - MIN_SCORE  # Полный диапазон score (160)
    
    # Новые константы для расширенного анализа
    CACHE_TTL_PRICE_HISTORY = 300  # 5 минут
    CACHE_TTL_FEAR_GREED = 1800  # 30 минут
    CACHE_TTL_FUNDING_RATE = 300  # 5 минут
    MIN_PRICE_POINTS = 30  # Минимум точек для индикаторов
    
    # Веса для нового алгоритма
    NEW_WHALE_WEIGHT = 25
    NEW_MARKET_WEIGHT = 20
    NEW_TECHNICAL_WEIGHT = 35
    NEW_FG_WEIGHT = 10
    NEW_FR_WEIGHT = 10
    
    def __init__(self, whale_tracker):
        """
        Инициализация анализатора.
        
        Args:
            whale_tracker: Экземпляр WhaleTracker для получения данных о транзакциях китов
        """
        self.whale_tracker = whale_tracker
        
        # Маппинг символов для whale tracker
        self.blockchain_mapping = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
        }
        
        # Маппинг для CoinGecko API
        self.coingecko_mapping = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
        }
        
        # Маппинг для Binance Futures
        self.binance_mapping = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
        }
        
        # Простой кэш для внешних API
        self._cache = {}
        self._cache_timestamps = {}
        
        logger.info("AISignalAnalyzer initialized")
    
    def _get_cache(self, key: str, ttl_seconds: int) -> Optional[Dict]:
        """
        Получить данные из кэша, если они еще актуальны.
        
        Args:
            key: Ключ кэша
            ttl_seconds: Время жизни кэша в секундах
            
        Returns:
            Данные из кэша или None если кэш устарел
        """
        if key not in self._cache:
            return None
        
        age = datetime.now() - self._cache_timestamps.get(key, datetime.min)
        if age > timedelta(seconds=ttl_seconds):
            return None
        
        return self._cache[key]
    
    def _set_cache(self, key: str, value: Dict):
        """
        Сохранить данные в кэш.
        
        Args:
            key: Ключ кэша
            value: Данные для сохранения
        """
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()
    
    async def get_whale_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение данных о транзакциях китов за последний час.
        
        Args:
            symbol: Символ монеты (BTC, ETH)
            
        Returns:
            Dict с данными китов или None если данные недоступны
        """
        try:
            blockchain = self.blockchain_mapping.get(symbol)
            if not blockchain:
                logger.warning(f"Unknown symbol for whale tracking: {symbol}")
                return None
            
            # Получаем транзакции для конкретного блокчейна
            transactions = await self.whale_tracker.get_transactions_by_blockchain(
                blockchain=blockchain.lower(),
                limit=50
            )
            
            if not transactions:
                logger.info(f"No whale transactions found for {symbol}")
                return {
                    "transaction_count": 0,
                    "total_volume_usd": 0,
                    "deposits": 0,
                    "withdrawals": 0,
                    "largest_transaction": 0,
                    "sentiment": "neutral"
                }
            
            # Подсчитываем депозиты и выводы
            deposits = sum(1 for tx in transactions if tx.is_exchange_deposit)
            withdrawals = sum(1 for tx in transactions if tx.is_exchange_withdrawal)
            total_volume = sum(tx.amount_usd for tx in transactions)
            largest_tx = max((tx.amount_usd for tx in transactions), default=0)
            
            # Определяем настроение
            if withdrawals > deposits:
                sentiment = "bullish"
            elif deposits > withdrawals:
                sentiment = "bearish"
            else:
                sentiment = "neutral"
            
            return {
                "transaction_count": len(transactions),
                "total_volume_usd": total_volume,
                "deposits": deposits,
                "withdrawals": withdrawals,
                "largest_transaction": largest_tx,
                "sentiment": sentiment
            }
            
        except Exception as e:
            logger.error(f"Error getting whale data for {symbol}: {e}")
            return None
    
    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение рыночных данных.
        
        Args:
            symbol: Символ монеты (BTC, ETH)
            
        Returns:
            Dict с рыночными данными или None если данные недоступны
        """
        try:
            price_data = await get_coin_price(symbol)
            
            if not price_data.get("success"):
                logger.warning(f"Failed to get market data for {symbol}")
                return None
            
            return {
                "price_usd": price_data.get("price_usd", 0),
                "change_24h": price_data.get("change_24h", 0),
                "volume_24h": price_data.get("volume_24h", 0),
                "market_cap": price_data.get("market_cap", 0),
            }
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
    
    async def get_price_history(self, symbol: str, days: int = 1) -> Optional[List[float]]:
        """
        Получение исторических цен для расчёта индикаторов.
        Использует CoinGecko API: /coins/{id}/market_chart
        
        Args:
            symbol: BTC или ETH
            days: Количество дней (1 день = ~288 точек при интервале 5 мин)
        
        Returns:
            List[float]: Список цен закрытия
        """
        cache_key = f"price_history_{symbol}_{days}"
        
        # Проверяем кэш
        cached_data = self._get_cache(cache_key, self.CACHE_TTL_PRICE_HISTORY)
        if cached_data is not None:
            return cached_data
        
        try:
            coin_id = self.coingecko_mapping.get(symbol)
            if not coin_id:
                logger.warning(f"Unknown coin for price history: {symbol}")
                return None
            
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": "usd",
                "days": days
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices = [price[1] for price in data.get("prices", [])]
                        
                        if prices:
                            self._set_cache(cache_key, prices)
                            logger.info(f"Fetched {len(prices)} price points for {symbol}")
                            return prices
                    elif response.status == 429:
                        logger.warning(f"CoinGecko rate limit reached for {symbol}")
                        return None
                    else:
                        logger.warning(f"Failed to fetch price history for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting price history for {symbol}: {e}")
            return None
    
    async def calculate_technical_indicators(self, symbol: str) -> Optional[Dict]:
        """
        Расчёт технических индикаторов.
        
        Returns:
            Dict с RSI, MACD, Bollinger Bands данными
        """
        try:
            # Получаем исторические данные
            prices = await self.get_price_history(symbol, days=1)
            
            if not prices or len(prices) < self.MIN_PRICE_POINTS:
                logger.warning(f"Insufficient price data for technical indicators: {symbol}")
                return None
            
            # Рассчитываем индикаторы
            rsi = calculate_rsi(prices, period=14)
            macd = calculate_macd(prices)
            bb = calculate_bollinger_bands(prices, period=20)
            
            if not rsi and not macd and not bb:
                logger.warning(f"Failed to calculate any technical indicators for {symbol}")
                return None
            
            result = {}
            
            if rsi:
                result["rsi"] = {
                    "value": rsi.value,
                    "signal": rsi.signal,
                    "period": rsi.period
                }
            
            if macd:
                result["macd"] = {
                    "macd_line": macd.macd_line,
                    "signal_line": macd.signal_line,
                    "histogram": macd.histogram,
                    "signal": macd.signal
                }
            
            if bb:
                result["bollinger_bands"] = {
                    "upper": bb.upper,
                    "middle": bb.middle,
                    "lower": bb.lower,
                    "current_price": bb.current_price,
                    "position": bb.position,
                    "bandwidth": bb.bandwidth,
                    "percent_b": bb.percent_b
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators for {symbol}: {e}")
            return None
    
    async def get_fear_greed_index(self) -> Optional[Dict]:
        """
        Получение Fear & Greed Index.
        API: https://api.alternative.me/fng/
        
        Returns:
            Dict: {"value": 75, "classification": "Greed"}
        """
        cache_key = "fear_greed_index"
        
        # Проверяем кэш
        cached_data = self._get_cache(cache_key, self.CACHE_TTL_FEAR_GREED)
        if cached_data is not None:
            return cached_data
        
        try:
            url = "https://api.alternative.me/fng/"
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        fng_data = data.get("data", [{}])[0]
                        
                        result = {
                            "value": int(fng_data.get("value", 50)),
                            "classification": fng_data.get("value_classification", "Neutral")
                        }
                        
                        self._set_cache(cache_key, result)
                        logger.info(f"Fetched Fear & Greed Index: {result['value']}")
                        return result
                    else:
                        logger.warning(f"Failed to fetch Fear & Greed Index: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting Fear & Greed Index: {e}")
            return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        Получение Funding Rate с Binance.
        API: https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1
        
        Returns:
            Dict: {"rate": 0.0001, "rate_percent": 0.01}
        """
        cache_key = f"funding_rate_{symbol}"
        
        # Проверяем кэш
        cached_data = self._get_cache(cache_key, self.CACHE_TTL_FUNDING_RATE)
        if cached_data is not None:
            return cached_data
        
        try:
            binance_symbol = self.binance_mapping.get(symbol)
            if not binance_symbol:
                logger.warning(f"Unknown symbol for funding rate: {symbol}")
                return None
            
            url = "https://fapi.binance.com/fapi/v1/fundingRate"
            params = {
                "symbol": binance_symbol,
                "limit": 1
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data and len(data) > 0:
                            funding_rate = float(data[0].get("fundingRate", 0))
                            rate_percent = funding_rate * 100
                            
                            result = {
                                "rate": funding_rate,
                                "rate_percent": rate_percent
                            }
                            
                            self._set_cache(cache_key, result)
                            logger.info(f"Fetched funding rate for {symbol}: {rate_percent:.4f}%")
                            return result
                        else:
                            logger.warning(f"Empty funding rate data for {symbol}")
                            return None
                    else:
                        logger.warning(f"Failed to fetch funding rate for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            return None
    
    def calculate_signal(self, whale_data: Dict, market_data: Dict, technical_data: Optional[Dict] = None, 
                        fear_greed: Optional[Dict] = None, funding_rate: Optional[Dict] = None) -> Dict:
        """
        Расширенный расчёт сигнала.
        
        Веса факторов:
        - Whale score: 25%
        - Technical score (RSI + MACD + BB): 35%
        - Market score (price change + volume): 20%
        - Fear & Greed: 10%
        - Funding Rate: 10%
        
        Technical score breakdown:
        - RSI: если < 30 = +15 (перепродан, покупка), если > 70 = -15 (перекуплен, продажа)
        - MACD: если bullish = +10, если bearish = -10
        - BB: если below_lower = +10, если above_upper = -10
        
        Fear & Greed score:
        - < 25 (Extreme Fear) = +10 (покупка)
        - > 75 (Extreme Greed) = -10 (продажа)
        
        Funding Rate score:
        - < -0.01% = +10 (shorts paying longs, bullish)
        - > 0.05% = -10 (longs paying shorts, bearish)
        
        Args:
            whale_data: Данные о транзакциях китов
            market_data: Рыночные данные
            technical_data: Технические индикаторы (опционально)
            fear_greed: Fear & Greed Index (опционально)
            funding_rate: Funding Rate (опционально)
            
        Returns:
            Dict с результатами анализа
        """
        # Whale score (максимум ±25)
        whale_score = 0
        total_exchange_txs = whale_data["withdrawals"] + whale_data["deposits"]
        if total_exchange_txs > 0:
            whale_score = (
                (whale_data["withdrawals"] - whale_data["deposits"]) 
                / total_exchange_txs
                * self.NEW_WHALE_WEIGHT
            )
        
        # Market score (максимум ±20)
        change_24h = market_data.get("change_24h", 0)
        # Price change contribution (max ±15)
        price_score = min(max(change_24h * 1.5, -15), 15)
        
        # Volume contribution (max ±5)
        volume_24h = market_data.get("volume_24h", 0)
        volume_score = 5 if volume_24h > self.HIGH_VOLUME_THRESHOLD else -5
        
        market_score = price_score + volume_score
        
        # Technical score (максимум ±35)
        technical_score = 0
        rsi_score = 0
        macd_score = 0
        bb_score = 0
        
        if technical_data:
            # RSI score (max ±15)
            if "rsi" in technical_data:
                rsi_value = technical_data["rsi"]["value"]
                if rsi_value < 30:
                    rsi_score = 15  # Перепродан - покупка
                elif rsi_value > 70:
                    rsi_score = -15  # Перекуплен - продажа
                else:
                    # Градиент в диапазоне 30-70
                    rsi_score = (50 - rsi_value) / 40 * 10
            
            # MACD score (max ±10)
            if "macd" in technical_data:
                macd_signal = technical_data["macd"]["signal"]
                if macd_signal == "bullish":
                    macd_score = 10
                elif macd_signal == "bearish":
                    macd_score = -10
            
            # Bollinger Bands score (max ±10)
            if "bollinger_bands" in technical_data:
                bb_position = technical_data["bollinger_bands"]["position"]
                if bb_position == "below_lower":
                    bb_score = 10  # Ниже нижней полосы - покупка
                elif bb_position == "above_upper":
                    bb_score = -10  # Выше верхней полосы - продажа
                elif bb_position == "lower_half":
                    bb_score = 3  # Нижняя половина - слабый сигнал на покупку
                elif bb_position == "upper_half":
                    bb_score = -3  # Верхняя половина - слабый сигнал на продажу
            
            technical_score = rsi_score + macd_score + bb_score
        
        # Fear & Greed score (максимум ±10)
        fg_score = 0
        if fear_greed:
            fg_value = fear_greed.get("value", 50)
            if fg_value < 25:
                fg_score = 10  # Extreme Fear - покупка
            elif fg_value > 75:
                fg_score = -10  # Extreme Greed - продажа
            else:
                # Градиент в диапазоне 25-75
                fg_score = (50 - fg_value) / 50 * 7
        
        # Funding Rate score (максимум ±10)
        fr_score = 0
        if funding_rate:
            rate_percent = funding_rate.get("rate_percent", 0)
            if rate_percent < -0.01:
                fr_score = 10  # Shorts paying longs - bullish
            elif rate_percent > 0.05:
                fr_score = -10  # Longs paying shorts - bearish
            else:
                # Градиент в диапазоне -0.01 до 0.05
                # Нормализуем: 0.02% это нейтрально (0 очков)
                if rate_percent < 0.02:
                    # От -0.01 до 0.02: от +10 до 0
                    fr_score = (0.02 - rate_percent) / 0.03 * 10
                else:
                    # От 0.02 до 0.05: от 0 до -10
                    fr_score = (0.02 - rate_percent) / 0.03 * 10
        
        # Total score
        total_score = whale_score + market_score + technical_score + fg_score + fr_score
        
        # Определяем направление и силу сигнала
        if total_score > 20:
            direction = "📈 ВВЕРХ"
            strength = "сильный"
            confidence = "Высокая"
        elif total_score > 10:
            direction = "📈 Вероятно вверх"
            strength = "средний"
            confidence = "Средняя"
        elif total_score < -20:
            direction = "📉 ВНИЗ"
            strength = "сильный"
            confidence = "Высокая"
        elif total_score < -10:
            direction = "📉 Вероятно вниз"
            strength = "средний"
            confidence = "Средняя"
        else:
            direction = "➡️ Боковик"
            strength = "слабый"
            confidence = "Низкая"
        
        # Расчёт силы сигнала в процентах (0-100%)
        # Максимальный возможный score: 25+35+20+10+10 = 100
        # Минимальный возможный score: -100
        # Нормализуем score от -100 до +100 в диапазон 0-100%
        strength_percent = min(max((total_score + 100) / 200 * 100, 0), 100)
        
        return {
            "direction": direction,
            "strength": strength,
            "strength_percent": round(strength_percent),
            "confidence": confidence,
            "total_score": round(total_score, 2),
            "whale_score": round(whale_score, 2),
            "market_score": round(market_score, 2),
            "technical_score": round(technical_score, 2),
            "rsi_score": round(rsi_score, 2),
            "macd_score": round(macd_score, 2),
            "bb_score": round(bb_score, 2),
            "fg_score": round(fg_score, 2),
            "fr_score": round(fr_score, 2),
        }
    
    def format_signal_message(
        self, 
        symbol: str, 
        signal_data: Dict,
        whale_data: Dict,
        market_data: Dict,
        technical_data: Optional[Dict] = None,
        fear_greed: Optional[Dict] = None,
        funding_rate: Optional[Dict] = None
    ) -> str:
        """
        Форматирование сообщения с AI сигналом.
        
        Args:
            symbol: Символ монеты
            signal_data: Результаты анализа сигнала
            whale_data: Данные о китах
            market_data: Рыночные данные
            technical_data: Технические индикаторы (опционально)
            fear_greed: Fear & Greed Index (опционально)
            funding_rate: Funding Rate (опционально)
            
        Returns:
            Форматированное сообщение для Telegram
        """
        # Форматирование объёмов
        def format_volume(volume: float) -> str:
            if volume >= 1_000_000_000:
                return f"${volume / 1_000_000_000:.1f}B"
            elif volume >= 1_000_000:
                return f"${volume / 1_000_000:.1f}M"
            elif volume >= 1_000:
                return f"${volume / 1_000:.1f}K"
            return f"${volume:.0f}"
        
        # Форматирование цены
        def format_price(price: float) -> str:
            if price >= 1000:
                return f"${price:,.0f}"
            elif price >= 1:
                return f"${price:,.2f}"
            else:
                return f"${price:.6f}"
        
        # Эмодзи настроения китов
        sentiment_emoji = {
            "bullish": "🟢",
            "bearish": "🔴",
            "neutral": "🟡"
        }
        
        sentiment = whale_data.get("sentiment", "neutral")
        sentiment_text = {
            "bullish": "Бычье",
            "bearish": "Медвежье",
            "neutral": "Нейтральное"
        }
        
        # Формируем сообщение
        text = f"🤖 *AI СИГНАЛ: {symbol}*\n\n"
        text += f"⏰ Прогноз на 1 час: {signal_data['direction']}\n"
        text += f"💪 Сила сигнала: {signal_data['strength_percent']}%\n"
        text += f"📊 Уверенность: {signal_data['confidence']}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Анализ китов
        text += "🐋 *Анализ китов (1ч):*\n"
        text += f"• Транзакций: {whale_data['transaction_count']} | Объём: {format_volume(whale_data['total_volume_usd'])}\n"
        
        deposits_emoji = "⬇️" if whale_data['deposits'] > whale_data['withdrawals'] else ""
        withdrawals_emoji = "⬆️" if whale_data['withdrawals'] > whale_data['deposits'] else ""
        
        text += f"• Депозиты: {whale_data['deposits']} {deposits_emoji} | Выводы: {whale_data['withdrawals']} {withdrawals_emoji}\n"
        
        whale_score = signal_data.get('whale_score', 0)
        whale_score_sign = "+" if whale_score >= 0 else ""
        text += f"• Настроение: {sentiment_emoji.get(sentiment, '🟡')} {sentiment_text.get(sentiment, 'Нейтральное')} ({whale_score_sign}{whale_score:.0f} очков)\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Технический анализ
        if technical_data:
            text += "📈 *Технический анализ:*\n\n"
            
            # RSI
            if "rsi" in technical_data:
                rsi_value = technical_data["rsi"]["value"]
                rsi_signal = technical_data["rsi"]["signal"]
                
                if rsi_signal == "oversold":
                    rsi_zone = "перепроданность"
                    rsi_emoji = "⬇️"
                    rsi_action = "Покупать"
                elif rsi_signal == "overbought":
                    rsi_zone = "перекупленность"
                    rsi_emoji = "⬆️"
                    rsi_action = "Продавать"
                else:
                    rsi_zone = "нормальная"
                    rsi_emoji = "➡️"
                    rsi_action = "Держать"
                
                text += f"RSI (14): {rsi_value:.1f} — "
                if rsi_signal == "neutral":
                    text += "Нейтрально\n"
                else:
                    text += f"{rsi_zone.capitalize()}\n"
                text += f"├─ Зона: 30-70 ({rsi_zone})\n"
                text += f"└─ Сигнал: {rsi_emoji} {rsi_action}\n\n"
            
            # MACD
            if "macd" in technical_data:
                macd = technical_data["macd"]
                macd_signal = macd["signal"]
                
                if macd_signal == "bullish":
                    macd_text = "Бычий ✅"
                elif macd_signal == "bearish":
                    macd_text = "Медвежий ❌"
                else:
                    macd_text = "Нейтральный ➡️"
                
                text += f"MACD: {macd_text}\n"
                text += f"├─ Линия: {macd['macd_line']:.1f}\n"
                text += f"├─ Сигнал: {macd['signal_line']:.1f}\n"
                text += f"└─ Гистограмма: {macd['histogram']:+.1f}\n\n"
            
            # Bollinger Bands
            if "bollinger_bands" in technical_data:
                bb = technical_data["bollinger_bands"]
                bb_position = bb["position"]
                
                if bb_position == "above_upper":
                    position_text = "Выше верхней полосы"
                elif bb_position == "below_lower":
                    position_text = "Ниже нижней полосы"
                elif bb_position == "upper_half":
                    position_text = "Верхняя половина"
                else:
                    position_text = "Нижняя половина"
                
                bandwidth = bb["bandwidth"]
                if bandwidth < 3:
                    vol_text = "низкая волатильность"
                elif bandwidth > 6:
                    vol_text = "высокая волатильность"
                else:
                    vol_text = "средняя волатильность"
                
                text += "Bollinger Bands:\n"
                text += f"├─ Позиция: {position_text}\n"
                text += f"├─ Ширина: {bandwidth:.1f}% ({vol_text})\n"
                text += f"└─ %B: {bb['percent_b']:.2f}\n\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Fear & Greed Index
        if fear_greed:
            fg_value = fear_greed["value"]
            fg_class = fear_greed["classification"]
            text += f"😱 *Fear & Greed Index:* {fg_value} — {fg_class}\n"
        
        # Funding Rate
        if funding_rate:
            rate_percent = funding_rate["rate_percent"]
            if rate_percent < -0.01:
                fr_text = "Бычье"
            elif rate_percent > 0.05:
                fr_text = "Медвежье"
            else:
                fr_text = "Нейтрально"
            text += f"📊 *Funding Rate:* {rate_percent:+.3f}% — {fr_text}\n"
        
        if fear_greed or funding_rate:
            text += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Рыночные данные
        text += "📊 *Рыночные данные:*\n"
        text += f"• Цена: {format_price(market_data['price_usd'])}\n"
        text += f"• 24ч: {market_data['change_24h']:+.1f}%\n"
        text += f"• Объём 24ч: {format_volume(market_data['volume_24h'])}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Breakdown сигнала
        breakdown_lines = []
        breakdown_lines.append(f"🐋 Киты: {signal_data['whale_score']:+.0f}")
        
        if technical_data:
            breakdown_lines.append(f"📈 Техника: {signal_data['technical_score']:+.0f}")
        
        breakdown_lines.append(f"📊 Рынок: {signal_data['market_score']:+.0f}")
        
        if fear_greed:
            breakdown_lines.append(f"😱 F&G: {signal_data['fg_score']:+.0f}")
        
        if funding_rate:
            breakdown_lines.append(f"💰 Funding: {signal_data['fr_score']:+.0f}")
        
        text += "🎯 *Breakdown сигнала:*\n"
        for i, line in enumerate(breakdown_lines):
            if i == len(breakdown_lines) - 1:
                text += f"└─ {line}\n"
            else:
                text += f"├─ {line}\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += f"*Итого: {signal_data['total_score']:+.0f} очков*\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Предупреждение
        text += "⚠️ _Не является финансовым советом.\n"
        text += "Проводите собственный анализ._\n\n"
        
        # Время обновления
        now = datetime.now()
        text += f"🕐 _Обновлено: {now.strftime('%H:%M:%S')}_"
        
        return text
    
    async def analyze_coin(self, symbol: str) -> str:
        """
        Полный анализ монеты и генерация сигнала.
        
        Args:
            symbol: Символ монеты (BTC, ETH)
            
        Returns:
            Форматированное сообщение с AI сигналом
        """
        symbol = symbol.upper()
        
        # Проверяем поддержку монеты
        if symbol not in self.blockchain_mapping:
            return (
                f"❌ *Ошибка*\n\n"
                f"Монета {symbol} пока не поддерживается.\n\n"
                f"Доступны: BTC, ETH"
            )
        
        try:
            # Получаем основные данные
            whale_data = await self.get_whale_data(symbol)
            market_data = await self.get_market_data(symbol)
            
            # Проверяем доступность основных данных
            if market_data is None:
                return (
                    "❌ *Ошибка получения данных*\n\n"
                    "Не удалось загрузить рыночные данные.\n"
                    "Попробуйте позже."
                )
            
            # Если данные китов недоступны, используем нулевые значения
            if whale_data is None:
                logger.warning(f"Whale data unavailable for {symbol}, using market data only")
                whale_data = {
                    "transaction_count": 0,
                    "total_volume_usd": 0,
                    "deposits": 0,
                    "withdrawals": 0,
                    "largest_transaction": 0,
                    "sentiment": "neutral"
                }
            
            # Получаем дополнительные данные (необязательные)
            technical_data = await self.calculate_technical_indicators(symbol)
            fear_greed = await self.get_fear_greed_index()
            funding_rate = await self.get_funding_rate(symbol)
            
            # Логируем доступность дополнительных данных
            if technical_data is None:
                logger.info(f"Technical indicators unavailable for {symbol}, using simplified analysis")
            if fear_greed is None:
                logger.info(f"Fear & Greed Index unavailable, skipping this factor")
            if funding_rate is None:
                logger.info(f"Funding rate unavailable for {symbol}, skipping this factor")
            
            # Расчёт сигнала
            signal_data = self.calculate_signal(
                whale_data, 
                market_data,
                technical_data,
                fear_greed,
                funding_rate
            )
            
            # Форматирование сообщения
            message = self.format_signal_message(
                symbol,
                signal_data,
                whale_data,
                market_data,
                technical_data,
                fear_greed,
                funding_rate
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return (
                "❌ *Ошибка анализа*\n\n"
                f"Произошла ошибка при анализе {symbol}.\n"
                "Попробуйте позже."
            )
