"""
Smart Money Concepts Enhancer - анализ Order Blocks, FVG, BOS.

Компоненты:
1. Order Blocks - зоны входа институционалов
2. FVG (Fair Value Gap) - имбалансы в цене
3. BOS (Break of Structure) - пробой структуры
"""

import logging
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class SmartMoneyEnhancer(BaseEnhancer):
    """
    Анализатор Smart Money Concepts.
    
    Параметры:
    - Таймфрейм: 4H
    - Вес в сигнале: 12%
    """
    
    # Константы
    TIMEFRAME = "4h"
    WEIGHT = 0.12  # 12%
    
    # Маппинг символов
    SYMBOL_MAPPING = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT",
        "TON": "TONUSDT",
    }
    
    # Минимальный размер импульса для Order Block (в %)
    MIN_IMPULSE_PERCENT = 2.0
    
    # Максимальное количество Order Blocks для отслеживания
    MAX_ORDER_BLOCKS = 5
    
    # Максимальное количество FVG для отслеживания
    MAX_FVG_COUNT = 5
    
    def __init__(self):
        """Инициализация Smart Money Enhancer."""
        super().__init__()
        self._cache = {}
        self._cache_ttl = 600  # 10 минут кэш
    
    async def get_score(self, coin: str, current_price: float = None, **kwargs) -> float:
        """
        Получить скор Smart Money для монеты.
        
        Возвращает скор от -12 до +12:
        - Цена у Bullish Order Block = +score
        - Цена у Bearish Order Block = -score
        - Незаполненный Bullish FVG ниже = цена вернётся = -score
        - Незаполненный Bearish FVG выше = цена вернётся = +score
        - BOS вверх = подтверждение лонга = +score
        - BOS вниз = подтверждение шорта = -score
        
        Args:
            coin: Символ монеты (BTC, ETH, etc.)
            current_price: Текущая цена
        
        Returns:
            float: Скор от -12 до +12
        """
        try:
            coin = coin.upper()
            
            # Если цена не передана, получаем её
            if current_price is None:
                current_price = await self._get_current_price(coin)
                if current_price is None:
                    self.logger.warning(f"Cannot get current price for {coin}")
                    return 0.0
            
            # Получаем SMC уровни
            smc_levels = await self.get_smc_levels(coin)
            
            if not smc_levels:
                self.logger.warning(f"No SMC levels data for {coin}")
                return 0.0
            
            # Рассчитываем скор
            score = self._calculate_score(smc_levels, current_price)
            
            # Ограничиваем в диапазоне [-12, 12]
            score = self.clamp(score, -12.0, 12.0)
            
            self.logger.info(
                f"Smart Money score for {coin}: {score:.2f} "
                f"(OB: {len(smc_levels.get('order_blocks', []))}, "
                f"FVG: {len(smc_levels.get('fvg', []))}, "
                f"BOS: {smc_levels.get('bos', {}).get('direction', 'none')})"
            )
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error calculating Smart Money score for {coin}: {e}", exc_info=True)
            return 0.0
    
    async def get_smc_levels(self, coin: str) -> Dict:
        """
        Получить все SMC уровни для монеты.
        
        Returns:
            Dict: {
                "order_blocks": [...],
                "fvg": [...],
                "bos": {...}
            }
        """
        try:
            # Получаем свечи 4H таймфрейма
            candles = await self._get_candles(coin, interval='4h', limit=100)
            
            if not candles or len(candles) < 20:
                return {}
            
            # Находим Order Blocks
            order_blocks = self._find_order_blocks(candles)
            
            # Находим FVG
            fvg = self._find_fvg(candles)
            
            # Определяем BOS
            bos = self._detect_bos(candles)
            
            return {
                'order_blocks': order_blocks,
                'fvg': fvg,
                'bos': bos
            }
            
        except Exception as e:
            self.logger.error(f"Error getting SMC levels for {coin}: {e}", exc_info=True)
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
    
    async def _get_candles(self, coin: str, interval: str = '4h', limit: int = 100) -> List[Dict]:
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
    
    def _find_order_blocks(self, candles: List[Dict]) -> List[Dict]:
        """
        Найти Order Blocks.
        
        Order Block = последняя противоположная свеча перед импульсом:
        - Bullish OB: последняя красная свеча перед сильным ростом
        - Bearish OB: последняя зелёная свеча перед сильным падением
        
        Returns:
            List[Dict]: [
                {"type": "bullish", "high": 87500, "low": 87000, "strength": 0.8},
                {"type": "bearish", "high": 92000, "low": 91500, "strength": 0.7}
            ]
        """
        order_blocks = []
        
        try:
            if len(candles) < 5:
                return []
            
            for i in range(len(candles) - 4):
                current = candles[i]
                next_candles = candles[i + 1:i + 4]
                
                # Проверяем Bullish Order Block
                # Текущая свеча красная, следующие растут
                if current['close'] < current['open']:
                    # Проверяем импульс вверх
                    total_move = 0
                    for next_c in next_candles:
                        move = (next_c['close'] - next_c['open']) / next_c['open'] * 100
                        total_move += move
                    
                    if total_move > self.MIN_IMPULSE_PERCENT:
                        strength = min(total_move / 10.0, 1.0)  # Нормализуем силу
                        order_blocks.append({
                            'type': 'bullish',
                            'high': current['high'],
                            'low': current['low'],
                            'strength': strength,
                            'timestamp': current['timestamp']
                        })
                
                # Проверяем Bearish Order Block
                # Текущая свеча зелёная, следующие падают
                elif current['close'] > current['open']:
                    # Проверяем импульс вниз
                    total_move = 0
                    for next_c in next_candles:
                        move = (next_c['close'] - next_c['open']) / next_c['open'] * 100
                        total_move += move
                    
                    if total_move < -self.MIN_IMPULSE_PERCENT:
                        strength = min(abs(total_move) / 10.0, 1.0)
                        order_blocks.append({
                            'type': 'bearish',
                            'high': current['high'],
                            'low': current['low'],
                            'strength': strength,
                            'timestamp': current['timestamp']
                        })
            
            # Оставляем только последние 5 самых сильных OB
            order_blocks.sort(key=lambda x: (x['timestamp'], x['strength']), reverse=True)
            return order_blocks[:self.MAX_ORDER_BLOCKS]
            
        except Exception as e:
            self.logger.error(f"Error finding order blocks: {e}")
            return []
    
    def _find_fvg(self, candles: List[Dict]) -> List[Dict]:
        """
        Найти Fair Value Gaps (FVG).
        
        FVG = gap между high свечи 1 и low свечи 3:
        - Bullish FVG: candle[0].high < candle[2].low (gap вверх)
        - Bearish FVG: candle[0].low > candle[2].high (gap вниз)
        
        Returns:
            List[Dict]: [
                {"type": "bullish", "top": 88000, "bottom": 87500, "filled": False},
                {"type": "bearish", "top": 91000, "bottom": 90500, "filled": True}
            ]
        """
        fvgs = []
        
        try:
            if len(candles) < 3:
                return []
            
            current_price = candles[-1]['close']
            
            for i in range(len(candles) - 2):
                candle_0 = candles[i]
                candle_1 = candles[i + 1]
                candle_2 = candles[i + 2]
                
                # Bullish FVG
                if candle_0['high'] < candle_2['low']:
                    gap_bottom = candle_0['high']
                    gap_top = candle_2['low']
                    
                    # Проверяем, заполнен ли gap (цена вернулась в эту зону)
                    filled = False
                    for j in range(i + 3, len(candles)):
                        if candles[j]['low'] <= gap_top and candles[j]['high'] >= gap_bottom:
                            filled = True
                            break
                    
                    fvgs.append({
                        'type': 'bullish',
                        'top': gap_top,
                        'bottom': gap_bottom,
                        'filled': filled,
                        'timestamp': candle_1['timestamp']
                    })
                
                # Bearish FVG
                elif candle_0['low'] > candle_2['high']:
                    gap_top = candle_0['low']
                    gap_bottom = candle_2['high']
                    
                    # Проверяем, заполнен ли gap
                    filled = False
                    for j in range(i + 3, len(candles)):
                        if candles[j]['low'] <= gap_top and candles[j]['high'] >= gap_bottom:
                            filled = True
                            break
                    
                    fvgs.append({
                        'type': 'bearish',
                        'top': gap_top,
                        'bottom': gap_bottom,
                        'filled': filled,
                        'timestamp': candle_1['timestamp']
                    })
            
            # Оставляем только последние 5 FVG
            fvgs.sort(key=lambda x: x['timestamp'], reverse=True)
            return fvgs[:self.MAX_FVG_COUNT]
            
        except Exception as e:
            self.logger.error(f"Error finding FVG: {e}")
            return []
    
    def _detect_bos(self, candles: List[Dict]) -> Dict:
        """
        Определить Break of Structure (BOS).
        
        BOS = пробой структуры:
        - Bullish BOS: цена пробила последний swing high
        - Bearish BOS: цена пробила последний swing low
        
        Returns:
            Dict: {"direction": "bullish", "broken_level": 89500, "confirmed": True}
        """
        try:
            if len(candles) < 20:
                return {}
            
            # Находим swing highs и swing lows
            swing_highs = []
            swing_lows = []
            
            for i in range(2, len(candles) - 2):
                candle = candles[i]
                
                # Swing High: high больше 2 свечей слева и справа
                if (candle['high'] > candles[i-1]['high'] and 
                    candle['high'] > candles[i-2]['high'] and
                    candle['high'] > candles[i+1]['high'] and 
                    candle['high'] > candles[i+2]['high']):
                    swing_highs.append({'price': candle['high'], 'index': i})
                
                # Swing Low: low меньше 2 свечей слева и справа
                if (candle['low'] < candles[i-1]['low'] and 
                    candle['low'] < candles[i-2]['low'] and
                    candle['low'] < candles[i+1]['low'] and 
                    candle['low'] < candles[i+2]['low']):
                    swing_lows.append({'price': candle['low'], 'index': i})
            
            if not swing_highs or not swing_lows:
                return {}
            
            # Берём последний swing high и swing low
            last_swing_high = swing_highs[-1]
            last_swing_low = swing_lows[-1]
            
            current_candle = candles[-1]
            
            # Проверяем Bullish BOS (пробой последнего swing high)
            if current_candle['close'] > last_swing_high['price']:
                return {
                    'direction': 'bullish',
                    'broken_level': last_swing_high['price'],
                    'confirmed': True
                }
            
            # Проверяем Bearish BOS (пробой последнего swing low)
            if current_candle['close'] < last_swing_low['price']:
                return {
                    'direction': 'bearish',
                    'broken_level': last_swing_low['price'],
                    'confirmed': True
                }
            
            return {'direction': 'none', 'confirmed': False}
            
        except Exception as e:
            self.logger.error(f"Error detecting BOS: {e}")
            return {}
    
    def _calculate_score(self, smc_levels: Dict, current_price: float) -> float:
        """
        Рассчитать скор на основе SMC уровней.
        
        Логика:
        - Цена у Bullish Order Block = +score
        - Цена у Bearish Order Block = -score
        - Незаполненный Bullish FVG ниже = -score (цена вернётся)
        - Незаполненный Bearish FVG выше = +score (цена вернётся)
        - BOS вверх = +score
        - BOS вниз = -score
        """
        score = 0.0
        
        # Order Blocks
        order_blocks = smc_levels.get('order_blocks', [])
        for ob in order_blocks:
            # Проверяем, находится ли цена в зоне OB
            if ob['low'] <= current_price <= ob['high']:
                if ob['type'] == 'bullish':
                    score += 4.0 * ob['strength']
                else:  # bearish
                    score -= 4.0 * ob['strength']
            # Проверяем, близка ли цена к OB (в пределах 1%)
            elif abs(current_price - ob['low']) / current_price < 0.01:
                if ob['type'] == 'bullish':
                    score += 2.0 * ob['strength']
                else:
                    score -= 2.0 * ob['strength']
        
        # FVG
        fvgs = smc_levels.get('fvg', [])
        for fvg in fvgs:
            if not fvg['filled']:
                if fvg['type'] == 'bullish':
                    # Bullish FVG ниже цены = цена может вернуться
                    if fvg['top'] < current_price:
                        score -= 2.0
                else:  # bearish
                    # Bearish FVG выше цены = цена может вернуться
                    if fvg['bottom'] > current_price:
                        score += 2.0
        
        # BOS
        bos = smc_levels.get('bos', {})
        if bos.get('confirmed'):
            if bos['direction'] == 'bullish':
                score += 6.0
            elif bos['direction'] == 'bearish':
                score -= 6.0
        
        return score
