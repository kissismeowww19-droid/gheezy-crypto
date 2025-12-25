"""
Dynamic Targets Enhancer.

Рассчитывает умные TP/SL на основе реальных уровней:
- ATR для адаптивных размеров
- S/R уровни и Order Blocks
- Volume Profile (POC, VAH, VAL)
- Liquidation Zones

Минимальный R:R: 1:2
"""

import logging
from typing import Dict, List, Optional, Tuple
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class DynamicTargetsEnhancer(BaseEnhancer):
    """
    Расчёт динамических TP/SL.
    
    Параметры:
    - Минимальный R:R: 1:2
    - Уровней TP: 2 (TP1 и TP2)
    - Trailing Stop: Да
    """
    
    MIN_RR = 2.0  # Минимум 1:2
    TP_LEVELS = 2  # TP1 и TP2
    TRAILING_STOP = True
    
    def __init__(self):
        """Инициализация Dynamic Targets enhancer."""
        super().__init__()
    
    async def get_score(self, coin: str, **kwargs) -> float:
        """
        Dynamic Targets не участвует в скоринге.
        
        Используется только для расчёта TP/SL через calculate_targets().
        """
        return 0.0
    
    async def calculate_targets(
        self,
        coin: str,
        entry_price: float,
        signal_type: str,
        enhancer_data: Dict
    ) -> Dict:
        """
        Рассчитать умные TP/SL.
        
        Args:
            coin: Символ монеты
            entry_price: Цена входа
            signal_type: "LONG" или "SHORT"
            enhancer_data: Данные от других enhancers
        
        Returns:
            {
                "entry": 87500,
                "stop_loss": 85800,
                "take_profit_1": 89500,
                "take_profit_2": 91200,
                "risk_reward": 2.35,
                "trailing_stop": {
                    "enabled": True,
                    "activation_price": 88500,
                    "trail_percent": 1.5
                },
                "reasoning": {
                    "sl": "Под Order Block $85,900",
                    "tp1": "VAH $89,500",
                    "tp2": "Short Liquidation Zone $91,200"
                }
            }
        """
        try:
            # Извлекаем данные из enhancers
            atr = enhancer_data.get('volatility', {}).get('atr', entry_price * 0.02)
            volume_profile = enhancer_data.get('volume_profile_levels', {})
            liquidation_zones = enhancer_data.get('liquidation_zones', {})
            smc_levels = enhancer_data.get('smc_levels', {})
            
            # Рассчитываем Stop Loss
            sl_data = self._calculate_stop_loss(
                entry_price,
                signal_type,
                atr,
                smc_levels.get('order_blocks', [])
            )
            
            # Рассчитываем Take Profits
            tp_data = self._calculate_take_profits(
                entry_price,
                sl_data['price'],
                signal_type,
                volume_profile,
                liquidation_zones,
                atr
            )
            
            # Рассчитываем Trailing Stop
            trailing_data = self._calculate_trailing_stop(
                entry_price,
                tp_data[0]['price'],
                atr
            )
            
            # Валидируем R:R
            risk = abs(entry_price - sl_data['price'])
            reward1 = abs(tp_data[0]['price'] - entry_price)
            reward2 = abs(tp_data[1]['price'] - entry_price)
            
            rr1 = reward1 / risk if risk > 0 else 0
            rr2 = reward2 / risk if risk > 0 else 0
            
            # Если R:R слишком низкий, корректируем TP
            if rr1 < self.MIN_RR:
                self.logger.warning(f"R:R too low ({rr1:.2f}), adjusting TP levels")
                tp_data = self._adjust_tp_for_rr(
                    entry_price,
                    sl_data['price'],
                    signal_type,
                    atr
                )
                
                # Пересчитываем R:R
                reward1 = abs(tp_data[0]['price'] - entry_price)
                reward2 = abs(tp_data[1]['price'] - entry_price)
                rr1 = reward1 / risk if risk > 0 else 0
                rr2 = reward2 / risk if risk > 0 else 0
            
            result = {
                "entry": entry_price,
                "stop_loss": sl_data['price'],
                "take_profit_1": tp_data[0]['price'],
                "take_profit_2": tp_data[1]['price'],
                "risk_reward": round(rr1, 2),
                "risk_reward_tp2": round(rr2, 2),
                "trailing_stop": trailing_data,
                "reasoning": {
                    "sl": sl_data['reason'],
                    "tp1": tp_data[0]['reason'],
                    "tp2": tp_data[1]['reason']
                }
            }
            
            self.logger.info(f"Dynamic targets for {coin} {signal_type}: "
                           f"Entry={entry_price:.2f}, SL={sl_data['price']:.2f}, "
                           f"TP1={tp_data[0]['price']:.2f}, TP2={tp_data[1]['price']:.2f}, "
                           f"R:R={rr1:.2f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating targets for {coin}: {e}")
            # Fallback к простым процентам
            return self._fallback_targets(entry_price, signal_type)
    
    def _calculate_stop_loss(
        self,
        entry: float,
        signal_type: str,
        atr: float,
        order_blocks: List[Dict]
    ) -> Dict:
        """
        Рассчитать Stop Loss.
        
        Стратегия:
        1. Минимум ATR * 1.5
        2. Если есть Order Block рядом - ставим под/над ним
        3. Иначе используем ATR
        """
        # Базовый SL на основе ATR
        atr_multiplier = 1.5
        
        if signal_type == "LONG":
            base_sl = entry - (atr * atr_multiplier)
            reason = f"ATR-based SL (ATR={atr:.0f})"
            
            # Ищем ближайший Order Block снизу
            nearby_ob = self._find_nearest_order_block(entry, order_blocks, "below")
            if nearby_ob:
                ob_low = nearby_ob.get('low', 0)
                distance = (entry - ob_low) / entry
                
                # Если OB не слишком далеко (< 3% от входа)
                if 0.005 < distance < 0.03:
                    base_sl = ob_low - (atr * 0.2)  # Чуть ниже OB
                    reason = f"Под Order Block ${ob_low:.0f}"
        else:
            # SHORT
            base_sl = entry + (atr * atr_multiplier)
            reason = f"ATR-based SL (ATR={atr:.0f})"
            
            # Ищем ближайший Order Block сверху
            nearby_ob = self._find_nearest_order_block(entry, order_blocks, "above")
            if nearby_ob:
                ob_high = nearby_ob.get('high', 0)
                distance = (ob_high - entry) / entry
                
                if 0.005 < distance < 0.03:
                    base_sl = ob_high + (atr * 0.2)  # Чуть выше OB
                    reason = f"Над Order Block ${ob_high:.0f}"
        
        return {
            "price": round(base_sl, 2),
            "reason": reason
        }
    
    def _calculate_take_profits(
        self,
        entry: float,
        stop_loss: float,
        signal_type: str,
        volume_profile: Dict,
        liquidation_zones: Dict,
        atr: float
    ) -> List[Dict]:
        """
        Рассчитать TP1 и TP2.
        
        Стратегия:
        - TP1: Ближайший значимый уровень (VAH/VAL или 1.5*ATR)
        - TP2: Дальний уровень (Liquidation Zone или 2.5*ATR)
        """
        risk = abs(entry - stop_loss)
        
        tp1_list = []
        tp2_list = []
        
        if signal_type == "LONG":
            # TP1: Ищем VAH или используем ATR
            vah = volume_profile.get('vah', 0)
            if vah > entry:
                distance = (vah - entry) / entry
                if 0.01 < distance < 0.05:  # 1-5% от входа
                    tp1_list.append({
                        'price': vah,
                        'reason': f"VAH ${vah:.0f}",
                        'distance': distance
                    })
            
            # TP2: Ищем Short Liquidation Zone
            short_zones = liquidation_zones.get('short_zones', [])
            if short_zones:
                # Берём ближайшую зону выше входа
                for zone in short_zones:
                    zone_price = zone.get('price', 0)
                    if zone_price > entry:
                        distance = (zone_price - entry) / entry
                        if 0.02 < distance < 0.08:  # 2-8% от входа
                            tp2_list.append({
                                'price': zone_price,
                                'reason': f"Short Liq Zone ${zone_price:.0f}",
                                'distance': distance
                            })
                            break
            
            # Fallback к ATR
            if not tp1_list:
                tp1_price = entry + (atr * 1.5)
                tp1_list.append({
                    'price': tp1_price,
                    'reason': f"1.5x ATR",
                    'distance': (tp1_price - entry) / entry
                })
            
            if not tp2_list:
                tp2_price = entry + (atr * 2.5)
                tp2_list.append({
                    'price': tp2_price,
                    'reason': f"2.5x ATR",
                    'distance': (tp2_price - entry) / entry
                })
        
        else:
            # SHORT
            # TP1: Ищем VAL
            val = volume_profile.get('val', 0)
            if val < entry and val > 0:
                distance = (entry - val) / entry
                if 0.01 < distance < 0.05:
                    tp1_list.append({
                        'price': val,
                        'reason': f"VAL ${val:.0f}",
                        'distance': distance
                    })
            
            # TP2: Ищем Long Liquidation Zone
            long_zones = liquidation_zones.get('long_zones', [])
            if long_zones:
                for zone in long_zones:
                    zone_price = zone.get('price', 0)
                    if zone_price < entry:
                        distance = (entry - zone_price) / entry
                        if 0.02 < distance < 0.08:
                            tp2_list.append({
                                'price': zone_price,
                                'reason': f"Long Liq Zone ${zone_price:.0f}",
                                'distance': distance
                            })
                            break
            
            # Fallback к ATR
            if not tp1_list:
                tp1_price = entry - (atr * 1.5)
                tp1_list.append({
                    'price': tp1_price,
                    'reason': f"1.5x ATR",
                    'distance': (entry - tp1_price) / entry
                })
            
            if not tp2_list:
                tp2_price = entry - (atr * 2.5)
                tp2_list.append({
                    'price': tp2_price,
                    'reason': f"2.5x ATR",
                    'distance': (entry - tp2_price) / entry
                })
        
        return [
            {
                'price': round(tp1_list[0]['price'], 2),
                'reason': tp1_list[0]['reason']
            },
            {
                'price': round(tp2_list[0]['price'], 2),
                'reason': tp2_list[0]['reason']
            }
        ]
    
    def _calculate_trailing_stop(
        self,
        entry: float,
        tp1: float,
        atr: float
    ) -> Dict:
        """
        Рассчитать Trailing Stop.
        
        Активируется когда цена достигает TP1.
        Trail на 1.5% или 1*ATR (что меньше).
        """
        trail_percent = min(1.5, (atr / entry) * 100)
        
        return {
            "enabled": self.TRAILING_STOP,
            "activation_price": round(tp1, 2),
            "trail_percent": round(trail_percent, 2)
        }
    
    def _find_nearest_order_block(
        self,
        entry: float,
        order_blocks: List[Dict],
        direction: str
    ) -> Optional[Dict]:
        """Найти ближайший Order Block."""
        if not order_blocks:
            return None
        
        nearest = None
        min_distance = float('inf')
        
        for ob in order_blocks:
            ob_high = ob.get('high', 0)
            ob_low = ob.get('low', 0)
            
            if direction == "below" and ob_high < entry:
                distance = entry - ob_high
                if distance < min_distance:
                    min_distance = distance
                    nearest = ob
            elif direction == "above" and ob_low > entry:
                distance = ob_low - entry
                if distance < min_distance:
                    min_distance = distance
                    nearest = ob
        
        return nearest
    
    def _adjust_tp_for_rr(
        self,
        entry: float,
        stop_loss: float,
        signal_type: str,
        atr: float
    ) -> List[Dict]:
        """Корректировать TP для достижения минимального R:R."""
        risk = abs(entry - stop_loss)
        min_reward = risk * self.MIN_RR
        
        if signal_type == "LONG":
            tp1 = entry + min_reward
            tp2 = entry + (min_reward * 1.5)
        else:
            tp1 = entry - min_reward
            tp2 = entry - (min_reward * 1.5)
        
        return [
            {'price': round(tp1, 2), 'reason': f'Adjusted for R:R {self.MIN_RR}'},
            {'price': round(tp2, 2), 'reason': f'Extended target'}
        ]
    
    def _fallback_targets(self, entry: float, signal_type: str) -> Dict:
        """Fallback к простым процентам при ошибке."""
        if signal_type == "LONG":
            sl = entry * 0.98  # -2%
            tp1 = entry * 1.04  # +4%
            tp2 = entry * 1.06  # +6%
        else:
            sl = entry * 1.02  # +2%
            tp1 = entry * 0.96  # -4%
            tp2 = entry * 0.94  # -6%
        
        return {
            "entry": entry,
            "stop_loss": round(sl, 2),
            "take_profit_1": round(tp1, 2),
            "take_profit_2": round(tp2, 2),
            "risk_reward": 2.0,
            "trailing_stop": {"enabled": False},
            "reasoning": {
                "sl": "Fallback: 2% from entry",
                "tp1": "Fallback: 4% from entry",
                "tp2": "Fallback: 6% from entry"
            }
        }
