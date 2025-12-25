"""
Signal Stability Manager - предотвращает нестабильность сигналов.

Обеспечивает стабильность торговых сигналов путём:
- Cooldown между сменами направления (минимум 1 час)
- Подтверждения для смены сигнала (3 подтверждения подряд)
- Проверка изменения score (минимум 30% изменение)
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SignalStabilityManager:
    """
    Менеджер стабильности сигналов.
    
    Предотвращает частые изменения сигналов путём применения:
    1. Cooldown - минимум 1 час между сменой направления
    2. Confirmation - требует 3 подтверждения для смены направления
    3. Score threshold - изменение score более 30% обходит cooldown
    """
    
    COOLDOWN_MINUTES = 60  # Минимум 1 час между сменой направления
    CONFIRMATION_REQUIRED = 3  # 3 подтверждения для смены
    SCORE_CHANGE_THRESHOLD = 0.3  # 30% изменение score для смены
    
    def __init__(self):
        """Инициализация менеджера стабильности."""
        # Хранилище последних сигналов
        # {coin: {"direction": "long", "score": 5.5, "time": timestamp, "confirmations": 0, "pending_direction": None}}
        self.last_signals: Dict[str, Dict] = {}
        logger.info("SignalStabilityManager initialized")
    
    def should_change_signal(
        self, 
        coin: str, 
        new_direction: str, 
        new_score: float,
        old_direction: Optional[str] = None,
        old_score: Optional[float] = None
    ) -> bool:
        """
        Проверяет можно ли сменить сигнал.
        
        Возвращает True только если:
        1. Прошло >= 1 часа с последнего сигнала
        2. ИЛИ есть 3 подтверждения подряд в новом направлении
        3. ИЛИ score изменился более чем на 30%
        
        Args:
            coin: Символ монеты (BTC, ETH, TON, etc.)
            new_direction: Новое направление сигнала (long/short/sideways)
            new_score: Новый score сигнала
            old_direction: Старое направление (для обратной совместимости)
            old_score: Старый score (для обратной совместимости)
            
        Returns:
            True если сигнал можно изменить, False если нужно подождать
        """
        coin = coin.upper()
        
        # Первый сигнал для этой монеты - разрешаем сразу
        if coin not in self.last_signals:
            logger.info(f"{coin}: First signal, allowing change to {new_direction}")
            return True
        
        last_signal = self.last_signals[coin]
        last_direction = last_signal.get("direction")
        last_score = last_signal.get("score", 0)
        last_time = last_signal.get("time", 0)
        
        # Используем old_direction/old_score если они переданы (fallback)
        if old_direction is not None:
            last_direction = old_direction
        if old_score is not None:
            last_score = old_score
        
        # Если направление не меняется - всегда разрешаем обновление
        if new_direction == last_direction:
            logger.debug(f"{coin}: Same direction ({new_direction}), allowing update")
            return True
        
        # Проверка 1: Прошло >= 1 часа с последнего изменения?
        time_diff = time.time() - last_time
        time_diff_minutes = time_diff / 60
        cooldown_passed = time_diff_minutes >= self.COOLDOWN_MINUTES
        
        # Проверка 2: Score изменился более чем на 30%?
        if last_score != 0:
            score_change_pct = abs(new_score - last_score) / abs(last_score)
        else:
            score_change_pct = 1.0  # Если старый score == 0, считаем что изменение большое
        
        significant_score_change = score_change_pct >= self.SCORE_CHANGE_THRESHOLD
        
        # Проверка 3: Есть 3 подтверждения подряд?
        pending_direction = last_signal.get("pending_direction")
        confirmations = last_signal.get("confirmations", 0)
        
        if pending_direction == new_direction:
            # Продолжаем накапливать подтверждения
            confirmations += 1
        else:
            # Сбрасываем подтверждения если направление изменилось
            confirmations = 1
        
        # Обновляем pending_direction и confirmations
        self.last_signals[coin]["pending_direction"] = new_direction
        self.last_signals[coin]["confirmations"] = confirmations
        
        enough_confirmations = confirmations >= self.CONFIRMATION_REQUIRED
        
        # Решение: разрешаем смену если выполнено любое условие
        allow_change = cooldown_passed or significant_score_change or enough_confirmations
        
        if allow_change:
            logger.info(
                f"{coin}: Allowing signal change {last_direction} -> {new_direction} "
                f"(cooldown: {cooldown_passed}, score_change: {significant_score_change:.1%}, "
                f"confirmations: {confirmations}/{self.CONFIRMATION_REQUIRED})"
            )
        else:
            logger.info(
                f"{coin}: Blocking signal change {last_direction} -> {new_direction} "
                f"(time: {time_diff_minutes:.1f}/{self.COOLDOWN_MINUTES}min, "
                f"score_change: {score_change_pct:.1%}, confirmations: {confirmations}/{self.CONFIRMATION_REQUIRED})"
            )
        
        return allow_change
    
    def update_signal(self, coin: str, direction: str, score: float):
        """
        Обновляет последний сигнал для монеты.
        
        Args:
            coin: Символ монеты (BTC, ETH, TON, etc.)
            direction: Направление сигнала (long/short/sideways)
            score: Score сигнала
        """
        coin = coin.upper()
        
        self.last_signals[coin] = {
            "direction": direction,
            "score": score,
            "time": time.time(),
            "confirmations": 0,
            "pending_direction": None
        }
        
        logger.debug(f"{coin}: Signal updated - direction={direction}, score={score}")
    
    def get_stable_signal(
        self,
        coin: str,
        new_direction: str,
        new_score: float,
        old_direction: Optional[str] = None,
        old_score: Optional[float] = None
    ) -> Dict:
        """
        Возвращает стабильный сигнал.
        
        Если нельзя менять — возвращает предыдущий.
        Если можно — возвращает новый.
        
        Args:
            coin: Символ монеты (BTC, ETH, TON, etc.)
            new_direction: Новое направление сигнала (long/short/sideways)
            new_score: Новый score сигнала
            old_direction: Старое направление (опционально)
            old_score: Старый score (опционально)
            
        Returns:
            Dict с полями:
                - direction: str - направление сигнала
                - score: float - score сигнала
                - changed: bool - был ли изменён сигнал
                - reason: str - причина решения
        """
        coin = coin.upper()
        
        # Проверяем можно ли менять сигнал
        can_change = self.should_change_signal(
            coin=coin,
            new_direction=new_direction,
            new_score=new_score,
            old_direction=old_direction,
            old_score=old_score
        )
        
        if can_change:
            # Обновляем сигнал
            self.update_signal(coin, new_direction, new_score)
            
            return {
                "direction": new_direction,
                "score": new_score,
                "changed": True,
                "reason": "Signal changed - conditions met"
            }
        else:
            # Возвращаем старый сигнал
            last_signal = self.last_signals.get(coin, {})
            last_direction = last_signal.get("direction", old_direction or new_direction)
            last_score = last_signal.get("score", old_score or new_score)
            
            return {
                "direction": last_direction,
                "score": last_score,
                "changed": False,
                "reason": "Signal blocked - cooldown or insufficient confirmations"
            }
    
    def get_last_signal(self, coin: str) -> Optional[Dict]:
        """
        Получает последний сигнал для монеты.
        
        Args:
            coin: Символ монеты (BTC, ETH, TON, etc.)
            
        Returns:
            Dict с последним сигналом или None если сигнала нет
        """
        coin = coin.upper()
        return self.last_signals.get(coin)
    
    def clear_signals(self):
        """Очищает все сохранённые сигналы."""
        self.last_signals.clear()
        logger.info("All signals cleared")
