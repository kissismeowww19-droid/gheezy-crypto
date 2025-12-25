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
from .on_chain import OnChainEnhancer
from .whale_tracker import WhaleTrackerEnhancer
from .funding_advanced import FundingAdvancedEnhancer
from .volatility import VolatilityEnhancer
from .dynamic_targets import DynamicTargetsEnhancer

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
        
        # PR #2 модули
        self.liquidations = LiquidationEnhancer()
        self.smart_money = SmartMoneyEnhancer()
        self.wyckoff = WyckoffEnhancer()
        
        # PR #3 модули (НОВЫЕ)
        self.on_chain = OnChainEnhancer()
        self.whale_tracker = WhaleTrackerEnhancer()
        self.funding_advanced = FundingAdvancedEnhancer()
        self.volatility = VolatilityEnhancer()
        self.dynamic_targets = DynamicTargetsEnhancer()
        
        logger.info("EnhancerManager initialized with 11 enhancers")
    
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
                   - On-Chain: от -10 до +10
                   - Whale Tracker: от -8 до +8
                   - Funding Advanced: от -7 до +7
                   - Volatility: от -6 до +6
                   - Итого: от -90 до +90
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
        
        # 4. Liquidations (до ±12)
        try:
            liquidations_score = await self.liquidations.get_score(coin, current_price=current_price)
            total += liquidations_score
            logger.debug(f"Liquidations score for {coin}: {liquidations_score:.2f}")
        except Exception as e:
            logger.warning(f"Liquidations error for {coin}: {e}")
        
        # 5. Smart Money (до ±12)
        try:
            smart_money_score = await self.smart_money.get_score(coin, current_price=current_price)
            total += smart_money_score
            logger.debug(f"Smart Money score for {coin}: {smart_money_score:.2f}")
        except Exception as e:
            logger.warning(f"SmartMoney error for {coin}: {e}")
        
        # 6. Wyckoff (до ±10)
        try:
            wyckoff_score = await self.wyckoff.get_score(coin, current_price=current_price)
            total += wyckoff_score
            logger.debug(f"Wyckoff score for {coin}: {wyckoff_score:.2f}")
        except Exception as e:
            logger.warning(f"Wyckoff error for {coin}: {e}")
        
        # 7. On-Chain (до ±10) - НОВЫЙ
        try:
            on_chain_score = await self.on_chain.get_score(coin, current_price=current_price)
            total += on_chain_score
            logger.debug(f"On-Chain score for {coin}: {on_chain_score:.2f}")
        except Exception as e:
            logger.warning(f"OnChain error for {coin}: {e}")
        
        # 8. Whale Tracker (до ±8) - НОВЫЙ
        try:
            whale_tracker_score = await self.whale_tracker.get_score(coin, current_price=current_price)
            total += whale_tracker_score
            logger.debug(f"Whale Tracker score for {coin}: {whale_tracker_score:.2f}")
        except Exception as e:
            logger.warning(f"WhaleTracker error for {coin}: {e}")
        
        # 9. Funding Advanced (до ±7) - НОВЫЙ
        try:
            funding_advanced_score = await self.funding_advanced.get_score(coin, current_price=current_price)
            total += funding_advanced_score
            logger.debug(f"Funding Advanced score for {coin}: {funding_advanced_score:.2f}")
        except Exception as e:
            logger.warning(f"FundingAdvanced error for {coin}: {e}")
        
        # 10. Volatility (до ±6) - НОВЫЙ
        try:
            volatility_score = await self.volatility.get_score(coin, current_price=current_price)
            total += volatility_score
            logger.debug(f"Volatility score for {coin}: {volatility_score:.2f}")
        except Exception as e:
            logger.warning(f"Volatility error for {coin}: {e}")
        
        # Note: DynamicTargetsEnhancer не участвует в скоринге
        
        logger.info(f"Total enhancer score for {coin}: {total:.2f}")
        
        return total
    
    async def get_dynamic_targets(
        self,
        coin: str,
        entry_price: float,
        signal_type: str
    ) -> Dict:
        """
        Получить умные динамические TP/SL.
        
        Args:
            coin: Символ монеты
            entry_price: Цена входа
            signal_type: "LONG" или "SHORT"
        
        Returns:
            Dict с динамическими таргетами (TP1, TP2, SL, trailing stop)
        """
        try:
            # Собираем данные от всех enhancers
            enhancer_data = await self.get_extra_data(coin, entry_price)
            
            # Рассчитываем динамические таргеты
            targets = await self.dynamic_targets.calculate_targets(
                coin, entry_price, signal_type, enhancer_data
            )
            
            return targets
            
        except Exception as e:
            logger.error(f"Error getting dynamic targets for {coin}: {e}")
            # Fallback к простым процентам
            return self._fallback_targets(entry_price, signal_type)
    
    def _fallback_targets(self, entry: float, signal_type: str) -> Dict:
        """Fallback targets при ошибке."""
        if signal_type == "LONG":
            return {
                "entry": entry,
                "stop_loss": round(entry * 0.98, 2),
                "take_profit_1": round(entry * 1.04, 2),
                "take_profit_2": round(entry * 1.06, 2),
                "risk_reward": 2.0,
                "trailing_stop": {"enabled": False},
                "reasoning": {
                    "sl": "Fallback: 2% from entry",
                    "tp1": "Fallback: 4% from entry",
                    "tp2": "Fallback: 6% from entry"
                }
            }
        else:
            return {
                "entry": entry,
                "stop_loss": round(entry * 1.02, 2),
                "take_profit_1": round(entry * 0.96, 2),
                "take_profit_2": round(entry * 0.94, 2),
                "risk_reward": 2.0,
                "trailing_stop": {"enabled": False},
                "reasoning": {
                    "sl": "Fallback: 2% from entry",
                    "tp1": "Fallback: 4% from entry",
                    "tp2": "Fallback: 6% from entry"
                }
            }
    
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
                'wyckoff_phase': {...},          # Фаза Wyckoff
                'on_chain': {...},               # On-chain данные (НОВЫЙ)
                'whale_activity': {...},         # Активность китов (НОВЫЙ)
                'funding': {...},                # Funding данные (НОВЫЙ)
                'volatility': {...}              # Волатильность (НОВЫЙ)
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
        
        # 4. Liquidation zones
        try:
            if current_price is not None:
                liquidation_zones = await self.liquidations.get_liquidation_zones(coin, current_price)
                extra_data['liquidation_zones'] = liquidation_zones
            else:
                extra_data['liquidation_zones'] = {}
        except Exception as e:
            logger.warning(f"Error getting liquidation zones for {coin}: {e}")
            extra_data['liquidation_zones'] = {}
        
        # 5. SMC levels
        try:
            smc_levels = await self.smart_money.get_smc_levels(coin)
            extra_data['smc_levels'] = smc_levels
        except Exception as e:
            logger.warning(f"Error getting SMC levels for {coin}: {e}")
            extra_data['smc_levels'] = {}
        
        # 6. Wyckoff phase
        try:
            wyckoff_phase = await self.wyckoff.get_wyckoff_phase(coin)
            extra_data['wyckoff_phase'] = wyckoff_phase
        except Exception as e:
            logger.warning(f"Error getting Wyckoff phase for {coin}: {e}")
            extra_data['wyckoff_phase'] = {}
        
        # 7. On-Chain data - НОВЫЙ
        try:
            on_chain_data = await self.on_chain.get_on_chain_data(coin)
            extra_data['on_chain'] = on_chain_data
        except Exception as e:
            logger.warning(f"Error getting on-chain data for {coin}: {e}")
            extra_data['on_chain'] = {}
        
        # 8. Whale Activity - НОВЫЙ
        try:
            whale_activity = await self.whale_tracker.get_whale_activity(coin)
            extra_data['whale_activity'] = whale_activity
        except Exception as e:
            logger.warning(f"Error getting whale activity for {coin}: {e}")
            extra_data['whale_activity'] = {}
        
        # 9. Funding data - НОВЫЙ
        try:
            funding_data = await self.funding_advanced.get_funding_data(coin)
            extra_data['funding'] = funding_data
        except Exception as e:
            logger.warning(f"Error getting funding data for {coin}: {e}")
            extra_data['funding'] = {}
        
        # 10. Volatility - НОВЫЙ
        try:
            volatility_data = await self.volatility.get_volatility_data(coin)
            extra_data['volatility'] = volatility_data
        except Exception as e:
            logger.warning(f"Error getting volatility data for {coin}: {e}")
            extra_data['volatility'] = {}
        
        return extra_data
