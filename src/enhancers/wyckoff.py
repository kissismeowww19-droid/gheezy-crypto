"""
Wyckoff Analysis Enhancer - анализ фаз рынка по методологии Wyckoff.

Компоненты:
1. Accumulation - фаза накопления
2. Distribution - фаза распределения
3. Spring - ложный пробой вниз
4. UTAD - ложный пробой вверх
"""

import logging
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class WyckoffEnhancer(BaseEnhancer):
    """
    Анализатор Wyckoff фаз рынка.
    
    Параметры:
    - Таймфрейм: 1D
    - Вес в сигнале: 10%
    """
    
    # Константы
    TIMEFRAME = "1d"
    WEIGHT = 0.10  # 10%
    
    # Маппинг символов
    SYMBOL_MAPPING = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT",
        "TON": "TONUSDT",
    }
    
    def __init__(self):
        """Инициализация Wyckoff Enhancer."""
        super().__init__()
        self._cache = {}
        self._cache_ttl = 3600  # 1 час кэш
    
    async def get_score(self, coin: str, current_price: float = None, **kwargs) -> float:
        """
        Получить скор Wyckoff для монеты.
        
        Возвращает скор от -10 до +10:
        - Accumulation phase = +score (готовится рост)
        - Distribution phase = -score (готовится падение)
        - Spring detected = сильный +score
        - UTAD detected = сильный -score
        
        Args:
            coin: Символ монеты (BTC, ETH, etc.)
            current_price: Текущая цена
        
        Returns:
            float: Скор от -10 до +10
        """
        try:
            coin = coin.upper()
            
            # Если цена не передана, получаем её
            if current_price is None:
                current_price = await self._get_current_price(coin)
                if current_price is None:
                    self.logger.warning(f"Cannot get current price for {coin}")
                    return 0.0
            
            # Получаем фазу Wyckoff
            wyckoff_phase = await self.get_wyckoff_phase(coin)
            
            if not wyckoff_phase:
                self.logger.warning(f"No Wyckoff phase data for {coin}")
                return 0.0
            
            # Рассчитываем скор
            score = self._calculate_score(wyckoff_phase)
            
            # Ограничиваем в диапазоне [-10, 10]
            score = self.clamp(score, -10.0, 10.0)
            
            self.logger.info(
                f"Wyckoff score for {coin}: {score:.2f} "
                f"(Phase: {wyckoff_phase.get('phase', 'unknown')}, "
                f"Sub-phase: {wyckoff_phase.get('sub_phase', 'none')}, "
                f"Confidence: {wyckoff_phase.get('confidence', 0):.2f})"
            )
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error calculating Wyckoff score for {coin}: {e}", exc_info=True)
            return 0.0
    
    async def get_wyckoff_phase(self, coin: str) -> Dict:
        """
        Определить текущую фазу Wyckoff.
        
        Returns:
            Dict: {
                "phase": "accumulation",  # или "distribution", "markup", "markdown"
                "sub_phase": "spring",    # или "utad", "sos", "sow", "none"
                "confidence": 0.75,
                "signal": "bullish"       # или "bearish", "neutral"
            }
        """
        try:
            # Получаем дневные свечи
            candles = await self._get_candles(coin, interval='1d', limit=100)
            
            if not candles or len(candles) < 30:
                return {}
            
            # Извлекаем объёмы
            volumes = [c['volume'] for c in candles]
            
            # Проверяем Accumulation
            accumulation = self._detect_accumulation(candles, volumes)
            if accumulation.get('detected'):
                return {
                    'phase': 'accumulation',
                    'sub_phase': accumulation.get('phase', 'none'),
                    'confidence': accumulation.get('confidence', 0.5),
                    'signal': 'bullish'
                }
            
            # Проверяем Distribution
            distribution = self._detect_distribution(candles, volumes)
            if distribution.get('detected'):
                return {
                    'phase': 'distribution',
                    'sub_phase': distribution.get('phase', 'none'),
                    'confidence': distribution.get('confidence', 0.5),
                    'signal': 'bearish'
                }
            
            # Определяем тренд (markup/markdown)
            trend = self._detect_trend(candles)
            
            return {
                'phase': trend,
                'sub_phase': 'none',
                'confidence': 0.3,
                'signal': 'neutral'
            }
            
        except Exception as e:
            self.logger.error(f"Error getting Wyckoff phase for {coin}: {e}", exc_info=True)
            return {}
    
    async def _get_current_price(self, coin: str) -> Optional[float]:
        """Получить текущую цену с Binance."""
        try:
            symbol = self.SYMBOL_MAPPING.get(coin, f"{coin}USDT")
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return float(data['price'])
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting current price for {coin}: {e}")
            return None
    
    async def _get_candles(self, coin: str, interval: str = '1d', limit: int = 100) -> List[Dict]:
        """Получить свечи с Binance."""
        try:
            symbol = self.SYMBOL_MAPPING.get(coin, f"{coin}USDT")
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        candles = []
                        for candle in data:
                            candles.append({
                                'timestamp': candle[0],
                                'open': float(candle[1]),
                                'high': float(candle[2]),
                                'low': float(candle[3]),
                                'close': float(candle[4]),
                                'volume': float(candle[5])
                            })
                        return candles
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting candles for {coin}: {e}")
            return []
    
    def _detect_accumulation(self, candles: List[Dict], volumes: List[float]) -> Dict:
        """
        Определить фазу накопления (Accumulation).
        
        Признаки:
        1. PS (Preliminary Support) - первая поддержка
        2. SC (Selling Climax) - кульминация продаж, высокий объём
        3. AR (Automatic Rally) - автоматический отскок
        4. ST (Secondary Test) - повторный тест минимума
        5. Spring - ложный пробой ниже поддержки
        6. SOS (Sign of Strength) - признак силы, пробой сопротивления
        
        Returns:
            Dict: {"detected": True, "phase": "spring", "confidence": 0.75}
        """
        try:
            if len(candles) < 30:
                return {'detected': False}
            
            # Анализируем последние 30-50 свечей
            recent_candles = candles[-50:]
            recent_volumes = volumes[-50:]
            
            # Находим локальный минимум (SC - Selling Climax)
            min_price = min(c['low'] for c in recent_candles)
            min_index = next(i for i, c in enumerate(recent_candles) if c['low'] == min_price)
            
            # Проверяем высокий объём на минимуме (признак SC)
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            sc_volume = recent_volumes[min_index]
            
            if sc_volume < avg_volume * 1.5:
                return {'detected': False}
            
            # Проверяем AR (Automatic Rally) - отскок после SC
            if min_index >= len(recent_candles) - 5:
                return {'detected': False}
            
            ar_candles = recent_candles[min_index + 1:min_index + 6]
            ar_high = max(c['high'] for c in ar_candles)
            ar_move = (ar_high - min_price) / min_price * 100
            
            if ar_move < 3.0:  # Минимум 3% отскок
                return {'detected': False}
            
            # Определяем диапазон накопления
            support_level = min_price
            resistance_level = ar_high
            
            # Проверяем Spring (ложный пробой поддержки)
            spring_detected = self._detect_spring(recent_candles[min_index:], support_level)
            
            if spring_detected:
                return {
                    'detected': True,
                    'phase': 'spring',
                    'confidence': 0.85
                }
            
            # Проверяем боковое движение в диапазоне (признак накопления)
            range_candles = recent_candles[min_index:]
            in_range_count = sum(
                1 for c in range_candles 
                if support_level * 0.98 <= c['low'] and c['high'] <= resistance_level * 1.02
            )
            
            if in_range_count / len(range_candles) > 0.6:
                return {
                    'detected': True,
                    'phase': 'secondary_test',
                    'confidence': 0.65
                }
            
            return {'detected': False}
            
        except Exception as e:
            self.logger.error(f"Error detecting accumulation: {e}")
            return {'detected': False}
    
    def _detect_distribution(self, candles: List[Dict], volumes: List[float]) -> Dict:
        """
        Определить фазу распределения (Distribution).
        
        Признаки:
        1. PSY (Preliminary Supply) - первое сопротивление
        2. BC (Buying Climax) - кульминация покупок
        3. AR (Automatic Reaction) - автоматический откат
        4. ST (Secondary Test) - повторный тест максимума
        5. UTAD - ложный пробой выше сопротивления
        6. SOW (Sign of Weakness) - признак слабости
        
        Returns:
            Dict: {"detected": True, "phase": "utad", "confidence": 0.8}
        """
        try:
            if len(candles) < 30:
                return {'detected': False}
            
            # Анализируем последние 30-50 свечей
            recent_candles = candles[-50:]
            recent_volumes = volumes[-50:]
            
            # Находим локальный максимум (BC - Buying Climax)
            max_price = max(c['high'] for c in recent_candles)
            max_index = next(i for i, c in enumerate(recent_candles) if c['high'] == max_price)
            
            # Проверяем высокий объём на максимуме (признак BC)
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            bc_volume = recent_volumes[max_index]
            
            if bc_volume < avg_volume * 1.5:
                return {'detected': False}
            
            # Проверяем AR (Automatic Reaction) - откат после BC
            if max_index >= len(recent_candles) - 5:
                return {'detected': False}
            
            ar_candles = recent_candles[max_index + 1:max_index + 6]
            ar_low = min(c['low'] for c in ar_candles)
            ar_move = (max_price - ar_low) / max_price * 100
            
            if ar_move < 3.0:  # Минимум 3% откат
                return {'detected': False}
            
            # Определяем диапазон распределения
            support_level = ar_low
            resistance_level = max_price
            
            # Проверяем UTAD (ложный пробой сопротивления)
            utad_detected = self._detect_utad(recent_candles[max_index:], resistance_level)
            
            if utad_detected:
                return {
                    'detected': True,
                    'phase': 'utad',
                    'confidence': 0.85
                }
            
            # Проверяем боковое движение в диапазоне (признак распределения)
            range_candles = recent_candles[max_index:]
            in_range_count = sum(
                1 for c in range_candles 
                if support_level * 0.98 <= c['low'] and c['high'] <= resistance_level * 1.02
            )
            
            if in_range_count / len(range_candles) > 0.6:
                return {
                    'detected': True,
                    'phase': 'secondary_test',
                    'confidence': 0.65
                }
            
            return {'detected': False}
            
        except Exception as e:
            self.logger.error(f"Error detecting distribution: {e}")
            return {'detected': False}
    
    def _detect_spring(self, candles: List[Dict], support_level: float) -> bool:
        """
        Определить Spring (ложный пробой поддержки).
        
        Spring: цена пробила поддержку, но быстро вернулась выше
        + Низкий объём на пробое = подтверждение
        
        Args:
            candles: Свечи для анализа
            support_level: Уровень поддержки
        
        Returns:
            bool: True если обнаружен Spring
        """
        try:
            if len(candles) < 5:
                return False
            
            for i in range(len(candles) - 3):
                candle = candles[i]
                
                # Проверяем пробой поддержки
                if candle['low'] < support_level * 0.99:  # Пробой на 1%
                    # Проверяем возврат в следующих 1-3 свечах
                    for j in range(i + 1, min(i + 4, len(candles))):
                        next_candle = candles[j]
                        if next_candle['close'] > support_level:
                            # Spring обнаружен!
                            return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error detecting spring: {e}")
            return False
    
    def _detect_utad(self, candles: List[Dict], resistance_level: float) -> bool:
        """
        Определить UTAD (ложный пробой сопротивления).
        
        UTAD: цена пробила сопротивление, но быстро вернулась ниже
        + Низкий объём на пробое = подтверждение
        
        Args:
            candles: Свечи для анализа
            resistance_level: Уровень сопротивления
        
        Returns:
            bool: True если обнаружен UTAD
        """
        try:
            if len(candles) < 5:
                return False
            
            for i in range(len(candles) - 3):
                candle = candles[i]
                
                # Проверяем пробой сопротивления
                if candle['high'] > resistance_level * 1.01:  # Пробой на 1%
                    # Проверяем возврат в следующих 1-3 свечах
                    for j in range(i + 1, min(i + 4, len(candles))):
                        next_candle = candles[j]
                        if next_candle['close'] < resistance_level:
                            # UTAD обнаружен!
                            return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error detecting UTAD: {e}")
            return False
    
    def _detect_trend(self, candles: List[Dict]) -> str:
        """
        Определить текущий тренд.
        
        Returns:
            str: "markup" (восходящий), "markdown" (нисходящий), "ranging" (боковик)
        """
        try:
            if len(candles) < 20:
                return 'ranging'
            
            recent = candles[-20:]
            
            # Простой расчёт на основе начала и конца периода
            start_price = recent[0]['close']
            end_price = recent[-1]['close']
            
            change_percent = (end_price - start_price) / start_price * 100
            
            if change_percent > 10:
                return 'markup'
            elif change_percent < -10:
                return 'markdown'
            else:
                return 'ranging'
            
        except Exception as e:
            self.logger.error(f"Error detecting trend: {e}")
            return 'ranging'
    
    def _calculate_score(self, wyckoff_phase: Dict) -> float:
        """
        Рассчитать скор на основе фазы Wyckoff.
        
        Логика:
        - Accumulation phase = +score (готовится рост)
        - Distribution phase = -score (готовится падение)
        - Spring = сильный +score
        - UTAD = сильный -score
        - Markup = слабый +score
        - Markdown = слабый -score
        """
        phase = wyckoff_phase.get('phase', 'ranging')
        sub_phase = wyckoff_phase.get('sub_phase', 'none')
        confidence = wyckoff_phase.get('confidence', 0.5)
        
        score = 0.0
        
        if phase == 'accumulation':
            if sub_phase == 'spring':
                score = 10.0 * confidence  # Очень сильный сигнал
            else:
                score = 6.0 * confidence
        
        elif phase == 'distribution':
            if sub_phase == 'utad':
                score = -10.0 * confidence  # Очень сильный медвежий сигнал
            else:
                score = -6.0 * confidence
        
        elif phase == 'markup':
            score = 3.0 * confidence
        
        elif phase == 'markdown':
            score = -3.0 * confidence
        
        return score
