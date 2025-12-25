"""
Order Flow Enhancer - анализ крупных ордеров и потока объема.

Компоненты:
1. CVD (Cumulative Volume Delta) - разница между покупками и продажами
2. Large Orders Detection - отслеживание ордеров > $100K
3. Buy/Sell Imbalance - дисбаланс bid/ask
"""

import logging
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class OrderFlowEnhancer(BaseEnhancer):
    """
    Анализатор Order Flow.
    
    Параметры:
    - Минимальный крупный ордер: $100,000+
    - Период анализа: 24 часа
    - Вес в сигнале: 10%
    """
    
    # Константы
    MIN_LARGE_ORDER_USD = 100_000  # $100K минимум для крупного ордера
    ANALYSIS_PERIOD_HOURS = 24     # 24 часа анализа
    
    # Маппинг символов для Binance
    BINANCE_SYMBOL_MAPPING = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT",
        "TON": "TONUSDT",
    }
    
    def __init__(self):
        """Инициализация Order Flow Enhancer."""
        super().__init__()
        self._cache = {}
        self._cache_ttl = 300  # 5 минут кэш
    
    async def get_score(self, coin: str, **kwargs) -> float:
        """
        Получить скор Order Flow для монеты.
        
        Возвращает скор от -10 до +10:
        - CVD растёт + Large Buy Orders = положительный скор
        - CVD падает + Large Sell Orders = отрицательный скор
        
        Args:
            coin: Символ монеты (BTC, ETH, etc.)
        
        Returns:
            float: Скор от -10 до +10
        """
        try:
            coin = coin.upper()
            
            # Получаем данные о сделках
            trades = await self._get_recent_trades(coin)
            if not trades:
                self.logger.warning(f"No trades data available for {coin}")
                return 0.0
            
            # Рассчитываем CVD
            cvd = self._calculate_cvd(trades)
            
            # Детектируем крупные ордера
            large_orders = self._detect_large_orders(trades)
            
            # Рассчитываем дисбаланс
            buy_sell_imbalance = self._calculate_imbalance(trades)
            
            # Рассчитываем итоговый скор
            score = self._calculate_score(cvd, large_orders, buy_sell_imbalance)
            
            # Ограничиваем в диапазоне [-10, 10]
            score = self.clamp(score, -10.0, 10.0)
            
            self.logger.info(
                f"Order Flow score for {coin}: {score:.2f} "
                f"(CVD: {cvd:.0f}, Large orders: {large_orders['buy_count']}/{large_orders['sell_count']}, "
                f"Imbalance: {buy_sell_imbalance:.2f})"
            )
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error calculating Order Flow score for {coin}: {e}", exc_info=True)
            return 0.0
    
    async def _get_recent_trades(self, coin: str, limit: int = 1000) -> Optional[List[Dict]]:
        """
        Получить последние сделки с Binance.
        
        Args:
            coin: Символ монеты
            limit: Количество сделок (макс 1000)
        
        Returns:
            List[Dict]: Список сделок или None
        """
        try:
            symbol = self.BINANCE_SYMBOL_MAPPING.get(coin)
            if not symbol:
                self.logger.warning(f"Unknown symbol for Order Flow: {coin}")
                return None
            
            # Используем Binance aggTrades endpoint
            url = "https://api.binance.com/api/v3/aggTrades"
            params = {
                "symbol": symbol,
                "limit": limit
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        trades = await response.json()
                        self.logger.debug(f"Fetched {len(trades)} trades for {coin}")
                        return trades
                    else:
                        self.logger.warning(f"Failed to fetch trades for {coin}: {response.status}")
                        return None
                        
        except Exception as e:
            self.logger.error(f"Error fetching trades for {coin}: {e}")
            return None
    
    def _calculate_cvd(self, trades: List[Dict]) -> float:
        """
        Рассчитать CVD (Cumulative Volume Delta).
        
        CVD = Σ(buy volume) - Σ(sell volume)
        
        Args:
            trades: Список сделок
        
        Returns:
            float: CVD в USD
        """
        buy_volume = 0.0
        sell_volume = 0.0
        
        for trade in trades:
            qty = float(trade.get('q', 0))  # Количество
            price = float(trade.get('p', 0))  # Цена
            is_buyer_maker = trade.get('m', False)  # Buyer is maker = sell
            
            volume_usd = qty * price
            
            if is_buyer_maker:
                # Maker = sell
                sell_volume += volume_usd
            else:
                # Taker = buy
                buy_volume += volume_usd
        
        cvd = buy_volume - sell_volume
        return cvd
    
    def _detect_large_orders(self, trades: List[Dict]) -> Dict:
        """
        Детектировать крупные ордера (> $100K).
        
        Args:
            trades: Список сделок
        
        Returns:
            Dict: {
                'buy_count': количество крупных покупок,
                'sell_count': количество крупных продаж,
                'buy_volume': объем крупных покупок в USD,
                'sell_volume': объем крупных продаж в USD
            }
        """
        buy_count = 0
        sell_count = 0
        buy_volume = 0.0
        sell_volume = 0.0
        
        for trade in trades:
            qty = float(trade.get('q', 0))
            price = float(trade.get('p', 0))
            is_buyer_maker = trade.get('m', False)
            
            volume_usd = qty * price
            
            # Проверяем, что ордер крупный
            if volume_usd >= self.MIN_LARGE_ORDER_USD:
                if is_buyer_maker:
                    # Крупная продажа
                    sell_count += 1
                    sell_volume += volume_usd
                else:
                    # Крупная покупка
                    buy_count += 1
                    buy_volume += volume_usd
        
        return {
            'buy_count': buy_count,
            'sell_count': sell_count,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume
        }
    
    def _calculate_imbalance(self, trades: List[Dict]) -> float:
        """
        Рассчитать дисбаланс покупок/продаж.
        
        Args:
            trades: Список сделок
        
        Returns:
            float: Дисбаланс (-1 до +1, где +1 = 100% покупки, -1 = 100% продажи)
        """
        buy_volume = 0.0
        sell_volume = 0.0
        
        for trade in trades:
            qty = float(trade.get('q', 0))
            price = float(trade.get('p', 0))
            is_buyer_maker = trade.get('m', False)
            
            volume_usd = qty * price
            
            if is_buyer_maker:
                sell_volume += volume_usd
            else:
                buy_volume += volume_usd
        
        total_volume = buy_volume + sell_volume
        
        if total_volume == 0:
            return 0.0
        
        # Нормализуем к [-1, 1]
        imbalance = (buy_volume - sell_volume) / total_volume
        return imbalance
    
    def _calculate_score(self, cvd: float, large_orders: Dict, imbalance: float) -> float:
        """
        Рассчитать итоговый скор Order Flow.
        
        Логика:
        - CVD > 0 = бычье (до +5)
        - CVD < 0 = медвежье (до -5)
        - Large buy orders > Large sell orders = бычье (до +3)
        - Imbalance > 0 = бычье (до +2)
        
        Args:
            cvd: CVD в USD
            large_orders: Данные о крупных ордерах
            imbalance: Дисбаланс покупок/продаж
        
        Returns:
            float: Скор от -10 до +10
        """
        score = 0.0
        
        # 1. CVD компонент (до ±5 баллов)
        # Нормализуем CVD к [-5, 5]
        # Предполагаем, что CVD в диапазоне [-10M, +10M] для BTC/ETH
        cvd_normalized = cvd / 10_000_000  # Делим на $10M
        cvd_score = self.clamp(cvd_normalized * 5, -5.0, 5.0)
        score += cvd_score
        
        # 2. Large orders компонент (до ±3 баллов)
        buy_count = large_orders['buy_count']
        sell_count = large_orders['sell_count']
        
        if buy_count + sell_count > 0:
            # Нормализуем разницу
            order_diff = buy_count - sell_count
            total_orders = buy_count + sell_count
            order_ratio = order_diff / total_orders  # [-1, 1]
            order_score = order_ratio * 3  # [-3, 3]
            score += order_score
        
        # 3. Imbalance компонент (до ±2 баллов)
        imbalance_score = imbalance * 2  # [-2, 2]
        score += imbalance_score
        
        return score
    
    async def get_cvd(self, coin: str) -> Optional[float]:
        """
        Получить CVD для отображения в сигнале.
        
        Args:
            coin: Символ монеты
        
        Returns:
            float: CVD в USD или None
        """
        try:
            trades = await self._get_recent_trades(coin)
            if not trades:
                return None
            
            cvd = self._calculate_cvd(trades)
            return cvd
            
        except Exception as e:
            self.logger.error(f"Error getting CVD for {coin}: {e}")
            return None
