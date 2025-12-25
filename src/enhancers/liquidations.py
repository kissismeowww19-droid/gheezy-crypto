"""
Liquidation Enhancer - анализ зон ликвидаций и охоты за стопами.

Компоненты:
1. Long Liquidation Zones - где ликвидируют лонгистов (магниты вниз)
2. Short Liquidation Zones - где ликвидируют шортистов (магниты вверх)
3. Stop Hunt Detection - обнаружение охоты за стопами
"""

import logging
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class LiquidationEnhancer(BaseEnhancer):
    """
    Анализатор ликвидаций и зон ликвидности.
    
    Параметры:
    - Минимальный объём ликвидаций: $50M+
    - Расстояние от текущей цены: ±5%
    - Вес в сигнале: 12%
    """
    
    # Константы
    MIN_LIQUIDATION_VOLUME = 50_000_000  # $50M минимум
    PRICE_RANGE_PERCENT = 5  # ±5%
    WEIGHT = 0.12  # 12%
    
    # Маппинг символов
    SYMBOL_MAPPING = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT",
        "TON": "TONUSDT",
    }
    
    def __init__(self):
        """Инициализация Liquidation Enhancer."""
        super().__init__()
        self._cache = {}
        self._cache_ttl = 300  # 5 минут кэш
    
    async def get_score(self, coin: str, current_price: float = None, **kwargs) -> float:
        """
        Получить скор ликвидаций для монеты.
        
        Возвращает скор от -12 до +12:
        - Ближайшая зона short liquidations выше цены = цена пойдёт вверх = +score
        - Ближайшая зона long liquidations ниже цены = цена пойдёт вниз = -score
        - Больше объём ликвидаций = сильнее магнит
        - Stop Hunt detected = сигнал разворота
        
        Args:
            coin: Символ монеты (BTC, ETH, etc.)
            current_price: Текущая цена (опционально, если None - получаем с API)
        
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
            
            # Получаем зоны ликвидаций
            zones = await self.get_liquidation_zones(coin, current_price)
            
            if not zones:
                self.logger.warning(f"No liquidation zones data for {coin}")
                return 0.0
            
            # Рассчитываем скор
            score = self._calculate_score(zones, current_price)
            
            # Ограничиваем в диапазоне [-12, 12]
            score = self.clamp(score, -12.0, 12.0)
            
            self.logger.info(
                f"Liquidation score for {coin}: {score:.2f} "
                f"(Nearest short: {zones.get('nearest_short', {}).get('price', 'N/A') if zones.get('nearest_short') else 'N/A'}, "
                f"Nearest long: {zones.get('nearest_long', {}).get('price', 'N/A') if zones.get('nearest_long') else 'N/A'}, "
                f"Stop hunt: {zones.get('stop_hunt_detected', False)})"
            )
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error calculating Liquidation score for {coin}: {e}", exc_info=True)
            return 0.0
    
    async def get_liquidation_zones(self, coin: str, current_price: float) -> Dict:
        """
        Получить зоны ликвидаций для монеты.
        
        Args:
            coin: Символ монеты
            current_price: Текущая цена
        
        Returns:
            Dict: {
                "long_zones": [{"price": 85000, "volume": 120000000}, ...],
                "short_zones": [{"price": 92000, "volume": 80000000}, ...],
                "nearest_long": {"price": 85000, "volume": 120000000, "distance": -3.2},
                "nearest_short": {"price": 92000, "volume": 80000000, "distance": 4.8},
                "stop_hunt_detected": False
            }
        """
        try:
            # Получаем данные о ликвидациях
            liquidation_data = await self._get_liquidation_data(coin)
            
            if not liquidation_data:
                return {}
            
            # Фильтруем зоны в пределах ±5% от текущей цены
            price_range_low = current_price * (1 - self.PRICE_RANGE_PERCENT / 100)
            price_range_high = current_price * (1 + self.PRICE_RANGE_PERCENT / 100)
            
            long_zones = []
            short_zones = []
            
            for item in liquidation_data:
                price = item.get('price', 0)
                volume = item.get('volume', 0)
                side = item.get('side', '')
                
                # Фильтруем по минимальному объёму
                if volume < self.MIN_LIQUIDATION_VOLUME:
                    continue
                
                # Фильтруем по диапазону цен
                if not (price_range_low <= price <= price_range_high):
                    continue
                
                if side == 'long':
                    long_zones.append({'price': price, 'volume': volume})
                elif side == 'short':
                    short_zones.append({'price': price, 'volume': volume})
            
            # Находим ближайшие зоны
            nearest_long = self._find_nearest_zone(long_zones, current_price, direction='below')
            nearest_short = self._find_nearest_zone(short_zones, current_price, direction='above')
            
            # Проверяем охоту за стопами
            candles = await self._get_recent_candles(coin)
            stop_hunt_detected = self._detect_stop_hunt(candles, long_zones + short_zones)
            
            return {
                'long_zones': long_zones,
                'short_zones': short_zones,
                'nearest_long': nearest_long,
                'nearest_short': nearest_short,
                'stop_hunt_detected': stop_hunt_detected
            }
            
        except Exception as e:
            self.logger.error(f"Error getting liquidation zones for {coin}: {e}", exc_info=True)
            return {}
    
    async def _get_liquidation_data(self, coin: str) -> List[Dict]:
        """
        Получить данные о ликвидациях (mock данные для демонстрации).
        
        В реальном случае здесь будет API Coinglass или расчёт на основе
        Open Interest + Leverage данных с Binance/Bybit.
        """
        # Mock данные для демонстрации
        # В продакшене заменить на реальный API call
        symbol = self.SYMBOL_MAPPING.get(coin, f"{coin}USDT")
        
        # Симулируем данные о ликвидациях
        current_price = await self._get_current_price(coin) or 50000
        
        mock_data = [
            {'price': current_price * 0.97, 'volume': 80_000_000, 'side': 'long'},
            {'price': current_price * 0.95, 'volume': 120_000_000, 'side': 'long'},
            {'price': current_price * 0.93, 'volume': 60_000_000, 'side': 'long'},
            {'price': current_price * 1.03, 'volume': 90_000_000, 'side': 'short'},
            {'price': current_price * 1.05, 'volume': 70_000_000, 'side': 'short'},
        ]
        
        return mock_data
    
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
    
    async def _get_recent_candles(self, coin: str, limit: int = 100) -> List[Dict]:
        """Получить последние свечи для анализа Stop Hunt."""
        try:
            symbol = self.SYMBOL_MAPPING.get(coin, f"{coin}USDT")
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': '1h',
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
    
    def _find_nearest_zone(self, zones: List[Dict], current_price: float, direction: str) -> Optional[Dict]:
        """
        Найти ближайшую зону ликвидаций.
        
        Args:
            zones: Список зон
            current_price: Текущая цена
            direction: 'above' или 'below'
        
        Returns:
            Dict: {"price": float, "volume": float, "distance": float (в %)}
        """
        if not zones:
            return None
        
        filtered_zones = []
        
        for zone in zones:
            price = zone['price']
            if direction == 'above' and price > current_price:
                filtered_zones.append(zone)
            elif direction == 'below' and price < current_price:
                filtered_zones.append(zone)
        
        if not filtered_zones:
            return None
        
        # Сортируем по расстоянию от текущей цены
        nearest = min(filtered_zones, key=lambda z: abs(z['price'] - current_price))
        
        distance_percent = ((nearest['price'] - current_price) / current_price) * 100
        
        return {
            'price': nearest['price'],
            'volume': nearest['volume'],
            'distance': distance_percent
        }
    
    def _detect_stop_hunt(self, candles: List[Dict], zones: List[Dict]) -> bool:
        """
        Обнаружение Stop Hunt.
        
        Stop Hunt: цена резко пробила зону ликвидаций и вернулась обратно
        в течение 1-3 свечей = ложный пробой, разворот.
        
        Args:
            candles: Список свечей
            zones: Список зон ликвидаций
        
        Returns:
            bool: True если обнаружен Stop Hunt
        """
        if not candles or not zones or len(candles) < 5:
            return False
        
        try:
            # Проверяем последние 5 свечей
            recent_candles = candles[-5:]
            
            for zone in zones:
                zone_price = zone['price']
                
                # Проверяем каждую свечу
                for i in range(len(recent_candles) - 3):
                    candle = recent_candles[i]
                    
                    # Проверяем, пробила ли свеча зону
                    if zone_price < candle['close']:
                        # Зона ниже цены закрытия, проверяем пробой вниз
                        if candle['low'] <= zone_price:
                            # Проверяем возврат в следующих 1-3 свечах
                            for j in range(i + 1, min(i + 4, len(recent_candles))):
                                next_candle = recent_candles[j]
                                if next_candle['close'] > zone_price:
                                    # Обнаружен Stop Hunt (пробой вниз и возврат)
                                    return True
                    else:
                        # Зона выше цены закрытия, проверяем пробой вверх
                        if candle['high'] >= zone_price:
                            # Проверяем возврат в следующих 1-3 свечах
                            for j in range(i + 1, min(i + 4, len(recent_candles))):
                                next_candle = recent_candles[j]
                                if next_candle['close'] < zone_price:
                                    # Обнаружен Stop Hunt (пробой вверх и возврат)
                                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error detecting stop hunt: {e}")
            return False
    
    def _calculate_score(self, zones: Dict, current_price: float) -> float:
        """
        Рассчитать скор на основе зон ликвидаций.
        
        Логика:
        - Ближайшая зона short liquidations выше цены = +score (магнит вверх)
        - Ближайшая зона long liquidations ниже цены = -score (магнит вниз)
        - Больше объём = сильнее скор
        - Stop Hunt = усиление сигнала разворота
        """
        score = 0.0
        
        nearest_short = zones.get('nearest_short')
        nearest_long = zones.get('nearest_long')
        stop_hunt = zones.get('stop_hunt_detected', False)
        
        # Скор от short зон (магнит вверх)
        if nearest_short:
            distance = abs(nearest_short['distance'])
            volume_factor = min(nearest_short['volume'] / self.MIN_LIQUIDATION_VOLUME, 3.0)
            # Чем ближе зона, тем сильнее эффект
            distance_factor = (self.PRICE_RANGE_PERCENT - distance) / self.PRICE_RANGE_PERCENT
            score += 6.0 * volume_factor * distance_factor
        
        # Скор от long зон (магнит вниз)
        if nearest_long:
            distance = abs(nearest_long['distance'])
            volume_factor = min(nearest_long['volume'] / self.MIN_LIQUIDATION_VOLUME, 3.0)
            distance_factor = (self.PRICE_RANGE_PERCENT - distance) / self.PRICE_RANGE_PERCENT
            score -= 6.0 * volume_factor * distance_factor
        
        # Stop Hunt усиливает сигнал разворота
        if stop_hunt:
            # Если есть stop hunt, усиливаем текущий сигнал
            score *= 1.5
        
        return score
