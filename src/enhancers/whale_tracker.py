"""
Whale Tracker Enhancer.

Отслеживание активности крупных китов:
- Накопление/распределение топ-50 кошельков
- Переводы на/с бирж ($1M+)
- Крупные транзакции

Вес: 8%
"""

import logging
from typing import Dict, List, Optional
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class WhaleTrackerEnhancer(BaseEnhancer):
    """
    Отслеживание активности китов.
    
    Параметры:
    - Топ кошельков: 50
    - Минимальная транзакция: $1M
    - Вес: 8%
    """
    
    TOP_WALLETS = 50
    MIN_TRANSACTION = 1_000_000  # $1M
    WEIGHT = 0.08  # 8%
    MAX_SCORE = 8.0
    
    def __init__(self):
        """Инициализация Whale Tracker."""
        super().__init__()
        self._cache = {}
        self._cache_timeout = 1800  # 30 минут кеш
    
    async def get_score(self, coin: str, **kwargs) -> float:
        """
        Получить скор активности китов.
        
        Args:
            coin: Символ монеты
            **kwargs: Дополнительные параметры (current_price)
        
        Returns:
            float: Скор от -8 до +8
                   - Положительный = киты накапливают (бычий)
                   - Отрицательный = киты распределяют (медвежий)
        """
        try:
            score = 0.0
            current_price = kwargs.get('current_price', 50000.0)
            
            # 1. Активность китов (вес 50%)
            try:
                activity = await self.get_whale_activity(coin)
                activity_score = self._calculate_activity_score(activity)
                score += activity_score * 0.5
            except Exception as e:
                self.logger.warning(f"Whale activity error for {coin}: {e}")
            
            # 2. Изменение балансов топ-кошельков (вес 50%)
            try:
                wallet_changes = await self.get_top_wallets_change(coin)
                wallet_score = self._calculate_wallet_score(wallet_changes)
                score += wallet_score * 0.5
            except Exception as e:
                self.logger.warning(f"Wallet changes error for {coin}: {e}")
            
            # Ограничиваем в диапазоне [-8, +8]
            final_score = self.clamp(score, -self.MAX_SCORE, self.MAX_SCORE)
            
            self.logger.info(f"Whale tracker score for {coin}: {final_score:.2f}")
            return final_score
            
        except Exception as e:
            self.logger.error(f"Whale tracker error for {coin}: {e}")
            return 0.0
    
    async def get_whale_activity(self, coin: str) -> Dict:
        """
        Получить активность китов.
        
        Returns:
            {
                "accumulation_24h": True,
                "large_txs": [
                    {"type": "withdrawal", "amount": 500, "usd_value": 43500000, "exchange": "Binance"},
                    {"type": "deposit", "amount": 200, "usd_value": 17400000, "exchange": "Coinbase"}
                ],
                "net_flow": "outflow",  # outflow/inflow/neutral
                "signal": "bullish"
            }
        """
        # Заглушка - в реальности используем Whale Alert API
        import random
        
        # Генерируем случайные крупные транзакции
        large_txs = []
        num_txs = random.randint(2, 8)
        
        total_withdrawals = 0
        total_deposits = 0
        
        for _ in range(num_txs):
            tx_type = random.choice(["withdrawal", "deposit"])
            amount = random.uniform(50, 1000)
            price = random.uniform(40000, 100000)
            usd_value = amount * price
            
            if usd_value >= self.MIN_TRANSACTION:
                large_txs.append({
                    "type": tx_type,
                    "amount": amount,
                    "usd_value": usd_value,
                    "exchange": random.choice(["Binance", "Coinbase", "Kraken", "Bybit"])
                })
                
                if tx_type == "withdrawal":
                    total_withdrawals += usd_value
                else:
                    total_deposits += usd_value
        
        # Определяем net flow
        net_diff = total_withdrawals - total_deposits
        if net_diff > 5_000_000:  # $5M+
            net_flow = "outflow"
            signal = "bullish"  # Выводят = холдят
            accumulation = True
        elif net_diff < -5_000_000:
            net_flow = "inflow"
            signal = "bearish"  # Депозитят = готовятся продавать
            accumulation = False
        else:
            net_flow = "neutral"
            signal = "neutral"
            accumulation = None
        
        return {
            "accumulation_24h": accumulation,
            "large_txs": large_txs,
            "net_flow": net_flow,
            "signal": signal,
            "total_withdrawals": total_withdrawals,
            "total_deposits": total_deposits
        }
    
    async def get_top_wallets_change(self, coin: str) -> Dict:
        """
        Изменение балансов топ-50 кошельков.
        
        Returns:
            {
                "change_24h": +1500,  # BTC добавили
                "change_7d": +8500,
                "percent_change_24h": 0.5,
                "signal": "accumulating"  # accumulating/distributing/neutral
            }
        """
        # Заглушка - в реальности используем Blockchair/Etherscan API
        import random
        
        change_24h = random.uniform(-2000, 2000)
        change_7d = random.uniform(-10000, 10000)
        
        # Процент от общего баланса топ-50 (обычно ~2-3M BTC или ~20M ETH)
        total_balance = 2_000_000 if coin.upper().startswith('BTC') else 20_000_000
        percent_change_24h = (change_24h / total_balance) * 100
        
        signal = "neutral"
        if change_24h > 500 and change_7d > 2000:
            signal = "accumulating"
        elif change_24h < -500 and change_7d < -2000:
            signal = "distributing"
        
        return {
            "change_24h": change_24h,
            "change_7d": change_7d,
            "percent_change_24h": percent_change_24h,
            "signal": signal
        }
    
    def _calculate_activity_score(self, data: Dict) -> float:
        """
        Рассчитать скор на основе активности.
        
        Логика:
        - Выводы с бирж = бычий (холдят)
        - Депозиты на биржи = медвежий (продают)
        """
        net_flow = data.get("net_flow", "neutral")
        total_withdrawals = data.get("total_withdrawals", 0)
        total_deposits = data.get("total_deposits", 0)
        
        score = 0.0
        
        if net_flow == "outflow":
            # Нормализуем на $50M
            net_amount = total_withdrawals - total_deposits
            if net_amount > 50_000_000:
                score = 8.0  # Очень сильный отток
            elif net_amount > 20_000_000:
                score = 5.0
            elif net_amount > 10_000_000:
                score = 3.0
            else:
                score = 1.0
        elif net_flow == "inflow":
            net_amount = total_deposits - total_withdrawals
            if net_amount > 50_000_000:
                score = -8.0  # Очень сильный приток
            elif net_amount > 20_000_000:
                score = -5.0
            elif net_amount > 10_000_000:
                score = -3.0
            else:
                score = -1.0
        
        return score
    
    def _calculate_wallet_score(self, data: Dict) -> float:
        """
        Рассчитать скор на основе изменения балансов.
        
        Логика:
        - Рост балансов = накопление = бычий
        - Падение балансов = распределение = медвежий
        """
        signal = data.get("signal", "neutral")
        change_24h = data.get("change_24h", 0)
        change_7d = data.get("change_7d", 0)
        
        score = 0.0
        
        if signal == "accumulating":
            # Сильное накопление
            if change_24h > 1000 and change_7d > 5000:
                score = 8.0
            elif change_24h > 500 and change_7d > 2000:
                score = 5.0
            else:
                score = 3.0
        elif signal == "distributing":
            # Сильное распределение
            if change_24h < -1000 and change_7d < -5000:
                score = -8.0
            elif change_24h < -500 and change_7d < -2000:
                score = -5.0
            else:
                score = -3.0
        
        return score
