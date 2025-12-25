"""
Funding Advanced Enhancer.

Продвинутый анализ фандинга с комбинацией:
- Funding Rate (экстремальные значения)
- Open Interest изменения
- Предсказание funding тренда

Вес: 7%
"""

import logging
from typing import Dict, List, Optional
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class FundingAdvancedEnhancer(BaseEnhancer):
    """
    Продвинутый анализ Funding Rate + Open Interest.
    
    Параметры:
    - Экстремальный положительный: > 0.1%
    - Экстремальный отрицательный: < -0.05%
    - Вес: 7%
    """
    
    EXTREME_POSITIVE = 0.001  # 0.1%
    EXTREME_NEGATIVE = -0.0005  # -0.05%
    WEIGHT = 0.07  # 7%
    MAX_SCORE = 7.0
    
    def __init__(self):
        """Инициализация Funding Advanced enhancer."""
        super().__init__()
        self._cache = {}
        self._cache_timeout = 600  # 10 минут кеш
    
    async def get_score(self, coin: str, **kwargs) -> float:
        """
        Получить скор комбинации Funding + OI.
        
        Args:
            coin: Символ монеты
            **kwargs: Дополнительные параметры
        
        Returns:
            float: Скор от -7 до +7
        
        Логика:
        1. Funding экстремально положительный + OI растёт
           = Перегретый лонг = скоро разворот вниз = -score
        
        2. Funding экстремально отрицательный + OI растёт
           = Перегретый шорт = скоро разворот вверх = +score
        
        3. Funding нормальный + OI растёт + цена растёт
           = Здоровый тренд = продолжение = +score
        
        4. Funding нормальный + OI падает
           = Закрытие позиций = осторожность = 0
        """
        try:
            funding_data = await self.get_funding_data(coin)
            score = self._calculate_combined_score(funding_data)
            
            # Ограничиваем в диапазоне [-7, +7]
            final_score = self.clamp(score, -self.MAX_SCORE, self.MAX_SCORE)
            
            self.logger.info(f"Funding advanced score for {coin}: {final_score:.2f}")
            return final_score
            
        except Exception as e:
            self.logger.error(f"Funding advanced error for {coin}: {e}")
            return 0.0
    
    async def get_funding_data(self, coin: str) -> Dict:
        """
        Получить данные о фандинге и OI.
        
        Returns:
            {
                "current_funding": 0.0125,  # %
                "predicted_funding": 0.015,
                "funding_8h_avg": 0.01,
                "is_extreme": True,
                "extreme_type": "positive",  # positive/negative/none
                "oi_change_24h": 5.2,  # %
                "oi_trend": "increasing",  # increasing/decreasing/stable
                "price_change_24h": 2.5,  # %
                "signal": "bearish_reversal"  # bearish_reversal/bullish_reversal/healthy_trend/neutral
            }
        """
        # Заглушка - в реальности используем Binance/Bybit API
        import random
        
        # Симулируем funding rate
        current_funding = random.uniform(-0.002, 0.002)  # -0.2% to 0.2%
        funding_history = [random.uniform(-0.002, 0.002) for _ in range(8)]
        funding_8h_avg = sum(funding_history) / len(funding_history)
        
        # Предсказание на основе тренда
        predicted_funding = self._predict_funding(current_funding, funding_history)
        
        # Определяем экстремальность
        is_extreme = False
        extreme_type = "none"
        
        if current_funding > self.EXTREME_POSITIVE:
            is_extreme = True
            extreme_type = "positive"
        elif current_funding < self.EXTREME_NEGATIVE:
            is_extreme = True
            extreme_type = "negative"
        
        # OI изменения
        oi_change_24h = random.uniform(-10, 15)
        oi_trend = "stable"
        if oi_change_24h > 3:
            oi_trend = "increasing"
        elif oi_change_24h < -3:
            oi_trend = "decreasing"
        
        # Изменение цены
        price_change_24h = random.uniform(-5, 5)
        
        # Комбинируем сигналы
        signal = self._combine_funding_oi(
            current_funding, 
            oi_change_24h, 
            price_change_24h,
            is_extreme,
            extreme_type
        )
        
        return {
            "current_funding": current_funding,
            "predicted_funding": predicted_funding,
            "funding_8h_avg": funding_8h_avg,
            "is_extreme": is_extreme,
            "extreme_type": extreme_type,
            "oi_change_24h": oi_change_24h,
            "oi_trend": oi_trend,
            "price_change_24h": price_change_24h,
            "signal": signal
        }
    
    def _predict_funding(self, current: float, history: List[float]) -> float:
        """
        Предсказать следующий фандинг на основе тренда.
        
        Использует простую линейную экстраполяцию.
        """
        if not history:
            return current
        
        # Простой тренд: среднее изменение
        changes = []
        for i in range(1, len(history)):
            changes.append(history[i] - history[i-1])
        
        if changes:
            avg_change = sum(changes) / len(changes)
            predicted = current + avg_change
        else:
            predicted = current
        
        return predicted
    
    def _combine_funding_oi(
        self, 
        funding: float, 
        oi_change: float, 
        price_change: float,
        is_extreme: bool,
        extreme_type: str
    ) -> str:
        """
        Комбинировать сигналы funding + OI + price.
        
        Returns:
            "bearish_reversal" | "bullish_reversal" | "healthy_trend" | "neutral"
        """
        # Экстремальные случаи
        if is_extreme and extreme_type == "positive" and oi_change > 3:
            # Перегретый лонг
            return "bearish_reversal"
        elif is_extreme and extreme_type == "negative" and oi_change > 3:
            # Перегретый шорт
            return "bullish_reversal"
        
        # Здоровый тренд
        if not is_extreme:
            if oi_change > 3 and price_change > 1 and funding > 0:
                return "healthy_bullish_trend"
            elif oi_change > 3 and price_change < -1 and funding < 0:
                return "healthy_bearish_trend"
        
        # OI падает
        if oi_change < -3:
            return "position_closing"
        
        return "neutral"
    
    def _calculate_combined_score(self, data: Dict) -> float:
        """
        Рассчитать финальный скор.
        
        Логика:
        - Экстремальный положительный funding + растущий OI = разворот вниз = -score
        - Экстремальный отрицательный funding + растущий OI = разворот вверх = +score
        - Здоровый тренд = продолжение тренда
        - OI падает = нейтрально
        """
        signal = data.get("signal", "neutral")
        is_extreme = data.get("is_extreme", False)
        oi_change = data.get("oi_change_24h", 0)
        funding = data.get("current_funding", 0)
        
        score = 0.0
        
        if signal == "bearish_reversal":
            # Перегретый лонг - скоро разворот вниз
            if oi_change > 10:
                score = -7.0
            elif oi_change > 5:
                score = -5.0
            else:
                score = -3.0
        
        elif signal == "bullish_reversal":
            # Перегретый шорт - скоро разворот вверх
            if oi_change > 10:
                score = 7.0
            elif oi_change > 5:
                score = 5.0
            else:
                score = 3.0
        
        elif signal == "healthy_bullish_trend":
            # Здоровый восходящий тренд
            score = 4.0
        
        elif signal == "healthy_bearish_trend":
            # Здоровый нисходящий тренд
            score = -4.0
        
        elif signal == "position_closing":
            # Закрытие позиций - осторожность
            score = 0.0
        
        else:
            # Нейтрально
            score = 0.0
        
        return score
