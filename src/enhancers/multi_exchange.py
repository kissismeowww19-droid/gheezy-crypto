"""
Multi-Exchange Enhancer - сравнение цен и объемов между биржами.

Компоненты:
1. Price Delta - разница цен между биржами (кто ведёт рынок)
2. Volume Comparison - где больше объёма торгов
"""

import logging
import aiohttp
from typing import Dict, Optional, List
from .base import BaseEnhancer

logger = logging.getLogger(__name__)


class MultiExchangeEnhancer(BaseEnhancer):
    """
    Анализатор Multi-Exchange.
    
    Параметры:
    - Биржи: Binance, Bybit, OKX, Coinbase
    - Вес в сигнале: 5%
    """
    
    # Маппинг символов для разных бирж
    BINANCE_SYMBOL_MAPPING = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT",
        "TON": "TONUSDT",
    }
    
    BYBIT_SYMBOL_MAPPING = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT",
        "TON": "TONUSDT",
    }
    
    OKX_SYMBOL_MAPPING = {
        "BTC": "BTC-USDT",
        "ETH": "ETH-USDT",
        "SOL": "SOL-USDT",
        "XRP": "XRP-USDT",
        "TON": "TON-USDT",
    }
    
    COINBASE_SYMBOL_MAPPING = {
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
        "SOL": "SOL-USD",
        "XRP": "XRP-USD",
        # TON не торгуется на Coinbase
    }
    
    def __init__(self):
        """Инициализация Multi-Exchange Enhancer."""
        super().__init__()
        self._cache = {}
        self._cache_ttl = 60  # 1 минута кэш
    
    async def get_score(self, coin: str, **kwargs) -> float:
        """
        Получить скор Multi-Exchange для монеты.
        
        Возвращает скор от -5 до +5:
        - Binance цена выше других = Binance ведёт вверх = положительный
        - Binance объём растёт = подтверждение движения
        
        Args:
            coin: Символ монеты
        
        Returns:
            float: Скор от -5 до +5
        """
        try:
            coin = coin.upper()
            
            # Получаем цены и объемы с всех бирж
            exchange_data = await self._get_multi_exchange_data(coin)
            
            if not exchange_data or len(exchange_data) < 2:
                self.logger.warning(f"Insufficient exchange data for {coin}")
                return 0.0
            
            # Рассчитываем price delta
            price_delta_score = self._calculate_price_delta_score(exchange_data)
            
            # Рассчитываем volume comparison score
            volume_score = self._calculate_volume_score(exchange_data)
            
            # Итоговый скор (price delta важнее)
            score = (price_delta_score * 0.6) + (volume_score * 0.4)
            
            # Ограничиваем в диапазоне [-5, 5]
            score = self.clamp(score, -5.0, 5.0)
            
            self.logger.info(
                f"Multi-Exchange score for {coin}: {score:.2f} "
                f"(Price delta: {price_delta_score:.2f}, Volume: {volume_score:.2f})"
            )
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error calculating Multi-Exchange score for {coin}: {e}", exc_info=True)
            return 0.0
    
    async def get_leader(self, coin: str) -> str:
        """
        Определить биржу-лидера по цене.
        
        Args:
            coin: Символ монеты
        
        Returns:
            str: Название биржи-лидера
        """
        try:
            coin = coin.upper()
            
            # Получаем данные с всех бирж
            exchange_data = await self._get_multi_exchange_data(coin)
            
            if not exchange_data:
                return "N/A"
            
            # Находим биржу с самой высокой ценой
            leader = max(exchange_data.items(), key=lambda x: x[1]['price'])
            
            return leader[0]
            
        except Exception as e:
            self.logger.error(f"Error getting exchange leader for {coin}: {e}")
            return "N/A"
    
    async def _get_multi_exchange_data(self, coin: str) -> Dict[str, Dict]:
        """
        Получить данные с нескольких бирж.
        
        Args:
            coin: Символ монеты
        
        Returns:
            Dict: {
                'binance': {'price': float, 'volume': float},
                'bybit': {'price': float, 'volume': float},
                ...
            }
        """
        results = {}
        
        # Binance
        binance_data = await self._get_binance_data(coin)
        if binance_data:
            results['Binance'] = binance_data
        
        # Bybit
        bybit_data = await self._get_bybit_data(coin)
        if bybit_data:
            results['Bybit'] = bybit_data
        
        # OKX
        okx_data = await self._get_okx_data(coin)
        if okx_data:
            results['OKX'] = okx_data
        
        # Coinbase (если поддерживается)
        if coin in self.COINBASE_SYMBOL_MAPPING:
            coinbase_data = await self._get_coinbase_data(coin)
            if coinbase_data:
                results['Coinbase'] = coinbase_data
        
        return results
    
    async def _get_binance_data(self, coin: str) -> Optional[Dict]:
        """Получить данные с Binance."""
        try:
            symbol = self.BINANCE_SYMBOL_MAPPING.get(coin)
            if not symbol:
                return None
            
            url = "https://api.binance.com/api/v3/ticker/24hr"
            params = {"symbol": symbol}
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'price': float(data.get('lastPrice', 0)),
                            'volume': float(data.get('volume', 0))
                        }
                    return None
        except Exception as e:
            self.logger.debug(f"Error fetching Binance data for {coin}: {e}")
            return None
    
    async def _get_bybit_data(self, coin: str) -> Optional[Dict]:
        """Получить данные с Bybit."""
        try:
            symbol = self.BYBIT_SYMBOL_MAPPING.get(coin)
            if not symbol:
                return None
            
            url = "https://api.bybit.com/v5/market/tickers"
            params = {
                "category": "spot",
                "symbol": symbol
            }
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data.get('result', {})
                        tickers = result.get('list', [])
                        
                        if tickers:
                            ticker = tickers[0]
                            return {
                                'price': float(ticker.get('lastPrice', 0)),
                                'volume': float(ticker.get('volume24h', 0))
                            }
                    return None
        except Exception as e:
            self.logger.debug(f"Error fetching Bybit data for {coin}: {e}")
            return None
    
    async def _get_okx_data(self, coin: str) -> Optional[Dict]:
        """Получить данные с OKX."""
        try:
            symbol = self.OKX_SYMBOL_MAPPING.get(coin)
            if not symbol:
                return None
            
            url = "https://www.okx.com/api/v5/market/ticker"
            params = {"instId": symbol}
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        tickers = data.get('data', [])
                        
                        if tickers:
                            ticker = tickers[0]
                            return {
                                'price': float(ticker.get('last', 0)),
                                'volume': float(ticker.get('vol24h', 0))
                            }
                    return None
        except Exception as e:
            self.logger.debug(f"Error fetching OKX data for {coin}: {e}")
            return None
    
    async def _get_coinbase_data(self, coin: str) -> Optional[Dict]:
        """Получить данные с Coinbase."""
        try:
            symbol = self.COINBASE_SYMBOL_MAPPING.get(coin)
            if not symbol:
                return None
            
            url = f"https://api.coinbase.com/v2/exchange-rates"
            params = {"currency": coin}
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        rates = data.get('data', {}).get('rates', {})
                        
                        if 'USD' in rates:
                            # Получаем 24h stats отдельно
                            stats_url = f"https://api.exchange.coinbase.com/products/{symbol}/stats"
                            async with session.get(stats_url, timeout=timeout) as stats_response:
                                if stats_response.status == 200:
                                    stats = await stats_response.json()
                                    return {
                                        'price': float(stats.get('last', 0)),
                                        'volume': float(stats.get('volume', 0))
                                    }
                    return None
        except Exception as e:
            self.logger.debug(f"Error fetching Coinbase data for {coin}: {e}")
            return None
    
    def _calculate_price_delta_score(self, exchange_data: Dict[str, Dict]) -> float:
        """
        Рассчитать скор на основе разницы цен между биржами.
        
        Логика:
        - Binance цена выше остальных = Binance ведёт вверх = положительный
        - Binance цена ниже остальных = Binance ведёт вниз = отрицательный
        
        Args:
            exchange_data: Данные с бирж
        
        Returns:
            float: Скор от -5 до +5
        """
        if 'Binance' not in exchange_data or len(exchange_data) < 2:
            return 0.0
        
        binance_price = exchange_data['Binance']['price']
        
        # Рассчитываем среднюю цену по остальным биржам
        other_prices = [
            data['price'] for name, data in exchange_data.items()
            if name != 'Binance' and data['price'] > 0
        ]
        
        if not other_prices:
            return 0.0
        
        avg_other_price = sum(other_prices) / len(other_prices)
        
        # Рассчитываем разницу в процентах
        price_diff_pct = ((binance_price - avg_other_price) / avg_other_price) * 100
        
        # Нормализуем к [-5, 5]
        # Предполагаем, что разница > 0.5% = сильный сигнал
        score = self.clamp(price_diff_pct * 10, -5.0, 5.0)
        
        return score
    
    def _calculate_volume_score(self, exchange_data: Dict[str, Dict]) -> float:
        """
        Рассчитать скор на основе объема торгов.
        
        Логика:
        - Binance объём больше остальных = подтверждение движения
        
        Args:
            exchange_data: Данные с бирж
        
        Returns:
            float: Скор от -5 до +5
        """
        if 'Binance' not in exchange_data or len(exchange_data) < 2:
            return 0.0
        
        binance_volume = exchange_data['Binance']['volume']
        
        # Рассчитываем общий объем по всем биржам
        total_volume = sum(data['volume'] for data in exchange_data.values() if data['volume'] > 0)
        
        if total_volume == 0:
            return 0.0
        
        # Доля Binance в общем объеме
        binance_share = binance_volume / total_volume
        
        # Если доля Binance > 50% = положительный сигнал (до +3)
        # Если доля Binance < 30% = отрицательный сигнал (до -3)
        if binance_share > 0.5:
            score = min(3.0, (binance_share - 0.5) * 10)
        elif binance_share < 0.3:
            score = max(-3.0, (binance_share - 0.3) * 10)
        else:
            score = 0.0
        
        return score
