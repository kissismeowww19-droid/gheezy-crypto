"""
Enhancer Manager - управление всеми enhancers.

Безопасно агрегирует скоры от всех модулей с fallback механизмом.
"""

import logging
from typing import Dict, Optional
from .order_flow import OrderFlowEnhancer
from .volume_profile import VolumeProfileEnhancer
from .multi_exchange import MultiExchangeEnhancer
from .liquidations import LiquidationEnhancer
from .smart_money import SmartMoneyEnhancer
from .wyckoff import WyckoffEnhancer

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
        # PR #1 модули
        self.order_flow = OrderFlowEnhancer()
        self.volume_profile = VolumeProfileEnhancer()
        self.multi_exchange = MultiExchangeEnhancer()
        
        # PR #2 модули (НОВЫЕ)
        self.liquidations = LiquidationEnhancer()
        self.smart_money = SmartMoneyEnhancer()
        self.wyckoff = WyckoffEnhancer()
        
        logger.info("EnhancerManager initialized with 6 enhancers")
    
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
                   - Liquidations: от -12 до +12
                   - Smart Money: от -12 до +12
                   - Wyckoff: от -10 до +10
                   - Итого: от -59 до +59
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
        
        # 4. Liquidations (до ±12) - НОВЫЙ
        try:
            liquidations_score = await self.liquidations.get_score(coin, current_price=current_price)
            total += liquidations_score
            logger.debug(f"Liquidations score for {coin}: {liquidations_score:.2f}")
        except Exception as e:
            logger.warning(f"Liquidations error for {coin}: {e}")
        
        # 5. Smart Money (до ±12) - НОВЫЙ
        try:
            smart_money_score = await self.smart_money.get_score(coin, current_price=current_price)
            total += smart_money_score
            logger.debug(f"Smart Money score for {coin}: {smart_money_score:.2f}")
        except Exception as e:
            logger.warning(f"SmartMoney error for {coin}: {e}")
        
        # 6. Wyckoff (до ±10) - НОВЫЙ
        try:
            wyckoff_score = await self.wyckoff.get_score(coin, current_price=current_price)
            total += wyckoff_score
            logger.debug(f"Wyckoff score for {coin}: {wyckoff_score:.2f}")
        except Exception as e:
            logger.warning(f"Wyckoff error for {coin}: {e}")
        
        logger.info(f"Total enhancer score for {coin}: {total:.2f}")
        
        return total
    
    async def get_extra_data(self, coin: str, current_price: float = None) -> Dict:
        """
        Возвращает дополнительные данные для отображения в сигнале.
        
        Args:
            coin: Символ монеты
            current_price: Текущая цена (опционально)
        
        Returns:
            Dict: {
                'volume_profile_levels': {...},  # POC, VAH, VAL, LVN
                'exchange_leader': str,          # Название биржи-лидера
                'order_flow_cvd': float,         # CVD в USD
                'liquidation_zones': {...},      # Зоны ликвидаций
                'smc_levels': {...},             # SMC уровни
                'wyckoff_phase': {...}           # Фаза Wyckoff
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
        
        # 4. Liquidation zones - НОВЫЙ
        try:
            if current_price is not None:
                liquidation_zones = await self.liquidations.get_liquidation_zones(coin, current_price)
                extra_data['liquidation_zones'] = liquidation_zones
            else:
                extra_data['liquidation_zones'] = {}
        except Exception as e:
            logger.warning(f"Error getting liquidation zones for {coin}: {e}")
            extra_data['liquidation_zones'] = {}
        
        # 5. SMC levels - НОВЫЙ
        try:
            smc_levels = await self.smart_money.get_smc_levels(coin)
            extra_data['smc_levels'] = smc_levels
        except Exception as e:
            logger.warning(f"Error getting SMC levels for {coin}: {e}")
            extra_data['smc_levels'] = {}
        
        # 6. Wyckoff phase - НОВЫЙ
        try:
            wyckoff_phase = await self.wyckoff.get_wyckoff_phase(coin)
            extra_data['wyckoff_phase'] = wyckoff_phase
        except Exception as e:
            logger.warning(f"Error getting Wyckoff phase for {coin}: {e}")
            extra_data['wyckoff_phase'] = {}
        
        return extra_data
