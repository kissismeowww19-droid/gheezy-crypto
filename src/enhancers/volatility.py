"""
Volatility Enhancer.

Анализ волатильности для умных TP/SL:
- ATR (Average True Range)
- Bollinger Bands Squeeze
- Volatility Percentile

Вес: 6%
"""

import logging
from typing import Dict, List, Optional
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class VolatilityEnhancer(BaseEnhancer):
    """
    Анализ волатильности.
    
    Параметры:
    - ATR период: 14
    - Вес: 6%
    
    Используется в основном для расчёта TP/SL, но также даёт сигналы:
    - BB Squeeze = скоро взрыв волатильности
    - Низкая волатильность = подготовка к движению
    """
    
    ATR_PERIOD = 14
    BB_PERIOD = 20
    KC_PERIOD = 20
    WEIGHT = 0.06  # 6%
    MAX_SCORE = 6.0
    
    def __init__(self):
        """Инициализация Volatility enhancer."""
        super().__init__()
        self._cache = {}
        self._cache_timeout = 600  # 10 минут кеш
    
    async def get_score(self, coin: str, **kwargs) -> float:
        """
        Получить скор волатильности.
        
        Args:
            coin: Символ монеты
            **kwargs: Дополнительные параметры
        
        Returns:
            float: Скор от -6 до +6
        
        Логика:
        - BB Squeeze = скоро взрыв = подготовка
        - Низкая волатильность = скоро движение
        - Высокая волатильность = осторожность
        """
        try:
            volatility_data = await self.get_volatility_data(coin)
            score = self._calculate_volatility_score(volatility_data)
            
            # Ограничиваем в диапазоне [-6, +6]
            final_score = self.clamp(score, -self.MAX_SCORE, self.MAX_SCORE)
            
            self.logger.info(f"Volatility score for {coin}: {final_score:.2f}")
            return final_score
            
        except Exception as e:
            self.logger.error(f"Volatility error for {coin}: {e}")
            return 0.0
    
    async def get_atr(self, coin: str, timeframe: str = "4h") -> float:
        """
        Получить текущий ATR.
        
        Args:
            coin: Символ монеты
            timeframe: Таймфрейм (4h по умолчанию)
        
        Returns:
            float: Значение ATR
        """
        # Заглушка - в реальности рассчитываем на основе OHLCV
        import random
        
        # Симулируем ATR на основе типичной цены
        base_price = 50000 if coin.upper().startswith('BTC') else 3000
        atr = base_price * random.uniform(0.01, 0.05)  # 1-5% от цены
        
        return atr
    
    async def detect_bb_squeeze(self, coin: str) -> Dict:
        """
        Обнаружить BB Squeeze (Bollinger Bands внутри Keltner Channel).
        
        Returns:
            {
                "squeeze": True,
                "squeeze_duration": 5,  # Свечей в сжатии
                "expected_breakout": "soon",  # soon/moderate/long
                "momentum": "bullish"  # На основе momentum oscillator
            }
        """
        # Заглушка - в реальности рассчитываем BB и KC
        import random
        
        squeeze = random.choice([True, False])
        squeeze_duration = random.randint(1, 12) if squeeze else 0
        
        if squeeze_duration > 8:
            expected_breakout = "soon"
        elif squeeze_duration > 4:
            expected_breakout = "moderate"
        else:
            expected_breakout = "long"
        
        momentum = random.choice(["bullish", "bearish", "neutral"])
        
        return {
            "squeeze": squeeze,
            "squeeze_duration": squeeze_duration,
            "expected_breakout": expected_breakout,
            "momentum": momentum
        }
    
    async def get_volatility_percentile(self, coin: str) -> Dict:
        """
        Получить процентиль волатильности.
        
        Returns:
            {
                "current_volatility": 2.5,  # %
                "avg_volatility_30d": 3.2,
                "percentile": 35,  # Текущая волатильность ниже 35% исторических
                "regime": "low"  # low/normal/high
            }
        """
        # Заглушка - в реальности рассчитываем на основе исторических данных
        import random
        
        current_vol = random.uniform(1.0, 5.0)
        avg_vol_30d = random.uniform(2.0, 4.0)
        percentile = random.randint(10, 90)
        
        if percentile < 30:
            regime = "low"
        elif percentile > 70:
            regime = "high"
        else:
            regime = "normal"
        
        return {
            "current_volatility": current_vol,
            "avg_volatility_30d": avg_vol_30d,
            "percentile": percentile,
            "regime": regime
        }
    
    async def get_volatility_data(self, coin: str) -> Dict:
        """
        Получить все данные о волатильности.
        
        Returns:
            Dict со всеми метриками волатильности
        """
        try:
            atr = await self.get_atr(coin)
            bb_squeeze = await self.detect_bb_squeeze(coin)
            percentile = await self.get_volatility_percentile(coin)
            
            return {
                "atr": atr,
                "bb_squeeze": bb_squeeze,
                "percentile": percentile
            }
        except Exception as e:
            self.logger.error(f"Error getting volatility data for {coin}: {e}")
            return {
                "atr": 0.0,
                "bb_squeeze": {"squeeze": False},
                "percentile": {"regime": "normal"}
            }
    
    def _calculate_volatility_score(self, data: Dict) -> float:
        """
        Рассчитать скор волатильности.
        
        Логика:
        - BB Squeeze + низкая волатильность = скоро взрыв = подготовка к сигналу
        - Высокая волатильность = осторожность (риск ложных сигналов)
        - Нормальная волатильность = нейтрально
        """
        bb_squeeze = data.get("bb_squeeze", {})
        percentile_data = data.get("percentile", {})
        
        score = 0.0
        
        # 1. BB Squeeze (вес 50%)
        if bb_squeeze.get("squeeze", False):
            momentum = bb_squeeze.get("momentum", "neutral")
            squeeze_duration = bb_squeeze.get("squeeze_duration", 0)
            
            # Чем дольше сжатие, тем сильнее будет взрыв
            strength = min(squeeze_duration / 10, 1.0)  # Максимум при 10+ свечах
            
            if momentum == "bullish":
                score += 6.0 * strength  # Ожидаем бычий взрыв
            elif momentum == "bearish":
                score -= 6.0 * strength  # Ожидаем медвежий взрыв
            else:
                # Сжатие есть, но направление неясно - информационный сигнал
                score += 2.0 * strength
        
        # 2. Volatility Percentile (вес 50%)
        regime = percentile_data.get("regime", "normal")
        percentile = percentile_data.get("percentile", 50)
        
        if regime == "low" and percentile < 20:
            # Очень низкая волатильность - скоро движение
            score += 3.0
        elif regime == "high" and percentile > 80:
            # Очень высокая волатильность - осторожность
            score -= 3.0
        
        return score
    
    def calculate_atr_from_ohlcv(self, ohlcv_data: List[Dict], period: int = 14) -> float:
        """
        Рассчитать ATR из OHLCV данных.
        
        Args:
            ohlcv_data: Список свечей с полями high, low, close
            period: Период ATR
        
        Returns:
            float: Значение ATR
        """
        if len(ohlcv_data) < period + 1:
            return 0.0
        
        true_ranges = []
        
        for i in range(1, len(ohlcv_data)):
            high = ohlcv_data[i].get('high', 0)
            low = ohlcv_data[i].get('low', 0)
            prev_close = ohlcv_data[i-1].get('close', 0)
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        # Берём последние N значений
        if len(true_ranges) >= period:
            atr = sum(true_ranges[-period:]) / period
            return atr
        
        return 0.0
