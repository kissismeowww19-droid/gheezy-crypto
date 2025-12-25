"""
On-Chain Analysis Enhancer.

Анализирует on-chain метрики для BTC и ETH:
- Exchange Netflow (отток/приток)
- MVRV Ratio (перекупленность/перепроданность)
- Stablecoin Flow (готовность к покупкам)

Вес: 10%
"""

import logging
import aiohttp
from typing import Dict, Optional
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class OnChainEnhancer(BaseEnhancer):
    """
    On-Chain анализ для BTC и ETH.
    
    Поддерживаемые монеты: только BTC и ETH (лучшие данные).
    Вес в итоговом скоре: 10%.
    """
    
    SUPPORTED_COINS = ["BTC", "ETH", "BTCUSDT", "ETHUSDT"]
    WEIGHT = 0.10  # 10%
    MAX_SCORE = 10.0
    
    def __init__(self):
        """Инициализация On-Chain enhancer."""
        super().__init__()
        self._cache = {}
        self._cache_timeout = 3600  # 1 час кеш
    
    async def get_score(self, coin: str, **kwargs) -> float:
        """
        Получить скор on-chain метрик.
        
        Args:
            coin: Символ монеты (BTC, ETH)
            **kwargs: Дополнительные параметры
        
        Returns:
            float: Скор от -10 до +10
                   - Отрицательный = медвежий
                   - Положительный = бычий
                   - 0 = нейтральный или нет данных
        """
        # Нормализуем символ
        normalized_coin = self._normalize_coin(coin)
        
        # Проверяем поддержку
        if normalized_coin not in self.SUPPORTED_COINS:
            self.logger.debug(f"On-chain data not available for {coin}")
            return 0.0
        
        try:
            score = 0.0
            
            # 1. Exchange Netflow (вес 40%)
            try:
                netflow_data = await self.get_exchange_netflow(normalized_coin)
                netflow_score = self._calculate_netflow_score(netflow_data)
                score += netflow_score * 0.4
            except Exception as e:
                self.logger.warning(f"Netflow error for {coin}: {e}")
            
            # 2. MVRV Ratio (вес 35%)
            try:
                mvrv_data = await self.get_mvrv(normalized_coin)
                mvrv_score = self._calculate_mvrv_score(mvrv_data)
                score += mvrv_score * 0.35
            except Exception as e:
                self.logger.warning(f"MVRV error for {coin}: {e}")
            
            # 3. Stablecoin Flow (вес 25%)
            try:
                stablecoin_data = await self.get_stablecoin_flow()
                stablecoin_score = self._calculate_stablecoin_score(stablecoin_data)
                score += stablecoin_score * 0.25
            except Exception as e:
                self.logger.warning(f"Stablecoin flow error: {e}")
            
            # Ограничиваем в диапазоне [-10, +10]
            final_score = self.clamp(score, -self.MAX_SCORE, self.MAX_SCORE)
            
            self.logger.info(f"On-chain score for {coin}: {final_score:.2f}")
            return final_score
            
        except Exception as e:
            self.logger.error(f"On-chain error for {coin}: {e}")
            return 0.0
    
    def _normalize_coin(self, coin: str) -> str:
        """Нормализует символ монеты."""
        coin = coin.upper().replace("USDT", "").replace("BUSD", "")
        return coin
    
    async def get_exchange_netflow(self, coin: str) -> Dict:
        """
        Получить данные о потоках на/с бирж.
        
        Returns:
            {
                "netflow_24h": -1500.5,  # Отрицательный = отток (бычий)
                "netflow_7d": -8500.2,
                "signal": "bullish"
            }
        """
        # Заглушка - в реальности используем Glassnode/CryptoQuant API
        # Симулируем данные на основе волатильности
        import random
        
        # Для демонстрации генерируем случайные данные
        netflow_24h = random.uniform(-3000, 2000)
        netflow_7d = random.uniform(-15000, 10000)
        
        signal = "neutral"
        if netflow_24h < -500 and netflow_7d < -2000:
            signal = "bullish"  # Отток = холдят
        elif netflow_24h > 500 and netflow_7d > 2000:
            signal = "bearish"  # Приток = готовятся продавать
        
        return {
            "netflow_24h": netflow_24h,
            "netflow_7d": netflow_7d,
            "signal": signal
        }
    
    async def get_mvrv(self, coin: str) -> Dict:
        """
        Получить MVRV ratio.
        
        Returns:
            {
                "mvrv": 1.85,
                "signal": "neutral",  # <1 = bullish, >3 = bearish
                "percentile": 45
            }
        """
        # Заглушка - в реальности используем Glassnode API
        import random
        
        mvrv = random.uniform(0.7, 3.5)
        percentile = random.randint(10, 90)
        
        signal = "neutral"
        if mvrv < 1.0:
            signal = "bullish"  # Перепроданность
        elif mvrv > 3.0:
            signal = "bearish"  # Перекупленность
        
        return {
            "mvrv": mvrv,
            "signal": signal,
            "percentile": percentile
        }
    
    async def get_stablecoin_flow(self) -> Dict:
        """
        Получить потоки стейблкоинов на биржи.
        
        Returns:
            {
                "usdt_netflow": 500000000,  # $500M приток
                "usdc_netflow": 200000000,
                "total": 700000000,
                "signal": "bullish"  # Приток = готовятся покупать
            }
        """
        # Заглушка - в реальности используем Blockchain.com / CryptoQuant
        import random
        
        usdt_flow = random.uniform(-1e9, 1e9)
        usdc_flow = random.uniform(-5e8, 5e8)
        total = usdt_flow + usdc_flow
        
        signal = "neutral"
        if total > 3e8:  # $300M+ приток
            signal = "bullish"  # Готовятся покупать
        elif total < -3e8:
            signal = "bearish"  # Отток
        
        return {
            "usdt_netflow": usdt_flow,
            "usdc_netflow": usdc_flow,
            "total": total,
            "signal": signal
        }
    
    async def get_on_chain_data(self, coin: str) -> Dict:
        """
        Получить все on-chain данные для отображения.
        
        Returns:
            Dict со всеми метриками
        """
        normalized_coin = self._normalize_coin(coin)
        
        if normalized_coin not in self.SUPPORTED_COINS:
            return {}
        
        try:
            netflow = await self.get_exchange_netflow(normalized_coin)
            mvrv = await self.get_mvrv(normalized_coin)
            stablecoin = await self.get_stablecoin_flow()
            
            return {
                "netflow": netflow,
                "mvrv": mvrv,
                "stablecoin": stablecoin,
                "supported": True
            }
        except Exception as e:
            self.logger.error(f"Error getting on-chain data for {coin}: {e}")
            return {"supported": False}
    
    def _calculate_netflow_score(self, data: Dict) -> float:
        """
        Рассчитать скор на основе netflow.
        
        Логика:
        - Отток (отрицательный) = бычий (холдят)
        - Приток (положительный) = медвежий (продают)
        """
        netflow_24h = data.get("netflow_24h", 0)
        netflow_7d = data.get("netflow_7d", 0)
        
        # Вес 60% для 24h, 40% для 7d
        score = 0.0
        
        # Нормализуем на типичные значения (±10K BTC или ±100K ETH)
        if netflow_24h < -1000:
            score += 5.0  # Сильный отток = очень бычий
        elif netflow_24h < -500:
            score += 3.0  # Средний отток
        elif netflow_24h < 0:
            score += 1.0  # Слабый отток
        elif netflow_24h > 1000:
            score -= 5.0  # Сильный приток = медвежий
        elif netflow_24h > 500:
            score -= 3.0
        elif netflow_24h > 0:
            score -= 1.0
        
        return score
    
    def _calculate_mvrv_score(self, data: Dict) -> float:
        """
        Рассчитать скор на основе MVRV.
        
        Логика:
        - MVRV < 1 = перепроданность = бычий
        - MVRV > 3 = перекупленность = медвежий
        - 1-3 = нейтрально
        """
        mvrv = data.get("mvrv", 1.5)
        
        if mvrv < 0.8:
            return 5.0  # Сильная перепроданность
        elif mvrv < 1.0:
            return 3.0  # Перепроданность
        elif mvrv > 3.5:
            return -5.0  # Сильная перекупленность
        elif mvrv > 3.0:
            return -3.0  # Перекупленность
        else:
            return 0.0  # Нейтрально
    
    def _calculate_stablecoin_score(self, data: Dict) -> float:
        """
        Рассчитать скор на основе stablecoin flow.
        
        Логика:
        - Приток стейблов = бычий (готовятся покупать)
        - Отток стейблов = медвежий
        """
        total = data.get("total", 0)
        
        # Нормализуем на $1B
        if total > 5e8:  # $500M+
            return 5.0  # Сильный приток = очень бычий
        elif total > 3e8:
            return 3.0
        elif total > 1e8:
            return 1.0
        elif total < -5e8:
            return -5.0  # Сильный отток = медвежий
        elif total < -3e8:
            return -3.0
        elif total < -1e8:
            return -1.0
        else:
            return 0.0
