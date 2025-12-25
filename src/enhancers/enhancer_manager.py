"""
Enhancer Manager - управление всеми enhancers.

Безопасно агрегирует скоры от всех модулей с fallback механизмом.
"""

import logging
from typing import Dict, Optional
from .order_flow import OrderFlowEnhancer
from .volume_profile import VolumeProfileEnhancer
from .multi_exchange import MultiExchangeEnhancer

logger = logging.getLogger(__name__)


class EnhancerManager:
    """
    Менеджер всех enhancers.
    
    Обеспечивает безопасную работу с каждым модулем:
    - Если модуль упал - возвращает 0, не ломает остальные
    - Логирует все ошибки
    - Агрегирует скоры от всех модулей
    """
    
    def __init__(self):
        """Инициализация EnhancerManager."""
        self.order_flow = OrderFlowEnhancer()
        self.volume_profile = VolumeProfileEnhancer()
        self.multi_exchange = MultiExchangeEnhancer()
        
        logger.info("EnhancerManager initialized with 3 enhancers")
    
    async def get_total_score(self, coin: str, current_price: float) -> float:
        """
        Безопасно получает скор от всех модулей.
        
        Если модуль упал — возвращает 0, не ломает остальные.
        
        Args:
            coin: Символ монеты
            current_price: Текущая цена
        
        Returns:
            float: Суммарный скор от всех enhancers
                   - Order Flow: от -10 до +10
                   - Volume Profile: от -10 до +10
                   - Multi-Exchange: от -5 до +5
                   - Итого: от -25 до +25
        """
        total = 0.0
        
        # 1. Order Flow (до ±10)
        try:
            order_flow_score = await self.order_flow.get_score(coin)
            total += order_flow_score
            logger.debug(f"Order Flow score for {coin}: {order_flow_score:.2f}")
        except Exception as e:
            logger.warning(f"OrderFlow error for {coin}: {e}")
        
        # 2. Volume Profile (до ±10)
        try:
            volume_profile_score = await self.volume_profile.get_score(coin, current_price=current_price)
            total += volume_profile_score
            logger.debug(f"Volume Profile score for {coin}: {volume_profile_score:.2f}")
        except Exception as e:
            logger.warning(f"VolumeProfile error for {coin}: {e}")
        
        # 3. Multi-Exchange (до ±5)
        try:
            multi_exchange_score = await self.multi_exchange.get_score(coin)
            total += multi_exchange_score
            logger.debug(f"Multi-Exchange score for {coin}: {multi_exchange_score:.2f}")
        except Exception as e:
            logger.warning(f"MultiExchange error for {coin}: {e}")
        
        logger.info(f"Total enhancer score for {coin}: {total:.2f}")
        
        return total
    
    async def get_extra_data(self, coin: str) -> Dict:
        """
        Возвращает дополнительные данные для отображения в сигнале.
        
        Args:
            coin: Символ монеты
        
        Returns:
            Dict: {
                'volume_profile_levels': {...},  # POC, VAH, VAL, LVN
                'exchange_leader': str,          # Название биржи-лидера
                'order_flow_cvd': float          # CVD в USD
            }
        """
        extra_data = {}
        
        # 1. Volume Profile levels
        try:
            levels = await self.volume_profile.get_levels(coin)
            extra_data['volume_profile_levels'] = levels
        except Exception as e:
            logger.warning(f"Error getting Volume Profile levels for {coin}: {e}")
            extra_data['volume_profile_levels'] = {}
        
        # 2. Exchange leader
        try:
            leader = await self.multi_exchange.get_leader(coin)
            extra_data['exchange_leader'] = leader
        except Exception as e:
            logger.warning(f"Error getting exchange leader for {coin}: {e}")
            extra_data['exchange_leader'] = "N/A"
        
        # 3. Order Flow CVD
        try:
            cvd = await self.order_flow.get_cvd(coin)
            extra_data['order_flow_cvd'] = cvd
        except Exception as e:
            logger.warning(f"Error getting Order Flow CVD for {coin}: {e}")
            extra_data['order_flow_cvd'] = None
        
        return extra_data
