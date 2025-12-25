"""
Volume Profile Enhancer - анализ уровней объема.

Компоненты:
1. POC (Point of Control) - уровень с максимальным объёмом
2. VAH (Value Area High) - верхняя граница 70% объёма
3. VAL (Value Area Low) - нижняя граница 70% объёма
4. LVN (Low Volume Nodes) - зоны низкого объёма
"""

import logging
import aiohttp
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class VolumeProfileEnhancer(BaseEnhancer):
    """
    Анализатор Volume Profile.
    
    Параметры:
    - Период: 7 дней + 30 дней (комбинация)
    - Вес в сигнале: 10%
    """
    
    # Константы
    SHORT_PERIOD_DAYS = 7   # Короткий период
    LONG_PERIOD_DAYS = 30   # Длинный период
    VALUE_AREA_PCT = 0.70   # 70% объёма для Value Area
    NUM_PRICE_LEVELS = 50   # Количество уровней для профиля
    
    # Маппинг символов для Binance
    BINANCE_SYMBOL_MAPPING = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT",
        "TON": "TONUSDT",
    }
    
    def __init__(self):
        """Инициализация Volume Profile Enhancer."""
        super().__init__()
        self._cache = {}
        self._cache_ttl = 600  # 10 минут кэш
    
    async def get_score(self, coin: str, **kwargs) -> float:
        """
        Получить скор Volume Profile для монеты.
        
        Возвращает скор от -10 до +10:
        - Цена у VAL + отскок = положительный скор (покупка)
        - Цена у VAH + отбой = отрицательный скор (продажа)
        - Цена ниже POC = вероятен возврат к POC
        
        Args:
            coin: Символ монеты
            **kwargs: current_price (обязательно)
        
        Returns:
            float: Скор от -10 до +10
        """
        try:
            coin = coin.upper()
            current_price = kwargs.get('current_price')
            
            if current_price is None:
                self.logger.warning(f"current_price not provided for {coin}")
                return 0.0
            
            # Получаем уровни Volume Profile
            levels = await self.get_levels(coin)
            if not levels:
                self.logger.warning(f"No Volume Profile levels available for {coin}")
                return 0.0
            
            poc = levels.get('poc')
            vah = levels.get('vah')
            val = levels.get('val')
            
            if poc is None or vah is None or val is None:
                self.logger.warning(f"Incomplete Volume Profile levels for {coin}")
                return 0.0
            
            # Рассчитываем скор на основе позиции цены
            score = self._calculate_score(current_price, poc, vah, val)
            
            # Ограничиваем в диапазоне [-10, 10]
            score = self.clamp(score, -10.0, 10.0)
            
            self.logger.info(
                f"Volume Profile score for {coin}: {score:.2f} "
                f"(Price: {current_price:.2f}, POC: {poc:.2f}, VAH: {vah:.2f}, VAL: {val:.2f})"
            )
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error calculating Volume Profile score for {coin}: {e}", exc_info=True)
            return 0.0
    
    async def get_levels(self, coin: str) -> Dict:
        """
        Получить уровни POC, VAH, VAL, LVN для отображения в сигнале.
        
        Args:
            coin: Символ монеты
        
        Returns:
            Dict: {
                'poc': float,
                'vah': float,
                'val': float,
                'lvn': List[float]
            }
        """
        try:
            coin = coin.upper()
            
            # Получаем OHLCV данные за 7 дней
            ohlcv_data = await self._get_ohlcv(coin, days=self.SHORT_PERIOD_DAYS)
            if not ohlcv_data:
                self.logger.warning(f"No OHLCV data for {coin}")
                return {}
            
            # Рассчитываем Volume Profile
            volume_profile = self._calculate_volume_profile(ohlcv_data)
            
            # Рассчитываем POC, VAH, VAL
            poc = self._calculate_poc(volume_profile)
            vah, val = self._calculate_value_area(volume_profile, poc)
            
            # Рассчитываем LVN (Low Volume Nodes)
            lvn = self._calculate_lvn(volume_profile)
            
            levels = {
                'poc': poc,
                'vah': vah,
                'val': val,
                'lvn': lvn
            }
            
            self.logger.debug(f"Volume Profile levels for {coin}: {levels}")
            
            return levels
            
        except Exception as e:
            self.logger.error(f"Error getting Volume Profile levels for {coin}: {e}")
            return {}
    
    async def _get_ohlcv(self, coin: str, days: int = 7) -> Optional[List[Dict]]:
        """
        Получить OHLCV данные с Binance.
        
        Args:
            coin: Символ монеты
            days: Количество дней
        
        Returns:
            List[Dict]: OHLCV данные или None
        """
        try:
            symbol = self.BINANCE_SYMBOL_MAPPING.get(coin)
            if not symbol:
                self.logger.warning(f"Unknown symbol for Volume Profile: {coin}")
                return None
            
            # Используем Binance klines endpoint
            url = "https://api.binance.com/api/v3/klines"
            
            # Рассчитываем временной диапазон
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            params = {
                "symbol": symbol,
                "interval": "1h",  # 1 час свечи
                "startTime": start_time,
                "endTime": end_time,
                "limit": 1000
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        klines = await response.json()
                        
                        # Преобразуем в удобный формат
                        ohlcv_data = []
                        for kline in klines:
                            ohlcv_data.append({
                                'timestamp': kline[0],
                                'open': float(kline[1]),
                                'high': float(kline[2]),
                                'low': float(kline[3]),
                                'close': float(kline[4]),
                                'volume': float(kline[5])
                            })
                        
                        self.logger.debug(f"Fetched {len(ohlcv_data)} candles for {coin}")
                        return ohlcv_data
                    else:
                        self.logger.warning(f"Failed to fetch OHLCV for {coin}: {response.status}")
                        return None
                        
        except Exception as e:
            self.logger.error(f"Error fetching OHLCV for {coin}: {e}")
            return None
    
    def _calculate_volume_profile(self, ohlcv_data: List[Dict]) -> Dict[float, float]:
        """
        Рассчитать Volume Profile.
        
        Args:
            ohlcv_data: OHLCV данные
        
        Returns:
            Dict[float, float]: {price_level: volume}
        """
        if not ohlcv_data:
            return {}
        
        # Найдем min и max цену
        all_prices = []
        for candle in ohlcv_data:
            all_prices.extend([candle['high'], candle['low']])
        
        min_price = min(all_prices)
        max_price = max(all_prices)
        
        # Создаем уровни цен
        price_step = (max_price - min_price) / self.NUM_PRICE_LEVELS
        
        # Инициализируем профиль
        volume_profile = {}
        
        for i in range(self.NUM_PRICE_LEVELS):
            level = min_price + (i * price_step)
            volume_profile[level] = 0.0
        
        # Распределяем объем по уровням
        for candle in ohlcv_data:
            # Распределяем объем свечи пропорционально между high и low
            candle_range = candle['high'] - candle['low']
            
            if candle_range == 0:
                # Если свеча без диапазона, весь объем на close
                level = self._find_nearest_level(candle['close'], volume_profile.keys())
                if level is not None:
                    volume_profile[level] += candle['volume']
            else:
                # Распределяем объем по всем уровням в диапазоне свечи
                for level in volume_profile.keys():
                    if candle['low'] <= level <= candle['high']:
                        # Пропорциональная часть объема
                        volume_profile[level] += candle['volume'] / self.NUM_PRICE_LEVELS
        
        return volume_profile
    
    def _find_nearest_level(self, price: float, levels) -> Optional[float]:
        """
        Найти ближайший уровень к цене.
        
        Args:
            price: Цена
            levels: Уровни (iterable)
        
        Returns:
            float: Ближайший уровень или None
        """
        levels_list = list(levels)
        if not levels_list:
            return None
        
        return min(levels_list, key=lambda x: abs(x - price))
    
    def _calculate_poc(self, volume_profile: Dict[float, float]) -> Optional[float]:
        """
        Рассчитать POC (Point of Control) - уровень с максимальным объёмом.
        
        Args:
            volume_profile: Volume Profile
        
        Returns:
            float: POC или None
        """
        if not volume_profile:
            return None
        
        # Находим уровень с максимальным объемом
        poc = max(volume_profile.items(), key=lambda x: x[1])
        return poc[0]
    
    def _calculate_value_area(self, volume_profile: Dict[float, float], poc: float) -> Tuple[Optional[float], Optional[float]]:
        """
        Рассчитать VAH и VAL (Value Area High/Low).
        
        Value Area = 70% от общего объёма, центрированная вокруг POC.
        
        Args:
            volume_profile: Volume Profile
            poc: Point of Control
        
        Returns:
            Tuple[float, float]: (VAH, VAL) или (None, None)
        """
        if not volume_profile or poc is None:
            return None, None
        
        # Сортируем уровни по объему (убывание)
        sorted_levels = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)
        
        # Рассчитываем общий объем
        total_volume = sum(volume_profile.values())
        target_volume = total_volume * self.VALUE_AREA_PCT
        
        # Накапливаем уровни до 70% объёма
        accumulated_volume = 0.0
        value_area_levels = []
        
        for level, volume in sorted_levels:
            if accumulated_volume >= target_volume:
                break
            value_area_levels.append(level)
            accumulated_volume += volume
        
        if not value_area_levels:
            return None, None
        
        # VAH = максимальный уровень в Value Area
        # VAL = минимальный уровень в Value Area
        vah = max(value_area_levels)
        val = min(value_area_levels)
        
        return vah, val
    
    def _calculate_lvn(self, volume_profile: Dict[float, float], threshold_pct: float = 0.3) -> List[float]:
        """
        Рассчитать LVN (Low Volume Nodes) - зоны низкого объёма.
        
        Args:
            volume_profile: Volume Profile
            threshold_pct: Порог для определения низкого объёма (30% от среднего)
        
        Returns:
            List[float]: Список LVN уровней
        """
        if not volume_profile:
            return []
        
        # Рассчитываем средний объем
        avg_volume = sum(volume_profile.values()) / len(volume_profile)
        threshold = avg_volume * threshold_pct
        
        # Находим уровни с объемом ниже порога
        lvn = [level for level, volume in volume_profile.items() if volume < threshold]
        
        # Сортируем по возрастанию цены
        lvn.sort()
        
        # Берем первые 5 LVN для отображения
        return lvn[:5]
    
    def _calculate_score(self, current_price: float, poc: float, vah: float, val: float) -> float:
        """
        Рассчитать итоговый скор Volume Profile.
        
        Логика:
        - Цена у VAL (нижняя граница) = бычье (до +10)
        - Цена у VAH (верхняя граница) = медвежье (до -10)
        - Цена ниже POC = вероятен возврат к POC (до +5)
        - Цена выше POC = вероятно движение вниз (до -5)
        
        Args:
            current_price: Текущая цена
            poc: Point of Control
            vah: Value Area High
            val: Value Area Low
        
        Returns:
            float: Скор от -10 до +10
        """
        score = 0.0
        
        # Расстояние до уровней (в процентах)
        dist_to_val = abs(current_price - val) / current_price
        dist_to_vah = abs(current_price - vah) / current_price
        dist_to_poc = abs(current_price - poc) / current_price
        
        # 1. Если цена близко к VAL (< 1%) = бычье
        if dist_to_val < 0.01 and current_price >= val:
            score += 8.0  # Сильный бычий сигнал
        
        # 2. Если цена близко к VAH (< 1%) = медвежье
        if dist_to_vah < 0.01 and current_price <= vah:
            score -= 8.0  # Сильный медвежий сигнал
        
        # 3. Если цена ниже POC = вероятен возврат вверх
        if current_price < poc:
            # Чем дальше от POC, тем сильнее притяжение
            poc_score = min(5.0, dist_to_poc * 500)  # До +5
            score += poc_score
        
        # 4. Если цена выше POC = вероятно движение вниз
        if current_price > poc:
            # Чем дальше от POC, тем сильнее притяжение вниз
            poc_score = min(5.0, dist_to_poc * 500)  # До -5
            score -= poc_score
        
        return score
