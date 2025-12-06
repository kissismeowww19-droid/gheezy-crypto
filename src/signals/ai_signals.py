"""
AI Signals - анализ и прогнозирование движения цен на основе данных китов и рынка.

Анализирует активность китов и рыночные данные для прогнозирования движения цены на ближайший час.
"""

import logging
from datetime import datetime
from typing import Optional, Dict

from api_manager import get_coin_price

logger = logging.getLogger(__name__)


class AISignalAnalyzer:
    """
    Анализатор AI сигналов для криптовалют.
    
    Использует данные китов и рыночные данные для прогнозирования движения цены.
    """
    
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
        
        logger.info("AISignalAnalyzer initialized")
    
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
    
    def calculate_signal(self, whale_data: Dict, market_data: Dict) -> Dict:
        """
        Расчёт сигнала на основе данных китов и рынка.
        
        Формула:
        - whale_score = (withdrawals - deposits) / total_transactions * 40
        - price_score = min(max(change_24h * 2, -30), 30)
        - volume_score = 10 если volume высокий, иначе -10
        - total_score = whale_score + price_score + volume_score
        
        Args:
            whale_data: Данные о транзакциях китов
            market_data: Рыночные данные
            
        Returns:
            Dict с результатами анализа
        """
        # Whale score
        whale_score = 0
        if whale_data["transaction_count"] > 0:
            whale_score = (
                (whale_data["withdrawals"] - whale_data["deposits"]) 
                / whale_data["transaction_count"] 
                * 40
            )
        
        # Price score
        change_24h = market_data.get("change_24h", 0)
        price_score = min(max(change_24h * 2, -30), 30)
        
        # Volume score (считаем высоким если volume > 10B)
        volume_24h = market_data.get("volume_24h", 0)
        volume_score = 10 if volume_24h > 10_000_000_000 else -10
        
        # Total score
        total_score = whale_score + price_score + volume_score
        
        # Определяем направление и силу сигнала
        if total_score > 20:
            direction = "📈 ВВЕРХ"
            strength = "сильный"
        elif total_score > 5:
            direction = "📈 Вероятно вверх"
            strength = "средний"
        elif total_score < -20:
            direction = "📉 ВНИЗ"
            strength = "сильный"
        elif total_score < -5:
            direction = "📉 Вероятно вниз"
            strength = "средний"
        else:
            direction = "➡️ Боковик"
            strength = "слабый"
        
        # Расчёт силы сигнала в процентах (0-100%)
        # Нормализуем score от -80 до 80 в диапазон 0-100%
        strength_percent = min(max((total_score + 80) / 160 * 100, 0), 100)
        
        return {
            "direction": direction,
            "strength": strength,
            "strength_percent": round(strength_percent),
            "total_score": round(total_score, 2),
            "whale_score": round(whale_score, 2),
            "price_score": round(price_score, 2),
            "volume_score": volume_score,
        }
    
    def format_signal_message(
        self, 
        symbol: str, 
        signal_data: Dict,
        whale_data: Dict,
        market_data: Dict
    ) -> str:
        """
        Форматирование сообщения с AI сигналом.
        
        Args:
            symbol: Символ монеты
            signal_data: Результаты анализа сигнала
            whale_data: Данные о китах
            market_data: Рыночные данные
            
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
        text += f"💪 Сила сигнала: {signal_data['strength_percent']}%\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Анализ китов
        text += "🐋 *Анализ китов (1ч):*\n"
        text += f"• Транзакций: {whale_data['transaction_count']}\n"
        text += f"• Объём: {format_volume(whale_data['total_volume_usd'])}\n"
        text += f"• Депозиты на биржи: {whale_data['deposits']}\n"
        text += f"• Выводы с бирж: {whale_data['withdrawals']}\n"
        text += f"• Настроение: {sentiment_emoji.get(sentiment, '🟡')} {sentiment_text.get(sentiment, 'Нейтральное')}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Рыночные данные
        text += "📊 *Рыночные данные:*\n"
        text += f"• Цена: {format_price(market_data['price_usd'])}\n"
        text += f"• Изменение 24ч: {market_data['change_24h']:+.2f}%\n"
        text += f"• Объём 24ч: {format_volume(market_data['volume_24h'])}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Предупреждение
        text += "⚠️ _Это не финансовый совет.\n"
        text += "Всегда проводите собственный анализ._\n\n"
        
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
            # Получаем данные
            whale_data = await self.get_whale_data(symbol)
            market_data = await self.get_market_data(symbol)
            
            # Проверяем доступность данных
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
            
            # Расчёт сигнала
            signal_data = self.calculate_signal(whale_data, market_data)
            
            # Форматирование сообщения
            message = self.format_signal_message(
                symbol,
                signal_data,
                whale_data,
                market_data
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return (
                "❌ *Ошибка анализа*\n\n"
                f"Произошла ошибка при анализе {symbol}.\n"
                "Попробуйте позже."
            )
