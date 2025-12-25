"""
Базовый класс для всех enhancers.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class BaseEnhancer(ABC):
    """
    Базовый класс для всех enhancers.
    
    Все enhancers должны наследоваться от этого класса и реализовать метод get_score.
    """
    
    def __init__(self):
        """Инициализация базового enhancer."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def get_score(self, coin: str, **kwargs) -> float:
        """
        Получить скор для монеты.
        
        Args:
            coin: Символ монеты (BTC, ETH, etc.)
            **kwargs: Дополнительные параметры (current_price, etc.)
        
        Returns:
            float: Скор от -10 до +10 (или другой диапазон в зависимости от enhancer)
        """
        pass
    
    def clamp(self, value: float, min_val: float, max_val: float) -> float:
        """
        Ограничить значение в диапазоне.
        
        Args:
            value: Значение для ограничения
            min_val: Минимальное значение
            max_val: Максимальное значение
        
        Returns:
            float: Ограниченное значение
        """
        return max(min_val, min(max_val, value))
