"""
AI Signals - анализ и прогнозирование движения цен на основе данных китов и рынка.

Анализирует активность китов и рыночные данные для прогнозирования движения цены на ближайший час.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import aiohttp
import asyncio
import numpy as np

from api_manager import get_coin_price
from signals.indicators import (
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_ma_crossover, calculate_stochastic_rsi, calculate_mfi,
    calculate_roc, calculate_williams_r, calculate_atr, calculate_keltner_channels,
    calculate_obv, calculate_vwap, calculate_volume_sma,
    calculate_pivot_points, calculate_fibonacci_levels,
    calculate_rsi_divergence, calculate_adx, detect_volume_spike,
    detect_candlestick_patterns, calculate_macd_divergence, _calculate_ema
)
from signals.data_sources import DataSourceManager
from signals.multi_timeframe import MultiTimeframeAnalyzer
from signals.price_forecast import PriceForecastAnalyzer
from signals.technical_analysis import (
    calculate_ichimoku, calculate_volume_profile, calculate_cvd,
    calculate_market_structure, find_order_blocks, find_fvg
)
from signals.whale_analysis import DeepWhaleAnalyzer
from signals.derivatives_analysis import DeepDerivativesAnalyzer
from signals.signal_stability import SignalStabilityManager
from signals.message_formatter import CompactMessageFormatter

try:
    from signals.phase3 import MacroAnalyzer, OptionsAnalyzer, SocialSentimentAnalyzer
    PHASE3_MACRO = True
    PHASE3_OPTIONS = True
    PHASE3_AVAILABLE = True
except ImportError:
    PHASE3_MACRO = False
    PHASE3_OPTIONS = False
    PHASE3_AVAILABLE = False

try:
    from enhancers import EnhancerManager
    ENHANCERS_AVAILABLE = True
except ImportError:
    ENHANCERS_AVAILABLE = False

logger = logging.getLogger(__name__)


def clamp(value: float, min_val: float = -10.0, max_val: float = 10.0) -> float:
    """Ограничивает значение в диапазоне [-10, 10]"""
    return max(min_val, min(max_val, value))


# DEPRECATED: Old SignalStabilizer class removed - now using SignalStabilityManager
# See signals.signal_stability for the new implementation with improved logic:
# - Cooldown: 1 hour minimum between direction changes
# - Confirmations: 3 confirmations required for direction change
# - Score threshold: 30% score change bypasses cooldown


class AISignalAnalyzer:
    """
    Анализатор AI сигналов для криптовалют.
    
    Использует данные китов и рыночные данные для прогнозирования движения цены.
    """
    
    # Константы для расчёта сигнала
    WHALE_SCORE_WEIGHT = 40  # Максимальный вес whale score
    PRICE_SCORE_WEIGHT = 30  # Максимальный вес price score
    VOLUME_SCORE_VALUE = 10  # Значение volume score
    HIGH_VOLUME_THRESHOLD = 10_000_000_000  # Порог высокого объёма ($10B)
    
    # Константы для нормализации score в проценты (диапазон -80 до +80)
    MIN_SCORE = -80  # Минимальный возможный score
    MAX_SCORE = 80   # Максимальный возможный score
    SCORE_RANGE = MAX_SCORE - MIN_SCORE  # Полный диапазон score (160)
    
    # Новые константы для расширенного анализа
    CACHE_TTL_PRICE_HISTORY = 300  # 5 минут
    CACHE_TTL_FEAR_GREED = 1800  # 30 минут
    CACHE_TTL_FUNDING_RATE = 300  # 5 минут
    MIN_PRICE_POINTS = 30  # Минимум точек для индикаторов
    
    # Веса для 22-факторной системы (100% total)
    # Долгосрочные факторы (35% веса)
    WHALE_WEIGHT = 0.04          # 4%
    TREND_WEIGHT = 0.05          # 5%
    MOMENTUM_WEIGHT = 0.04       # 4%
    VOLATILITY_WEIGHT = 0.04     # 4%
    VOLUME_WEIGHT = 0.04         # 4%
    MARKET_WEIGHT = 0.04         # 4%
    ORDERBOOK_WEIGHT = 0.04      # 4%
    DERIVATIVES_WEIGHT = 0.03    # 3%
    ONCHAIN_WEIGHT = 0.02        # 2%
    SENTIMENT_WEIGHT = 0.01      # 1%
    
    # Краткосрочные факторы (35% веса)
    SHORT_TREND_WEIGHT = 0.08    # 8% - RSI 5м/15м, EMA
    TRADES_FLOW_WEIGHT = 0.07    # 7% - Buy/Sell flow
    LIQUIDATIONS_WEIGHT = 0.06   # 6% - Ликвидации
    ORDERBOOK_DELTA_WEIGHT = 0.07 # 7% - Изменение order book
    PRICE_MOMENTUM_WEIGHT = 0.07 # 7% - Движение цены за 10 мин
    
    # Новые источники (30% веса)
    COINGLASS_OI_WEIGHT = 0.05    # 5% - Open Interest Change
    COINGLASS_TOP_TRADERS_WEIGHT = 0.05  # 5% - Top Traders L/S
    NEWS_SENTIMENT_WEIGHT = 0.05  # 5% - CryptoPanic
    TRADINGVIEW_WEIGHT = 0.06     # 6% - TradingView Rating
    WHALE_ALERT_WEIGHT = 0.05     # 5% - Whale Alert
    SOCIAL_WEIGHT = 0.04          # 4% - LunarCrush
    
    # Deep Whale Analysis Weights (Phase 2)
    WHALE_ACCUMULATION_WEIGHT = 3.0      # Accumulation/Distribution phase
    EXCHANGE_FLOW_DETAILED_WEIGHT = 2.5  # Per-exchange flow analysis
    STABLECOIN_FLOW_WEIGHT = 2.0         # USDT/USDC flows
    
    # Deep Derivatives Analysis Weights (Phase 2)
    OI_PRICE_CORRELATION_WEIGHT = 2.5    # OI/Price correlation
    LIQUIDATION_LEVELS_WEIGHT = 2.0      # Liquidation clustering
    LS_RATIO_DETAILED_WEIGHT = 1.5       # Multi-exchange L/S ratio
    FUNDING_TREND_WEIGHT = 1.5           # Funding rate trend
    BASIS_WEIGHT = 1.0                   # Futures/Spot spread
    
    # Total factors in the analysis system (includes Phase 2 deep analysis)
    TOTAL_FACTORS = 30  # 10 long-term + 5 short-term + 6 new sources + sentiment + 8 deep analysis
    TOTAL_DATA_SOURCES = 30  # Total number of data sources for probability calculation
    
    # Scaling factor for final score calculation
    SCORE_SCALE_FACTOR = 10  # Scale weighted sum from -10/+10 to -100/+100
    
    # Block score calculation constants
    BLOCK_SCORE_MULTIPLIER = 2.0  # Default multiplier for scaling block scores
    DERIVATIVES_SCORE_MULTIPLIER = 1.5  # Special multiplier for derivatives (more factors involved)
    
    # Short-term analysis constants
    EMA_CROSSOVER_THRESHOLD = 0.001  # 0.1% threshold for EMA crossover detection
    LONG_LIQUIDATION_RATIO = 0.7     # Assumed ratio of long liquidations in total
    SHORT_LIQUIDATION_RATIO = 0.3    # Assumed ratio of short liquidations in total
    TRADES_FLOW_BULLISH_THRESHOLD = 1.5   # Buy/Sell ratio threshold for bullish
    TRADES_FLOW_BEARISH_THRESHOLD = 0.67  # Buy/Sell ratio threshold for bearish
    TRADES_FLOW_NEUTRAL_DIVISOR = 0.33    # Normalization divisor for neutral range
    
    # Conflict detection constants
    CONFLICT_SCORE_ADJUSTMENT_FACTOR = 0.5  # Factor to adjust score when resolving conflicts
    CONFLICT_SCORE_BOOST = 15  # Score boost when strong signals override weak ones
    CONFLICT_HIGH_NEUTRAL_THRESHOLD = 0.6  # Threshold for high neutral factor ratio
    CONFLICT_MIN_FACTORS_FOR_BALANCE = 15  # Minimum factors needed to check balance
    RSI_EXTREME_OVERRIDE_FACTOR = 0.3  # Factor for RSI extreme override (more aggressive than normal conflicts)
    RSI_EXTREME_OVERRIDE_BOOST = 20  # Score boost for RSI extreme override
    
    # Signal direction thresholds
    WEAK_SIGNAL_THRESHOLD = 5  # Порог слабого сигнала (боковик)
    
    # Signal stabilization constants
    SMOOTHING_ALPHA = 0.4  # 40% новый score + 60% старый (для сглаживания)
    DEAD_ZONE_DEFAULT = 10  # Мёртвая зона для BTC/ETH
    DEAD_ZONE_TON = 15  # Мёртвая зона для TON (более волатильный)
    HYSTERESIS_THRESHOLD = 30  # Минимальный score для разворота направления
    WEAK_SIGNAL_PROBABILITY = 52  # Фиксированная вероятность для слабых сигналов
    MEDIUM_SIGNAL_MAX_PROBABILITY = 58  # Максимальная вероятность для средних сигналов
    
    # Sideways display constants
    SIDEWAYS_RANGE_PERCENT = 1.0  # Диапазон для боковика (+/-1.0%)
    
    # Supported coins for AI signals
    SUPPORTED_SIGNAL_COINS = {"BTC", "ETH", "TON", "SOL", "XRP"}
    
    # Correlation signals TTL (10 minutes)
    CORRELATION_SIGNAL_TTL = 600  # 10 минут - время жизни сигналов для корреляции
    
    # Maximum contribution from any single factor (prevents over-dominance)
    MAX_SINGLE_FACTOR_SCORE = 15  # ±15 - максимальный вклад одного фактора в итоговый score
    MAX_TOTAL_SCORE = 130  # ±130 - максимальный общий score (с учётом Phase 3)
    MAX_PROBABILITY = 78  # Максимальная вероятность (реалистичная)
    
    # NEW: Weighted Factor System (100% total)
    # Оптимизированные веса для 4-часового прогноза
    
    # Для BTC/ETH (есть whale данные)
    # For BTC/ETH (coins with whale data available)
    FACTOR_WEIGHTS_WITH_WHALES = {
        'whales': 0.25,        # 25% - Smart money, leads market
        'derivatives': 0.20,   # 20% - Trader positions (OI, Funding, L/S)
        'trend': 0.15,         # 15% - EMA, Ichimoku, Market Structure
        'momentum': 0.12,      # 12% - RSI, MACD, Stoch
        'volume': 0.10,        # 10% - Volume, CVD, Volume Spike
        'adx': 0.05,           # 5%  - Trend strength filter
        'divergence': 0.05,    # 5%  - Reversal signals
        'sentiment': 0.04,     # 4%  - Fear & Greed
        'macro': 0.03,         # 3%  - DXY, S&P500, Gold
        'options': 0.01,       # 1%  - Put/Call ratio
    }  # = 100%
    
    # Для TON/SOL/XRP (без whale данных - 25% whale веса перераспределены)
    # For TON/SOL/XRP (coins without whale data - 25% whale weight redistributed)
    FACTOR_WEIGHTS_NO_WHALES = {
        'whales': 0.00,        # 0%  - Нет данных / No data available
        'derivatives': 0.28,   # 28% - +8% (основной индикатор без whale / main indicator without whale)
        'trend': 0.22,         # 22% - +7% (второй по важности / second most important)
        'momentum': 0.16,      # 16% - +4%
        'volume': 0.14,        # 14% - +4%
        'adx': 0.06,           # 6%  - +1%
        'divergence': 0.06,    # 6%  - +1%
        'sentiment': 0.04,     # 4%  - без изменений / unchanged
        'macro': 0.03,         # 3%  - без изменений / unchanged
        'options': 0.01,       # 1%  - без изменений / unchanged
    }  # = 100%
    
    # Legacy weights for backward compatibility
    # DEPRECATED: Use get_weights_for_symbol() to get appropriate weights for a coin
    # TODO: Remove in v2.0.0 after migrating all code to dynamic weights
    FACTOR_WEIGHTS = FACTOR_WEIGHTS_WITH_WHALES
    
    # Price prediction constants
    MAX_PREDICTED_MOVEMENT_PCT = 3.0  # Maximum predicted price change percentage
    MACRO_SCORE_NORMALIZER = 1.5  # Normalize macro score from wider range to -10/+10
    
    # Weighted score scaling factor (converts -10/+10 to -100/+100 for compatibility)
    WEIGHTED_SCORE_SCALE_FACTOR = 10
    
    # OLD + NEW score combination constants
    OLD_SCORE_NORMALIZER = 100.0  # Normalize OLD score from -100/+100 to -1/+1
    NEW_SCORE_NORMALIZER = 10.0   # Normalize NEW score from -10/+10 to -1/+1
    NEW_SCORE_WEIGHT = 0.70        # Weight for NEW weighted system (70%)
    OLD_SCORE_WEIGHT = 0.30        # Weight for OLD 30-factor system (30%)
    COMBINED_SCORE_SCALE = 10.0    # Scale combined score back to -10/+10
    
    # Signal direction thresholds (combined score)
    DIRECTION_LONG_THRESHOLD = 1.75    # Score > 1.75 = LONG
    DIRECTION_SHORT_THRESHOLD = -1.75  # Score < -1.75 = SHORT
    # Between -1.75 and +1.75 = NEUTRAL
    
    # Fibonacci retracement level constants
    FIB_382_LEVEL = 0.382  # 38.2% Fibonacci retracement
    FIB_50_LEVEL = 0.5     # 50% Fibonacci retracement
    FIB_618_LEVEL = 0.618  # 61.8% Fibonacci retracement
    FIB_RANGE_MIN_PCT = 0.02  # Minimum price range (2%) to apply Fibonacci levels
    FIB_DISTANCE_MIN_PCT = 0.003  # Minimum distance from current price (0.3%) to include level
    
    def __init__(self, whale_tracker):
        """
        Инициализация анализатора.
        
        Args:
            whale_tracker: Экземпляр WhaleTracker для получения данных о транзакциях китов
        """
        self.whale_tracker = whale_tracker
        self.data_source_manager = DataSourceManager()
        self.multi_timeframe_analyzer = MultiTimeframeAnalyzer()
        self.price_forecast_analyzer = PriceForecastAnalyzer()
        self.deep_whale_analyzer = DeepWhaleAnalyzer()
        self.deep_derivatives_analyzer = DeepDerivativesAnalyzer()
        self.macro_analyzer = MacroAnalyzer() if PHASE3_MACRO else None
        self.options_analyzer = OptionsAnalyzer() if PHASE3_OPTIONS else None
        self.sentiment_analyzer = SocialSentimentAnalyzer() if PHASE3_AVAILABLE else None
        
        # Enhancers (Order Flow, Volume Profile, Multi-Exchange)
        self.enhancer = EnhancerManager() if ENHANCERS_AVAILABLE else None
        
        # Signal stability manager для предотвращения частых изменений
        self.stability_manager = SignalStabilityManager()
        
        # Compact message formatter для компактных сообщений (15-20 строк)
        self.compact_formatter = CompactMessageFormatter()
        
        # Маппинг символов для whale tracker
        self.blockchain_mapping = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
            "SOL": "Solana",
            "XRP": "XRP",
        }
        
        # Маппинг для CoinGecko API
        self.coingecko_mapping = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "XRP": "ripple",
            "TON": "the-open-network",  # ID TON в CoinGecko
        }
        
        # Маппинг для Bybit
        self.bybit_mapping = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
            "SOL": "SOLUSDT",
            "XRP": "XRPUSDT",
            "TON": "TONUSDT",  # Добавлено для TON
        }
        
        # Простой кэш для внешних API
        self._cache = {}
        self._cache_timestamps = {}
        
        # Хранилище для расчёта delta (краткосрочные данные)
        self._previous_orderbook = {}  # {"BTC": {...}, "ETH": {...}}
        self._previous_prices = {}  # {"BTC": [(timestamp, price), ...], "ETH": [...]}
        
        # Память для стабилизации сигналов
        self.previous_scores: dict[str, float] = {}      # предыдущий score по монете
        self.previous_direction: dict[str, str] = {}     # предыдущее направление по монете
        
        # Хранение последних сигналов для межмонетной проверки (УСТАРЕВШЕЕ, для обратной совместимости)
        self.last_symbol_signals: dict[str, dict] = {}
        
        # Отдельное хранилище для сигналов корреляции (НЕ очищается при clear_cache, имеет TTL)
        self._correlation_signals: dict[str, dict] = {}
        
        # Хранение последнего полного сигнала для предотвращения повторного анализа
        self._last_signal_data: dict[str, dict] = {}
        
        logger.info("AISignalAnalyzer initialized with 22-factor system")
    
    def _get_cache(self, key: str, ttl_seconds: int) -> Optional[Dict]:
        """
        Получить данные из кэша, если они еще актуальны.
        
        Args:
            key: Ключ кэша
            ttl_seconds: Время жизни кэша в секундах
            
        Returns:
            Данные из кэша или None если кэш устарел
        """
        if key not in self._cache:
            return None
        
        age = datetime.now() - self._cache_timestamps.get(key, datetime.min)
        if age > timedelta(seconds=ttl_seconds):
            return None
        
        return self._cache[key]
    
    def _set_cache(self, key: str, value: Dict):
        """
        Сохранить данные в кэш.
        
        Args:
            key: Ключ кэша
            value: Данные для сохранения
        """
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()
    
    def clear_cache(self):
        """
        Очистить кэш внешних API данных для получения свежих данных.
        
        ВАЖНО: _correlation_signals НЕ очищаются - они имеют собственный TTL
        и используются для межмонетной корреляции (BTC → ETH/TON).
        """
        self._cache = {}
        self._cache_timestamps = {}
        logger.info("AISignalAnalyzer cache cleared (correlation signals preserved)")
    
    def _cleanup_expired_signals(self):
        """
        Удалить устаревшие сигналы для корреляции.
        
        Сигналы с истекшим TTL (expires_at < текущее время) удаляются,
        чтобы не влиять на новые расчёты устаревшими данными.
        """
        current_time = time.time()
        expired = [
            symbol for symbol, data in self._correlation_signals.items()
            if data.get("expires_at", 0) < current_time
        ]
        for symbol in expired:
            del self._correlation_signals[symbol]
            logger.debug(f"Expired correlation signal removed: {symbol}")
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired correlation signals: {expired}")
    
    def get_weights_for_symbol(self, symbol: str) -> Dict[str, float]:
        """
        Get appropriate factor weights for the given symbol.
        
        BTC and ETH have whale data available, so use FACTOR_WEIGHTS_WITH_WHALES.
        TON, SOL, XRP don't have whale data, so use FACTOR_WEIGHTS_NO_WHALES.
        
        Args:
            symbol: Symbol (BTC, ETH, TON, SOL, XRP, etc.)
            
        Returns:
            Dict of factor weights (sums to 1.0)
        """
        # Coins with whale data available
        COINS_WITH_WHALE_DATA = {"BTC", "ETH"}
        
        if symbol.upper() in COINS_WITH_WHALE_DATA:
            return self.FACTOR_WEIGHTS_WITH_WHALES
        else:
            return self.FACTOR_WEIGHTS_NO_WHALES
    
    def calculate_weighted_score(self, factors: Dict[str, float], weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate weighted score from factor scores.
        
        Each factor score is expected to be in range -10 to +10.
        Multiply by weight and sum to get final weighted score.
        
        Args:
            factors: Dictionary of factor names to scores (-10 to +10)
            weights: Optional custom weights dict. If None, uses FACTOR_WEIGHTS (legacy mode).
                     For dynamic weights based on symbol, use get_weights_for_symbol(symbol)
                     and pass the result here. This allows BTC/ETH to use WITH_WHALES weights
                     while TON/SOL/XRP use NO_WHALES weights.
            
        Returns:
            Weighted score (-10 to +10)
            
        Note:
            Factors outside the -10/+10 range are clamped to avoid outliers.
            
        Example:
            >>> # For BTC (has whale data)
            >>> btc_weights = analyzer.get_weights_for_symbol('BTC')
            >>> score = analyzer.calculate_weighted_score(factors, weights=btc_weights)
            >>> # For TON (no whale data)
            >>> ton_weights = analyzer.get_weights_for_symbol('TON')
            >>> score = analyzer.calculate_weighted_score(factors, weights=ton_weights)
        """
        # Use provided weights or fallback to legacy FACTOR_WEIGHTS
        weights_to_use = weights if weights is not None else self.FACTOR_WEIGHTS
        
        total = 0.0
        for factor, score in factors.items():
            weight = weights_to_use.get(factor, 0)
            # Clamp score to -10/+10 range for safety
            clamped_score = max(-10, min(10, score))
            total += clamped_score * weight
        
        return total
    
    def calculate_adaptive_threshold(self, bullish_count: int, bearish_count: int) -> tuple[float, str]:
        """
        Рассчитывает адаптивный порог на основе конфликта факторов.
        
        Args:
            bullish_count: Количество бычьих факторов
            bearish_count: Количество медвежьих факторов
        
        Returns:
            tuple: (threshold, conflict_level)
            - threshold: адаптированный порог
            - conflict_level: "none", "moderate", "strong"
        """
        BASE_THRESHOLD = 1.75
        
        # Минимум факторов для анализа конфликта
        min_factors = min(bullish_count, bearish_count)
        
        if min_factors >= 2:
            difference = abs(bullish_count - bearish_count)
            
            if difference == 0:
                # Сильный конфликт: равное количество
                return BASE_THRESHOLD + 0.75, "strong"
            elif difference == 1:
                # Умеренный конфликт
                return BASE_THRESHOLD + 0.5, "moderate"
        
        return BASE_THRESHOLD, "none"
    
    def apply_adaptive_threshold(self, weighted_score: float, bullish_count: int, bearish_count: int) -> tuple[str, Optional[str]]:
        """
        Применяет адаптивный порог для определения направления.
        
        Returns:
            tuple: (direction, warning_message)
        """
        threshold, conflict_level = self.calculate_adaptive_threshold(bullish_count, bearish_count)
        
        if weighted_score > threshold:
            direction = "long"
        elif weighted_score < -threshold:
            direction = "short"
        else:
            direction = "sideways"
        
        # Предупреждение о конфликте
        if conflict_level == "strong":
            warning = "⚠️ Сильный конфликт факторов — порог повышен до ±2.50"
        elif conflict_level == "moderate":
            warning = "⚠️ Умеренный конфликт — порог повышен до ±2.25"
        else:
            warning = None
        
        return direction, warning
    
    def calculate_real_sr_levels(self, ohlcv_data: List[dict], current_price: float) -> Dict:
        """
        Calculate REAL support and resistance levels from actual price data.
        
        Finds levels from:
        1. Recent swing highs/lows (last 50-100 candles)
        2. Round numbers ($85000, $90000, etc.)
        3. Previous day/week high/low
        
        Args:
            ohlcv_data: List of OHLCV candles with 'high', 'low', 'close' keys
            current_price: Current price
            
        Returns:
            Dict with resistances, supports, nearest_resistance, nearest_support
        """
        from signals.indicators import find_swing_points, count_touches, calculate_level_strength
        
        levels = []
        
        if not ohlcv_data or len(ohlcv_data) < 5:
            # Fallback to simple levels based on current price
            return {
                'resistances': [
                    {'price': current_price * 1.02, 'strength': 2, 'source': 'calculated'},
                    {'price': current_price * 1.04, 'strength': 2, 'source': 'calculated'},
                    {'price': current_price * 1.06, 'strength': 2, 'source': 'calculated'},
                ],
                'supports': [
                    {'price': current_price * 0.98, 'strength': 2, 'source': 'calculated'},
                    {'price': current_price * 0.96, 'strength': 2, 'source': 'calculated'},
                    {'price': current_price * 0.94, 'strength': 2, 'source': 'calculated'},
                ],
                'nearest_resistance': current_price * 1.02,
                'nearest_support': current_price * 0.98,
            }
        
        # 1. Find swing highs/lows
        swing_highs, swing_lows = find_swing_points(ohlcv_data, lookback=min(100, len(ohlcv_data)))
        
        for swing in swing_highs:
            touches = count_touches(ohlcv_data, swing.price)
            strength = calculate_level_strength(swing.price, 'swing_high', touches)
            if swing.price > current_price:
                levels.append({
                    'price': swing.price,
                    'type': 'resistance',
                    'source': 'swing_high',
                    'strength': strength,
                    'touches': touches
                })
        
        for swing in swing_lows:
            touches = count_touches(ohlcv_data, swing.price)
            strength = calculate_level_strength(swing.price, 'swing_low', touches)
            if swing.price < current_price:
                levels.append({
                    'price': swing.price,
                    'type': 'support',
                    'source': 'swing_low',
                    'strength': strength,
                    'touches': touches
                })
        
        # 2. Round numbers (every $1000 for BTC, or appropriate for other coins)
        if current_price >= 1000:
            step = 1000
        elif current_price >= 100:
            step = 100
        elif current_price >= 10:
            step = 10
        else:
            step = 1
        
        base = round(current_price / step) * step
        for offset in [-2*step, -step, 0, step, 2*step]:
            level = base + offset
            if level > 0 and abs(level - current_price) / current_price > 0.005:  # At least 0.5% away
                if level > current_price:
                    levels.append({
                        'price': level,
                        'type': 'resistance',
                        'source': 'round_number',
                        'strength': 3,
                        'touches': 0
                    })
                elif level < current_price:
                    levels.append({
                        'price': level,
                        'type': 'support',
                        'source': 'round_number',
                        'strength': 3,
                        'touches': 0
                    })
        
        # 3. Previous day/week high/low (last 24-48 4h candles)
        lookback_candles = min(48, len(ohlcv_data))
        if lookback_candles >= 24:
            recent_data = ohlcv_data[-lookback_candles:]
            prev_high = max(c.get('high', 0) for c in recent_data)
            prev_low = min(c.get('low', float('inf')) for c in recent_data)
            
            if prev_high != current_price and prev_high > 0:
                levels.append({
                    'price': prev_high,
                    'type': 'resistance' if prev_high > current_price else 'support',
                    'source': 'prev_high',
                    'strength': 5,
                    'touches': 1
                })
            
            if prev_low != current_price and prev_low < float('inf'):
                levels.append({
                    'price': prev_low,
                    'type': 'support' if prev_low < current_price else 'resistance',
                    'source': 'prev_low',
                    'strength': 5,
                    'touches': 1
                })
            
            # 4. Fibonacci retracement levels (38.2%, 50%, 61.8% of weekly range)
            if prev_high > 0 and prev_low < float('inf'):
                price_range = prev_high - prev_low
                # Only add Fibonacci levels if range is significant (> 2%)
                if price_range / current_price > self.FIB_RANGE_MIN_PCT:
                    fib_382 = prev_high - (self.FIB_382_LEVEL * price_range)
                    fib_50 = prev_high - (self.FIB_50_LEVEL * price_range)
                    fib_618 = prev_high - (self.FIB_618_LEVEL * price_range)
                    
                    fib_levels_data = [
                        (fib_382, '38.2%'),
                        (fib_50, '50%'),
                        (fib_618, '61.8%'),
                    ]
                    
                    for fib_level, fib_name in fib_levels_data:
                        # Skip if too close to current price (< 0.3%)
                        if abs(fib_level - current_price) / current_price > self.FIB_DISTANCE_MIN_PCT:
                            level_type = 'resistance' if fib_level > current_price else 'support'
                            levels.append({
                                'price': fib_level,
                                'type': level_type,
                                'source': f'fib_{fib_name}',
                                'strength': 4,  # Fibonacci levels are strong
                                'touches': 0
                            })
        
        # Filter and sort
        resistances = [l for l in levels if l['type'] == 'resistance' and l['price'] > current_price]
        supports = [l for l in levels if l['type'] == 'support' and l['price'] < current_price]
        
        # Sort resistances by price (ascending) and take top 3
        resistances = sorted(resistances, key=lambda x: x['price'])[:3]
        
        # Sort supports by price (descending) and take top 3
        supports = sorted(supports, key=lambda x: x['price'], reverse=True)[:3]
        
        # Get nearest levels
        nearest_resistance = resistances[0]['price'] if resistances else current_price * 1.02
        nearest_support = supports[0]['price'] if supports else current_price * 0.98
        
        return {
            'resistances': resistances,
            'supports': supports,
            'nearest_resistance': nearest_resistance,
            'nearest_support': nearest_support,
        }
    
    def calculate_real_targets(
        self,
        direction: str,
        current_price: float,
        resistances: list,
        supports: list,
        atr: float
    ) -> Dict:
        """
        Calculate real TP/SL based on S/R levels instead of fixed percentages.
        
        Logic:
        - LONG: TP on resistances, SL below nearest support + ATR buffer
        - SHORT: TP on supports, SL above nearest resistance + ATR buffer
        - SIDEWAYS: No specific targets
        
        Args:
            direction: Signal direction ("long", "short", "sideways")
            current_price: Current price
            resistances: List of resistance levels [{'price': float, 'strength': int, ...}, ...]
            supports: List of support levels [{'price': float, 'strength': int, ...}, ...]
            atr: Average True Range value for buffer calculation
            
        Returns:
            Dict with tp1, tp2, stop_loss, rr_ratio, risk_percent, reward_percent
        """
        # Calculate adaptive ATR buffer based on volatility
        atr_pct = (atr / current_price * 100) if current_price > 0 else 2.0
        
        if atr_pct > 3.0:
            # High volatility - wider buffer
            stop_buffer_multiplier = 0.75
        elif atr_pct < 1.5:
            # Low volatility - narrower buffer
            stop_buffer_multiplier = 0.3
        else:
            # Normal volatility - standard buffer
            stop_buffer_multiplier = 0.5
        
        if direction == "long":
            # LONG: TP on resistances, SL below support
            if len(resistances) > 0:
                tp1 = resistances[0]['price']
            else:
                tp1 = current_price * 1.015  # Fallback to +1.5%
            
            if len(resistances) > 1:
                tp2 = resistances[1]['price']
            else:
                tp2 = current_price * 1.025  # Fallback to +2.5%
            
            # Stop below nearest support with ATR buffer
            if len(supports) > 0:
                nearest_support = supports[0]['price']
            else:
                nearest_support = current_price * 0.97  # Fallback to -3%
            
            stop_loss = nearest_support - (atr * stop_buffer_multiplier)
            
            # Ensure stop loss doesn't go below reasonable level (max -5%)
            min_stop = current_price * 0.95
            if stop_loss < min_stop:
                stop_loss = min_stop
            
        elif direction == "short":
            # SHORT: TP on supports, SL above resistance
            if len(supports) > 0:
                tp1 = supports[0]['price']
            else:
                tp1 = current_price * 0.985  # Fallback to -1.5%
            
            if len(supports) > 1:
                tp2 = supports[1]['price']
            else:
                tp2 = current_price * 0.975  # Fallback to -2.5%
            
            # Stop above nearest resistance with ATR buffer
            if len(resistances) > 0:
                nearest_resistance = resistances[0]['price']
            else:
                nearest_resistance = current_price * 1.03  # Fallback to +3%
            
            stop_loss = nearest_resistance + (atr * stop_buffer_multiplier)
            
            # Ensure stop loss doesn't go above reasonable level (max +5%)
            max_stop = current_price * 1.05
            if stop_loss > max_stop:
                stop_loss = max_stop
            
        else:  # sideways
            tp1 = None
            tp2 = None
            stop_loss = None
        
        # Calculate real R:R ratio
        if tp1 and stop_loss and direction in ["long", "short"]:
            if direction == "long":
                reward = tp1 - current_price
                risk = current_price - stop_loss
            else:  # short
                reward = current_price - tp1
                risk = stop_loss - current_price
            
            rr_ratio = reward / risk if risk > 0 else 0
        else:
            rr_ratio = 0
        
        # Calculate risk and reward percentages
        if stop_loss and current_price > 0:
            risk_percent = round((abs(current_price - stop_loss) / current_price * 100), 2)
        else:
            risk_percent = 0
        
        if tp1 and current_price > 0:
            reward_percent = round((abs(tp1 - current_price) / current_price * 100), 2)
        else:
            reward_percent = 0
        
        return {
            "tp1": tp1,
            "tp2": tp2,
            "stop_loss": stop_loss,
            "rr_ratio": round(rr_ratio, 1),
            "risk_percent": risk_percent,
            "reward_percent": reward_percent,
        }
    
    def predict_price_4h(
        self, 
        current_price: float, 
        weighted_score: float, 
        sr_levels: Dict, 
        atr: float
    ) -> Dict:
        """
        Predict price movement for next 4 hours.
        
        Logic:
        - weighted_score > 0: expect price UP
        - weighted_score < 0: expect price DOWN
        - Magnitude based on score strength and ATR
        - Respect S/R levels as targets/barriers
        
        Args:
            current_price: Current price
            weighted_score: Weighted score from -10 to +10
            sr_levels: Support/resistance levels dict
            atr: Average True Range value
            
        Returns:
            Dict with predicted_price, predicted_change_pct, direction, confidence, price_range
        """
        # Base movement based on score (-10 to +10 scale)
        # Typical 4h move is 0.5-2% for BTC
        base_move_pct = weighted_score * 0.3  # -3% to +3% max
        
        # Adjust for ATR (volatility)
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 1.5
        adjusted_move = base_move_pct * (atr_pct / 1.5)  # Normalize to typical ATR
        
        # Cap movement to prevent unrealistic predictions
        adjusted_move = max(-self.MAX_PREDICTED_MOVEMENT_PCT, min(self.MAX_PREDICTED_MOVEMENT_PCT, adjusted_move))
        
        predicted_price = current_price * (1 + adjusted_move / 100)
        
        # Respect S/R levels
        if adjusted_move > 0:
            # Going up - resistance is barrier
            nearest_r = sr_levels.get('nearest_resistance', current_price * 1.02)
            if predicted_price > nearest_r:
                predicted_price = nearest_r * 0.995  # Stop just before resistance
        else:
            # Going down - support is barrier
            nearest_s = sr_levels.get('nearest_support', current_price * 0.98)
            if predicted_price < nearest_s:
                predicted_price = nearest_s * 1.005  # Stop just before support
        
        # Calculate confidence (50-85%)
        confidence = min(85, 50 + abs(weighted_score) * 3.5)
        
        # Direction
        direction = 'UP' if predicted_price > current_price else 'DOWN'
        
        # Price range based on ATR
        price_range_low = current_price - atr
        price_range_high = current_price + atr
        
        # Calculate predicted change percentage
        predicted_change_pct = ((predicted_price / current_price) - 1) * 100 if current_price > 0 else 0
        
        return {
            'predicted_price': predicted_price,
            'predicted_change_pct': predicted_change_pct,
            'direction': direction,
            'confidence': confidence,
            'price_range': {
                'low': price_range_low,
                'high': price_range_high,
            }
        }
    
    async def get_whale_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение данных о транзакциях китов за последний час.
        
        Args:
            symbol: Символ монеты (BTC, ETH)
            
        Returns:
            Dict с данными китов или None если данные недоступны
        """
        try:
            blockchain = self.blockchain_mapping.get(symbol)
            if not blockchain:
                logger.warning(f"Unknown symbol for whale tracking: {symbol}")
                return None
            
            # Получаем транзакции для конкретного блокчейна
            transactions = await self.whale_tracker.get_transactions_by_blockchain(
                blockchain=blockchain.lower(),
                limit=50
            )
            
            if not transactions:
                logger.info(f"No whale transactions found for {symbol}")
                return {
                    "transaction_count": 0,
                    "total_volume_usd": 0,
                    "deposits": 0,
                    "withdrawals": 0,
                    "largest_transaction": 0,
                    "sentiment": "neutral"
                }
            
            # Подсчитываем депозиты и выводы
            deposits = sum(1 for tx in transactions if tx.is_exchange_deposit)
            withdrawals = sum(1 for tx in transactions if tx.is_exchange_withdrawal)
            total_volume = sum(tx.amount_usd for tx in transactions)
            largest_tx = max((tx.amount_usd for tx in transactions), default=0)
            
            # Определяем настроение
            if withdrawals > deposits:
                sentiment = "bullish"
            elif deposits > withdrawals:
                sentiment = "bearish"
            else:
                sentiment = "neutral"
            
            return {
                "transaction_count": len(transactions),
                "total_volume_usd": total_volume,
                "deposits": deposits,
                "withdrawals": withdrawals,
                "largest_transaction": largest_tx,
                "sentiment": sentiment
            }
            
        except Exception as e:
            logger.error(f"Error getting whale data for {symbol}: {e}")
            return None
    
    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение рыночных данных.
        
        Args:
            symbol: Символ монеты (BTC, ETH)
            
        Returns:
            Dict с рыночными данными или None если данные недоступны
        """
        try:
            price_data = await get_coin_price(symbol)
            
            if not price_data.get("success"):
                logger.warning(f"Failed to get market data for {symbol}")
                return None
            
            return {
                "price_usd": price_data.get("price_usd", 0),
                "change_24h": price_data.get("change_24h", 0),
                "volume_24h": price_data.get("volume_24h", 0),
                "market_cap": price_data.get("market_cap", 0),
            }
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
    
    async def get_price_history_bybit(self, symbol: str, interval: str = "60", limit: int = 300) -> Optional[List[float]]:
        """
        Получение истории цен с Bybit вместо CoinGecko (fallback для rate limit).
        
        Endpoint: https://api.bybit.com/v5/market/kline?category=spot&symbol=ETHUSDT&interval=60&limit=300
        
        Args:
            symbol: BTC или ETH
            interval: Интервал в минутах (60 = 1 час)
            limit: Количество свечей (макс 1000)
        
        Returns:
            List[float]: Список цен закрытия
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown Bybit symbol for price history: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/kline"
            params = {
                "category": "spot",
                "symbol": bybit_symbol,
                "interval": interval,
                "limit": limit
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data.get("result", {})
                        klines = result.get("list", [])
                        
                        if klines:
                            # Bybit returns [startTime, open, high, low, close, volume, turnover]
                            # Reverse order (most recent first -> oldest first)
                            prices = [float(kline[4]) for kline in reversed(klines)]
                            logger.info(f"Fetched {len(prices)} price points from Bybit for {symbol}")
                            return prices
                    else:
                        logger.warning(f"Failed to fetch Bybit price history for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting Bybit price history for {symbol}: {e}")
            return None
    
    async def get_price_history(self, symbol: str, days: int = 1) -> Optional[List[float]]:
        """
        Получение исторических цен для расчёта индикаторов.
        Сначала пробует CoinGecko API, при rate limit использует Bybit.
        
        Args:
            symbol: BTC или ETH
            days: Количество дней (1 день = ~288 точек при интервале 5 мин)
        
        Returns:
            List[float]: Список цен закрытия
        """
        cache_key = f"price_history_{symbol}_{days}"
        
        # Проверяем кэш
        cached_data = self._get_cache(cache_key, self.CACHE_TTL_PRICE_HISTORY)
        if cached_data is not None:
            return cached_data
        
        try:
            coin_id = self.coingecko_mapping.get(symbol)
            if not coin_id:
                logger.warning(f"Unknown coin for price history: {symbol}")
                return None
            
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": "usd",
                "days": days
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices = [price[1] for price in data.get("prices", [])]
                        
                        if prices:
                            self._set_cache(cache_key, prices)
                            logger.info(f"Fetched {len(prices)} price points from CoinGecko for {symbol}")
                            return prices
                    elif response.status == 429:
                        logger.warning(f"CoinGecko rate limit reached for {symbol}, trying Bybit fallback...")
                        # Use Bybit as fallback with 200 candles for better technical indicator calculation
                        bybit_prices = await self.get_price_history_bybit(symbol, interval="60", limit=200)
                        if bybit_prices:
                            self._set_cache(cache_key, bybit_prices)
                            return bybit_prices
                        return None
                    else:
                        logger.warning(f"Failed to fetch price history for {symbol}: {response.status}")
                        # Try Bybit as fallback for any error with 200 candles
                        bybit_prices = await self.get_price_history_bybit(symbol, interval="60", limit=200)
                        if bybit_prices:
                            self._set_cache(cache_key, bybit_prices)
                            return bybit_prices
                        return None
        except Exception as e:
            logger.error(f"Error getting price history for {symbol}: {e}")
            # Try Bybit as last resort fallback with 200 candles
            try:
                bybit_prices = await self.get_price_history_bybit(symbol, interval="60", limit=200)
                if bybit_prices:
                    self._set_cache(cache_key, bybit_prices)
                    return bybit_prices
            except Exception as e2:
                logger.error(f"Error getting Bybit fallback for {symbol}: {e2}")
            return None
    
    async def calculate_technical_indicators(self, symbol: str, ohlcv_data: Optional[List] = None) -> Optional[Dict]:
        """
        Calculate all technical indicators.
        
        Args:
            symbol: Symbol (BTC, ETH)
            ohlcv_data: Optional OHLCV data from CryptoCompare
        
        Returns:
            Dict with all technical indicators
        """
        try:
            # Get historical data
            prices = await self.get_price_history(symbol, days=1)
            
            if not prices or len(prices) < self.MIN_PRICE_POINTS:
                logger.warning(f"Insufficient price data for technical indicators: {symbol}")
                return None
            
            result = {}
            
            # Basic indicators (existing)
            rsi = calculate_rsi(prices, period=14)
            macd = calculate_macd(prices)
            bb = calculate_bollinger_bands(prices, period=20)
            
            if rsi:
                result["rsi"] = {
                    "value": rsi.value,
                    "signal": rsi.signal,
                    "period": rsi.period
                }
            
            if macd:
                result["macd"] = {
                    "macd_line": macd.macd_line,
                    "signal_line": macd.signal_line,
                    "histogram": macd.histogram,
                    "signal": macd.signal
                }
            
            if bb:
                result["bollinger_bands"] = {
                    "upper": bb.upper,
                    "middle": bb.middle,
                    "lower": bb.lower,
                    "current_price": bb.current_price,
                    "position": bb.position,
                    "bandwidth": bb.bandwidth,
                    "percent_b": bb.percent_b
                }
            
            # New Trend Indicators
            if len(prices) >= 200:
                ma_cross = calculate_ma_crossover(prices, short_period=50, long_period=200)
                if ma_cross:
                    result["ma_crossover"] = {
                        "ma_short": ma_cross.ma_short,
                        "ma_long": ma_cross.ma_long,
                        "crossover": ma_cross.crossover,
                        "trend": ma_cross.trend
                    }
            
            # New Momentum Indicators
            stoch_rsi = calculate_stochastic_rsi(prices, period=14, smooth_k=3, smooth_d=3)
            if stoch_rsi:
                result["stoch_rsi"] = {
                    "k": stoch_rsi.k,
                    "d": stoch_rsi.d,
                    "signal": stoch_rsi.signal
                }
            
            roc = calculate_roc(prices, period=12)
            if roc:
                result["roc"] = {
                    "value": roc.value,
                    "momentum": roc.momentum
                }
            
            # Indicators requiring OHLCV data
            if ohlcv_data and len(ohlcv_data) >= 14:
                high_prices = [c["high"] for c in ohlcv_data]
                low_prices = [c["low"] for c in ohlcv_data]
                close_prices = [c["close"] for c in ohlcv_data]
                volumes = [c["volumeto"] for c in ohlcv_data]  # Volume in USD
                
                # MFI
                mfi = calculate_mfi(high_prices, low_prices, close_prices, volumes, period=14)
                if mfi:
                    result["mfi"] = {
                        "value": mfi.value,
                        "signal": mfi.signal
                    }
                
                # Williams %R
                williams = calculate_williams_r(high_prices, low_prices, close_prices, period=14)
                if williams:
                    result["williams_r"] = {
                        "value": williams.value,
                        "signal": williams.signal
                    }
                
                # ATR
                atr = calculate_atr(high_prices, low_prices, close_prices, period=14)
                if atr:
                    result["atr"] = {
                        "value": atr.value,
                        "percent": atr.percent,
                        "volatility": atr.volatility
                    }
                
                # Keltner Channels
                keltner = calculate_keltner_channels(high_prices, low_prices, close_prices, period=20, multiplier=2.0)
                if keltner:
                    result["keltner_channels"] = {
                        "upper": keltner.upper,
                        "middle": keltner.middle,
                        "lower": keltner.lower,
                        "position": keltner.position
                    }
                
                # OBV
                obv = calculate_obv(close_prices, volumes)
                if obv:
                    result["obv"] = {
                        "value": obv.value,
                        "trend": obv.trend,
                        "sma": obv.sma
                    }
                
                # VWAP
                vwap = calculate_vwap(high_prices, low_prices, close_prices, volumes)
                if vwap:
                    result["vwap"] = {
                        "value": vwap.value,
                        "position": vwap.position,
                        "deviation_percent": vwap.deviation_percent
                    }
                
                # Volume SMA
                vol_sma = calculate_volume_sma(volumes, period=20)
                if vol_sma:
                    result["volume_sma"] = {
                        "current_volume": vol_sma.current_volume,
                        "sma": vol_sma.sma,
                        "ratio": vol_sma.ratio,
                        "status": vol_sma.status
                    }
                
                # Volume Spike Detection (NEW)
                vol_spike = detect_volume_spike(volumes, threshold=2.0, lookback=20)
                if vol_spike:
                    result["volume_spike"] = {
                        "is_spike": vol_spike.is_spike,
                        "spike_percentage": vol_spike.spike_percentage,
                        "current_volume": vol_spike.current_volume,
                        "average_volume": vol_spike.average_volume
                    }
                
                # ADX - Average Directional Index (NEW)
                adx = calculate_adx(high_prices, low_prices, close_prices, period=14)
                if adx:
                    result["adx"] = {
                        "value": adx.value,
                        "plus_di": adx.plus_di,
                        "minus_di": adx.minus_di,
                        "trend_strength": adx.trend_strength,
                        "direction": adx.direction
                    }
                
                # RSI Divergence Detection (NEW)
                # Need to calculate RSI values for divergence detection
                if rsi and len(close_prices) >= 30:
                    # Calculate RSI for all historical points
                    rsi_values = []
                    for i in range(14, len(close_prices)):
                        temp_rsi = calculate_rsi(close_prices[:i+1], period=14)
                        if temp_rsi:
                            rsi_values.append(temp_rsi.value)
                    
                    if len(rsi_values) >= 14:
                        # Use the last part of prices that matches rsi_values
                        prices_for_div = close_prices[14:]
                        rsi_div = calculate_rsi_divergence(prices_for_div, rsi_values, lookback=14)
                        if rsi_div:
                            result["rsi_divergence"] = {
                                "type": rsi_div.type,
                                "strength": rsi_div.strength,
                                "explanation": rsi_div.explanation
                            }
                    
                    # MACD Divergence (NEW - calculate from histogram)
                    # Требует полную историю MACD histogram для детекции дивергенции
                    if len(close_prices) >= 50:
                        # Пересчитываем MACD для получения полной истории histogram
                        prices_array = np.array(close_prices)
                        
                        # Use the extracted EMA function from indicators module
                        ema_fast = _calculate_ema(prices_array, 12)
                        ema_slow = _calculate_ema(prices_array, 26)
                        macd_line = ema_fast - ema_slow
                        signal_line = _calculate_ema(macd_line, 9)
                        histogram = macd_line - signal_line
                        
                        # Вычисляем MACD Divergence
                        macd_div = calculate_macd_divergence(
                            close_prices,
                            histogram.tolist(),
                            lookback=14
                        )
                        
                        if macd_div:
                            result["macd_divergence"] = {
                                "type": macd_div.type,
                                "strength": macd_div.strength,
                                "explanation": macd_div.explanation
                            }

                
                # Pivot Points (using previous day's data)
                if len(ohlcv_data) >= 2:
                    prev_candle = ohlcv_data[-2]
                    current_price = close_prices[-1]
                    pivot = calculate_pivot_points(
                        prev_candle["high"],
                        prev_candle["low"],
                        prev_candle["close"],
                        current_price
                    )
                    result["pivot_points"] = {
                        "pivot": pivot.pivot,
                        "r1": pivot.r1,
                        "r2": pivot.r2,
                        "r3": pivot.r3,
                        "s1": pivot.s1,
                        "s2": pivot.s2,
                        "s3": pivot.s3,
                        "current_zone": pivot.current_zone
                    }
                
                # Fibonacci Levels
                if len(high_prices) >= 20:
                    period_high = max(high_prices[-20:])
                    period_low = min(low_prices[-20:])
                    current_price = close_prices[-1]
                    fib = calculate_fibonacci_levels(period_high, period_low, current_price)
                    result["fibonacci"] = {
                        "level_0": fib.level_0,
                        "level_236": fib.level_236,
                        "level_382": fib.level_382,
                        "level_50": fib.level_50,
                        "level_618": fib.level_618,
                        "level_786": fib.level_786,
                        "level_100": fib.level_100,
                        "nearest_level": fib.nearest_level,
                        "nearest_value": fib.nearest_value
                    }
            
            logger.info(f"Calculated {len(result)} technical indicators for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators for {symbol}: {e}")
            return None
    
    async def get_fear_greed_index(self) -> Optional[Dict]:
        """
        Получение Fear & Greed Index.
        API: https://api.alternative.me/fng/
        
        Returns:
            Dict: {"value": 75, "classification": "Greed"}
        """
        cache_key = "fear_greed_index"
        
        # Проверяем кэш
        cached_data = self._get_cache(cache_key, self.CACHE_TTL_FEAR_GREED)
        if cached_data is not None:
            return cached_data
        
        try:
            url = "https://api.alternative.me/fng/"
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        fng_data = data.get("data", [{}])[0]
                        
                        result = {
                            "value": int(fng_data.get("value", 50)),
                            "classification": fng_data.get("value_classification", "Neutral")
                        }
                        
                        self._set_cache(cache_key, result)
                        logger.info(f"Fetched Fear & Greed Index: {result['value']}")
                        return result
                    else:
                        logger.warning(f"Failed to fetch Fear & Greed Index: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting Fear & Greed Index: {e}")
            return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        Получение Funding Rate с Bybit.
        API: https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1
        
        Returns:
            Dict: {"rate": 0.0001, "rate_percent": 0.01}
        """
        cache_key = f"funding_rate_{symbol}"
        
        # Проверяем кэш
        cached_data = self._get_cache(cache_key, self.CACHE_TTL_FUNDING_RATE)
        if cached_data is not None:
            return cached_data
        
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for funding rate: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/funding/history"
            params = {
                "category": "linear",
                "symbol": bybit_symbol,
                "limit": 1
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        result_data = data.get("result", {})
                        funding_list = result_data.get("list", [])
                        
                        if funding_list and len(funding_list) > 0:
                            latest_funding = funding_list[0]
                            funding_rate = float(latest_funding.get("fundingRate", 0))
                            rate_percent = funding_rate * 100
                            
                            result = {
                                "rate": funding_rate,
                                "rate_percent": rate_percent
                            }
                            
                            self._set_cache(cache_key, result)
                            logger.info(f"Fetched funding rate for {symbol}: {rate_percent:.4f}%")
                            return result
                        else:
                            logger.warning(f"Empty funding rate data for {symbol}")
                            return None
                    else:
                        logger.warning(f"Failed to fetch funding rate for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            return None
    
    async def get_short_term_ohlcv(self, symbol: str, interval: str = "5", limit: int = 50) -> Optional[List]:
        """
        Получение краткосрочных свечей с Bybit.
        НЕ кэшируется для получения свежих данных!
        
        Args:
            symbol: BTC или ETH
            interval: "5" (5 мин), "15" (15 мин)
            limit: количество свечей
        
        API: https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval=5&limit=50
        
        Returns:
            List of candles: [{"open": 97000, "high": 98000, "low": 96500, "close": 97500, 
                               "volume": 123.45, "timestamp": 1234567890}, ...]
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for short-term OHLCV: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/kline"
            params = {
                "category": "spot",
                "symbol": bybit_symbol,
                "interval": interval,
                "limit": limit
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit kline error: {data.get('retMsg')}")
                            return None
                        
                        klines = data.get("result", {}).get("list", [])
                        
                        if not klines:
                            return None
                        
                        result = []
                        for kline in klines:
                            # Bybit format: [timestamp, open, high, low, close, volume, turnover]
                            result.append({
                                "timestamp": int(kline[0]),
                                "open": float(kline[1]),
                                "high": float(kline[2]),
                                "low": float(kline[3]),
                                "close": float(kline[4]),
                                "volume": float(kline[5])
                            })
                        
                        logger.info(f"Fetched {len(result)} short-term {interval}m candles for {symbol}")
                        return result
                    else:
                        logger.warning(f"Failed to fetch short-term OHLCV for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting short-term OHLCV for {symbol}: {e}")
            return None
    
    async def get_recent_trades_flow(self, symbol: str) -> Optional[Dict]:
        """
        Анализ потока сделок за последние 10 минут.
        НЕ кэшируется для получения свежих данных!
        
        Args:
            symbol: BTC или ETH
        
        API: https://api.bybit.com/v5/market/recent-trade?category=spot&symbol=BTCUSDT&limit=1000
        
        Returns:
            {
                "buy_volume": 1234567,
                "sell_volume": 987654,
                "buy_count": 150,
                "sell_count": 120,
                "flow_ratio": 1.25,  # buy/sell
                "sentiment": "bullish"  # bullish/bearish/neutral
            }
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for trades flow: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/recent-trade"
            params = {
                "category": "spot",
                "symbol": bybit_symbol,
                "limit": 1000
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit trades error: {data.get('retMsg')}")
                            return None
                        
                        trades = data.get("result", {}).get("list", [])
                        
                        if not trades:
                            return None
                        
                        # Filter only last 10 minutes
                        now_ms = datetime.now().timestamp() * 1000
                        ten_min_ago_ms = now_ms - (10 * 60 * 1000)
                        
                        buy_volume = 0.0
                        sell_volume = 0.0
                        buy_count = 0
                        sell_count = 0
                        
                        for trade in trades:
                            trade_time = int(trade.get("time", 0))
                            if trade_time < ten_min_ago_ms:
                                continue
                            
                            price = float(trade.get("price", 0))
                            size = float(trade.get("size", 0))
                            side = trade.get("side", "")
                            
                            if price <= 0 or size <= 0 or not side:
                                continue
                            
                            volume_usd = price * size
                            
                            if side == "Buy":
                                buy_volume += volume_usd
                                buy_count += 1
                            elif side == "Sell":
                                sell_volume += volume_usd
                                sell_count += 1
                        
                        # Calculate flow ratio and sentiment
                        flow_ratio = buy_volume / sell_volume if sell_volume > 0 else 1.0
                        
                        if flow_ratio > 1.2:
                            sentiment = "bullish"
                        elif flow_ratio < 0.83:
                            sentiment = "bearish"
                        else:
                            sentiment = "neutral"
                        
                        result = {
                            "buy_volume": round(buy_volume, 2),
                            "sell_volume": round(sell_volume, 2),
                            "buy_count": buy_count,
                            "sell_count": sell_count,
                            "flow_ratio": round(flow_ratio, 3),
                            "sentiment": sentiment
                        }
                        
                        logger.info(f"Analyzed trades flow for {symbol}: {sentiment} (ratio: {flow_ratio:.2f})")
                        return result
                    else:
                        logger.warning(f"Failed to fetch trades flow for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting trades flow for {symbol}: {e}")
            return None
    
    async def get_liquidations(self, symbol: str) -> Optional[Dict]:
        """
        Получение данных о ликвидациях из Bybit futures.
        НЕ кэшируется для получения свежих данных!
        
        Args:
            symbol: BTC или ETH
        
        Note: Bybit не предоставляет прямого API для ликвидаций.
        Используем Open Interest изменения как прокси для ликвидаций.
        
        Returns:
            {
                "long_liquidations": 5000000,
                "short_liquidations": 3000000,
                "net_liquidations": 2000000,  # long - short
                "sentiment": "bearish"  # много лонг ликвидаций = bearish
            }
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for liquidations: {symbol}")
                return None
            
            # Используем open interest change как прокси для ликвидаций
            url = "https://api.bybit.com/v5/market/open-interest"
            params = {
                "category": "linear",
                "symbol": bybit_symbol,
                "intervalTime": "5min",
                "limit": 10
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("retCode") != 0:
                            logger.warning(f"Bybit OI error: {data.get('retMsg')}")
                            return None
                        
                        oi_list = data.get("result", {}).get("list", [])
                        
                        if not oi_list or len(oi_list) < 2:
                            return None
                        
                        # Calculate OI change
                        latest_oi = float(oi_list[0].get("openInterest", 0))
                        prev_oi = float(oi_list[-1].get("openInterest", 0))
                        oi_change = latest_oi - prev_oi
                        
                        # Negative OI change suggests liquidations
                        # Positive suggests new positions opening
                        if oi_change < 0:
                            # OI decreased = liquidations happened
                            liquidation_volume = abs(oi_change)
                            # Estimate split based on historical ratios
                            long_liquidations = liquidation_volume * self.LONG_LIQUIDATION_RATIO
                            short_liquidations = liquidation_volume * self.SHORT_LIQUIDATION_RATIO
                            sentiment = "bearish"  # More longs liquidated
                        else:
                            # OI increased or stable
                            long_liquidations = 0
                            short_liquidations = 0
                            sentiment = "neutral"
                        
                        net_liquidations = long_liquidations - short_liquidations
                        
                        result = {
                            "long_liquidations": round(long_liquidations, 2),
                            "short_liquidations": round(short_liquidations, 2),
                            "net_liquidations": round(net_liquidations, 2),
                            "sentiment": sentiment
                        }
                        
                        logger.info(f"Analyzed liquidations for {symbol}: {sentiment}")
                        return result
                    else:
                        logger.warning(f"Failed to fetch liquidations for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting liquidations for {symbol}: {e}")
            return None
    
    async def get_orderbook_delta(self, symbol: str) -> Optional[Dict]:
        """
        Изменение order book за последние запросы.
        Сравнивает текущий order book с предыдущим (хранится в памяти).
        НЕ кэшируется для получения свежих данных!
        
        Args:
            symbol: BTC или ETH
        
        Returns:
            {
                "bid_change": +5.2,  # % изменение bid wall
                "ask_change": -3.1,  # % изменение ask wall
                "delta": +8.3,  # bid_change - ask_change
                "sentiment": "bullish"
            }
        """
        try:
            bybit_symbol = self.bybit_mapping.get(symbol)
            if not bybit_symbol:
                logger.warning(f"Unknown symbol for orderbook delta: {symbol}")
                return None
            
            url = "https://api.bybit.com/v5/market/orderbook"
            params = {
                "category": "spot",
                "symbol": bybit_symbol,
                "limit": 50
            }
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        result_data = data.get("result", {})
                        bids = result_data.get("b", [])
                        asks = result_data.get("a", [])
                        
                        if not bids or not asks:
                            return None
                        
                        # Calculate current volumes
                        bid_volume = sum(float(b[1]) for b in bids)
                        ask_volume = sum(float(a[1]) for a in asks)
                        
                        # Get previous orderbook data
                        prev_orderbook = self._previous_orderbook.get(symbol)
                        
                        if prev_orderbook:
                            prev_bid_volume = prev_orderbook["bid_volume"]
                            prev_ask_volume = prev_orderbook["ask_volume"]
                            
                            # Calculate percentage change
                            bid_change = ((bid_volume - prev_bid_volume) / prev_bid_volume * 100) if prev_bid_volume > 0 else 0
                            ask_change = ((ask_volume - prev_ask_volume) / prev_ask_volume * 100) if prev_ask_volume > 0 else 0
                            delta = bid_change - ask_change
                            
                            # Determine sentiment
                            if delta > 5:
                                sentiment = "bullish"
                            elif delta < -5:
                                sentiment = "bearish"
                            else:
                                sentiment = "neutral"
                            
                            result = {
                                "bid_change": round(bid_change, 2),
                                "ask_change": round(ask_change, 2),
                                "delta": round(delta, 2),
                                "sentiment": sentiment
                            }
                        else:
                            # First call, no delta yet
                            result = {
                                "bid_change": 0.0,
                                "ask_change": 0.0,
                                "delta": 0.0,
                                "sentiment": "neutral"
                            }
                        
                        # Store current orderbook for next comparison
                        self._previous_orderbook[symbol] = {
                            "bid_volume": bid_volume,
                            "ask_volume": ask_volume,
                            "timestamp": datetime.now()
                        }
                        
                        logger.info(f"Calculated orderbook delta for {symbol}: {result.get('delta', 0):.2f}%")
                        return result
                    else:
                        logger.warning(f"Failed to fetch orderbook delta for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting orderbook delta for {symbol}: {e}")
            return None
    
    async def get_macro_data(self) -> Dict:
        """Получить макро данные (безопасно)"""
        if not self.macro_analyzer:
            return {'score': 0, 'verdict': 'neutral'}
        try:
            return await self.macro_analyzer.analyze()
        except Exception as e:
            logger.warning(f"Macro analysis failed: {e}")
            return {'score': 0, 'verdict': 'neutral'}
    
    async def get_options_data(self, symbol: str) -> Dict:
        """Получить опционные данные (только BTC/ETH/SOL)"""
        if not self.options_analyzer or symbol.upper() not in ['BTC', 'ETH', 'SOL']:
            return {'score': 0, 'verdict': 'neutral'}
        try:
            return await self.options_analyzer.analyze(symbol)
        except Exception as e:
            logger.warning(f"Options analysis failed: {e}")
            return {'score': 0, 'verdict': 'neutral'}
    
    async def get_sentiment_data(self, symbol: str) -> Dict:
        """Получить social sentiment"""
        if not self.sentiment_analyzer:
            return {'score': 0, 'verdict': 'neutral'}
        try:
            return await self.sentiment_analyzer.analyze(symbol)
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
            return {'score': 0, 'verdict': 'neutral'}
    
    async def get_coinglass_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение данных с Coinglass.
        
        Endpoints:
        - Open Interest: https://open-api.coinglass.com/public/v2/open_interest?symbol=BTC
        - Liquidations: https://open-api.coinglass.com/public/v2/liquidation_history?symbol=BTC&time_type=h1
        - Top Traders L/S: https://open-api.coinglass.com/public/v2/long_short?symbol=BTC&time_type=h1
        
        Returns:
            {
                "oi_change_24h": 2.3,  # % изменение Open Interest
                "liquidations_long": 12000000,  # $ ликвидаций лонгов
                "liquidations_short": 8000000,  # $ ликвидаций шортов
                "top_traders_ratio": 1.8,  # Long/Short ratio топ трейдеров
            }
        """
        try:
            # Coinglass uses uppercase symbols without USDT
            cg_symbol = symbol.upper()
            
            result = {}
            
            # Fetch Open Interest
            try:
                oi_url = f"https://open-api.coinglass.com/public/v2/open_interest"
                params = {"symbol": cg_symbol}
                
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession() as session:
                    async with session.get(oi_url, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("success") and data.get("data"):
                                oi_data = data["data"]
                                result["oi_change_24h"] = float(oi_data.get("oiChangePercent", 0))
                                logger.info(f"Fetched Coinglass OI for {symbol}: {result['oi_change_24h']}%")
            except Exception as e:
                logger.warning(f"Could not fetch Coinglass OI for {symbol}: {e}")
            
            # Fetch Liquidations
            try:
                liq_url = f"https://open-api.coinglass.com/public/v2/liquidation_history"
                params = {"symbol": cg_symbol, "time_type": "h1"}
                
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession() as session:
                    async with session.get(liq_url, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("success") and data.get("data"):
                                liq_data = data["data"]
                                # Assuming structure has long/short liquidations
                                result["liquidations_long"] = float(liq_data.get("longLiquidation", 0))
                                result["liquidations_short"] = float(liq_data.get("shortLiquidation", 0))
                                logger.info(f"Fetched Coinglass liquidations for {symbol}")
            except Exception as e:
                logger.warning(f"Could not fetch Coinglass liquidations for {symbol}: {e}")
            
            # Fetch Top Traders L/S Ratio
            try:
                ls_url = f"https://open-api.coinglass.com/public/v2/long_short"
                params = {"symbol": cg_symbol, "time_type": "h1"}
                
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession() as session:
                    async with session.get(ls_url, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("success") and data.get("data"):
                                ls_data = data["data"]
                                # Calculate ratio from percentages
                                long_pct = float(ls_data.get("longPercent", 50))
                                short_pct = float(ls_data.get("shortPercent", 50))
                                if short_pct > 0:
                                    result["top_traders_ratio"] = long_pct / short_pct
                                else:
                                    result["top_traders_ratio"] = 2.0  # Default bullish
                                logger.info(f"Fetched Coinglass top traders for {symbol}: {result['top_traders_ratio']:.2f}")
            except Exception as e:
                logger.warning(f"Could not fetch Coinglass top traders for {symbol}: {e}")
            
            return result if result else None
            
        except Exception as e:
            logger.error(f"Error getting Coinglass data for {symbol}: {e}")
            return None
    
    async def get_crypto_news_sentiment(self, symbol: str) -> Optional[Dict]:
        """
        Получение новостей и сентимента с CryptoPanic.
        
        Endpoint: https://cryptopanic.com/api/v1/posts/?auth_token=FREE&currencies=BTC&filter=hot
        
        Для бесплатного API можно использовать публичный endpoint или парсить.
        
        Returns:
            {
                "news_count": 10,
                "bullish_count": 6,
                "bearish_count": 2,
                "neutral_count": 2,
                "sentiment_score": 0.6,  # (bullish - bearish) / total
                "important_news": ["Bitcoin ETF approved", ...],
            }
        """
        try:
            # Use free public endpoint (no auth required for some endpoints)
            url = "https://cryptopanic.com/api/free/v1/posts/"
            params = {
                "currencies": symbol.upper(),
                "filter": "hot",
                "public": "true"
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])
                        
                        if not results:
                            logger.info(f"No CryptoPanic news found for {symbol}")
                            return None
                        
                        news_count = len(results)
                        bullish_count = 0
                        bearish_count = 0
                        neutral_count = 0
                        important_news = []
                        
                        for post in results[:10]:  # Analyze top 10
                            title = post.get("title", "")
                            votes = post.get("votes", {})
                            
                            # Analyze sentiment from votes
                            positive = votes.get("positive", 0)
                            negative = votes.get("negative", 0)
                            important = votes.get("important", 0)
                            
                            if positive > negative:
                                bullish_count += 1
                            elif negative > positive:
                                bearish_count += 1
                            else:
                                neutral_count += 1
                            
                            if important > 5:
                                important_news.append(title[:50])
                        
                        # Calculate sentiment score
                        total = bullish_count + bearish_count + neutral_count
                        sentiment_score = (bullish_count - bearish_count) / total if total > 0 else 0
                        
                        result = {
                            "news_count": news_count,
                            "bullish_count": bullish_count,
                            "bearish_count": bearish_count,
                            "neutral_count": neutral_count,
                            "sentiment_score": round(sentiment_score, 2),
                            "important_news": important_news[:3]
                        }
                        
                        logger.info(f"Fetched CryptoPanic news for {symbol}: sentiment {sentiment_score:.2f}")
                        return result
                    else:
                        logger.warning(f"Failed to fetch CryptoPanic news for {symbol}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting CryptoPanic news for {symbol}: {e}")
            return None
    
    async def get_tradingview_rating(self, symbol: str) -> Optional[Dict]:
        """
        Получение технического рейтинга TradingView.
        
        Использовать библиотеку tradingview_ta.
        
        Returns:
            {
                "recommendation": "STRONG_BUY",  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
                "buy_signals": 15,
                "sell_signals": 3,
                "neutral_signals": 8,
                "moving_averages": "BUY",
                "oscillators": "BUY",
            }
        """
        try:
            from tradingview_ta import TA_Handler, Interval
            
            bybit_symbol = self.bybit_mapping.get(symbol, f"{symbol}USDT")
            
            handler = TA_Handler(
                symbol=bybit_symbol,
                exchange="BYBIT",
                screener="crypto",
                interval=Interval.INTERVAL_1_HOUR
            )
            
            analysis = handler.get_analysis()
            
            result = {
                "recommendation": analysis.summary["RECOMMENDATION"],
                "buy_signals": analysis.summary["BUY"],
                "sell_signals": analysis.summary["SELL"],
                "neutral_signals": analysis.summary["NEUTRAL"],
                "moving_averages": analysis.moving_averages["RECOMMENDATION"],
                "oscillators": analysis.oscillators["RECOMMENDATION"],
            }
            
            logger.info(f"Fetched TradingView rating for {symbol}: {result['recommendation']}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting TradingView rating for {symbol}: {e}")
            return None
    
    async def get_whale_alert_transactions(self, symbol: str) -> Optional[Dict]:
        """
        Получение крупных транзакций с Whale Alert.
        
        Бесплатный endpoint (ограниченный) или mock data для демонстрации.
        
        Returns:
            {
                "transactions_1h": 5,
                "to_exchange_usd": 45000000,  # На биржи (продажа)
                "from_exchange_usd": 120000000,  # С бирж (накопление)
                "unknown_usd": 30000000,
                "net_flow": 75000000,  # from_exchange - to_exchange (положительный = бычье)
            }
        """
        try:
            # Note: Whale Alert API requires API key for production use
            # Using mock/simulated data based on our existing whale tracker data
            
            # Get whale data from our tracker
            whale_data = await self.get_whale_data(symbol)
            
            if not whale_data:
                return None
            
            # Simulate Whale Alert style data from our whale tracker
            deposits = whale_data.get("deposits", 0)
            withdrawals = whale_data.get("withdrawals", 0)
            total_volume = whale_data.get("total_volume_usd", 0)
            
            # Estimate flows
            to_exchange_usd = (deposits / (deposits + withdrawals + 0.001)) * total_volume if (deposits + withdrawals) > 0 else 0
            from_exchange_usd = (withdrawals / (deposits + withdrawals + 0.001)) * total_volume if (deposits + withdrawals) > 0 else 0
            unknown_usd = total_volume * 0.1  # Assume 10% unknown
            
            net_flow = from_exchange_usd - to_exchange_usd
            
            result = {
                "transactions_1h": whale_data.get("transaction_count", 0),
                "to_exchange_usd": round(to_exchange_usd, 0),
                "from_exchange_usd": round(from_exchange_usd, 0),
                "unknown_usd": round(unknown_usd, 0),
                "net_flow": round(net_flow, 0)
            }
            
            logger.info(f"Calculated Whale Alert transactions for {symbol}: net_flow ${net_flow:,.0f}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting Whale Alert transactions for {symbol}: {e}")
            return None
    
    async def get_lunarcrush_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение социальных метрик с LunarCrush.
        
        Endpoint: https://lunarcrush.com/api3/coins/{symbol}
        
        Returns:
            {
                "galaxy_score": 72,  # 0-100, общий рейтинг
                "social_volume": 15000,  # упоминания
                "social_volume_change": 15.5,  # % изменение
                "sentiment": 0.65,  # -1 to 1
                "social_dominance": 45.2,  # % от всего крипто
            }
        """
        try:
            # LunarCrush API v3 (free tier available)
            coin_symbol = symbol.lower()
            url = f"https://lunarcrush.com/api3/coins/{coin_symbol}"
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    # Check if request was successful before using mock data
                    if response.status != 200:
                        logger.warning(f"Failed to fetch LunarCrush data for {symbol}: {response.status}")
                        return None
                    
                    # TODO: Parse actual LunarCrush API response structure
                    # Currently using mock data - implement proper parsing when API structure is confirmed
                    # For now, only return data if the API is accessible
                    data = await response.json()
                    
                    # Use mock data based on symbol (to be replaced with actual parsing)
                    if symbol == "BTC":
                        galaxy_score = 75
                        social_volume = 18000
                        social_volume_change = 5.5
                        sentiment = 0.65
                        social_dominance = 45.0
                    elif symbol == "ETH":
                        galaxy_score = 70
                        social_volume = 12000
                        social_volume_change = 3.2
                        sentiment = 0.60
                        social_dominance = 25.0
                    else:
                        return None
                    
                    result = {
                        "galaxy_score": galaxy_score,
                        "social_volume": social_volume,
                        "social_volume_change": social_volume_change,
                        "sentiment": sentiment,
                        "social_dominance": social_dominance
                    }
                    
                    logger.info(f"Fetched LunarCrush data for {symbol}: galaxy_score {galaxy_score}")
                    return result
        except Exception as e:
            logger.error(f"Error getting LunarCrush data for {symbol}: {e}")
            return None
    
    async def calculate_short_term_indicators(self, symbol: str, ohlcv_5m: Optional[List], 
                                             ohlcv_15m: Optional[List]) -> Optional[Dict]:
        """
        Расчёт краткосрочных индикаторов на основе 5м и 15м данных.
        
        Args:
            symbol: BTC или ETH
            ohlcv_5m: Свечи 5 минут
            ohlcv_15m: Свечи 15 минут
        
        Returns:
            Dict: {
                "rsi_5m": 65.5,
                "rsi_15m": 58.2,
                "ema_9_5m": 97500,
                "ema_21_5m": 97200,
                "ema_crossover": "bullish",  # bullish/bearish/neutral
                "price_10min_ago": 97000,
                "current_price": 97500
            }
        """
        try:
            result = {}
            
            # RSI 5m
            if ohlcv_5m and len(ohlcv_5m) >= 14:
                closes_5m = [c["close"] for c in ohlcv_5m]
                rsi_5m = calculate_rsi(closes_5m, period=14)
                if rsi_5m:
                    result["rsi_5m"] = rsi_5m.value
            
            # RSI 15m
            if ohlcv_15m and len(ohlcv_15m) >= 14:
                closes_15m = [c["close"] for c in ohlcv_15m]
                rsi_15m = calculate_rsi(closes_15m, period=14)
                if rsi_15m:
                    result["rsi_15m"] = rsi_15m.value
            
            # EMA crossover on 5m
            if ohlcv_5m and len(ohlcv_5m) >= 21:
                closes_5m = [c["close"] for c in ohlcv_5m]
                
                # Calculate EMA 9 and 21
                closes_array = np.array(closes_5m)
                
                # EMA formula: EMA = price * k + EMA(prev) * (1-k), where k = 2/(N+1)
                ema_9 = closes_array[0]
                k_9 = 2 / (9 + 1)
                for price in closes_array:
                    ema_9 = price * k_9 + ema_9 * (1 - k_9)
                
                ema_21 = closes_array[0]
                k_21 = 2 / (21 + 1)
                for price in closes_array:
                    ema_21 = price * k_21 + ema_21 * (1 - k_21)
                
                result["ema_9_5m"] = round(ema_9, 2)
                result["ema_21_5m"] = round(ema_21, 2)
                
                # Crossover detection with threshold to avoid false signals
                threshold = self.EMA_CROSSOVER_THRESHOLD
                if ema_9 > ema_21 * (1 + threshold):
                    result["ema_crossover"] = "bullish"
                elif ema_9 < ema_21 * (1 - threshold):
                    result["ema_crossover"] = "bearish"
                else:
                    result["ema_crossover"] = "neutral"
            
            # Price 10 minutes ago (index -3 represents 2 candles back = 10 min on 5m chart)
            if ohlcv_5m and len(ohlcv_5m) >= 3:
                result["price_10min_ago"] = ohlcv_5m[-3]["close"]
                result["current_price"] = ohlcv_5m[0]["close"]
            
            logger.info(f"Calculated short-term indicators for {symbol}")
            return result if result else None
            
        except Exception as e:
            logger.error(f"Error calculating short-term indicators for {symbol}: {e}")
            return None
    
    async def calculate_advanced_indicators(self, bybit_symbol: str, ohlcv_data: Optional[List]) -> Optional[Dict]:
        """
        Расчёт продвинутых технических индикаторов.
        
        Args:
            bybit_symbol: Символ для Bybit (e.g., "BTCUSDT")
            ohlcv_data: OHLCV данные
            
        Returns:
            Dict с продвинутыми индикаторами или None
        """
        try:
            # Fetch 4h candles for advanced analysis
            candles_4h = await self.multi_timeframe_analyzer.fetch_candles(
                bybit_symbol, "4h", limit=100
            )
            
            if not candles_4h or len(candles_4h) < 52:
                logger.warning(f"Insufficient 4h candle data for advanced indicators")
                return None
            
            # Extract price arrays
            opens = [c["open"] for c in candles_4h]
            highs = [c["high"] for c in candles_4h]
            lows = [c["low"] for c in candles_4h]
            closes = [c["close"] for c in candles_4h]
            volumes = [c["volume"] for c in candles_4h]
            
            result = {}
            
            # Calculate Ichimoku Cloud
            ichimoku = calculate_ichimoku(highs, lows, closes, closes[-1])
            if ichimoku:
                result["ichimoku"] = {
                    "tenkan_sen": ichimoku.tenkan_sen,
                    "kijun_sen": ichimoku.kijun_sen,
                    "senkou_span_a": ichimoku.senkou_span_a,
                    "senkou_span_b": ichimoku.senkou_span_b,
                    "cloud_color": ichimoku.cloud_color,
                    "signal": ichimoku.signal
                }
            
            # Calculate Volume Profile
            volume_profile = calculate_volume_profile(closes, volumes)
            if volume_profile:
                result["volume_profile"] = {
                    "poc": volume_profile.poc,
                    "vah": volume_profile.vah,
                    "val": volume_profile.val,
                    "position": volume_profile.get_position(closes[-1])
                }
            
            # Calculate CVD
            cvd = calculate_cvd(opens, closes, volumes)
            if cvd:
                result["cvd"] = {
                    "value": cvd.value,
                    "trend": cvd.trend,
                    "signal": cvd.signal
                }
            
            # Calculate Market Structure
            market_structure = calculate_market_structure(highs, lows)
            if market_structure:
                result["market_structure"] = {
                    "structure": market_structure.structure,
                    "signal": market_structure.signal
                }
            
            # Find Order Blocks
            order_blocks = find_order_blocks(opens, highs, lows, closes)
            if order_blocks:
                # Get most recent order block
                latest_ob = order_blocks[-1] if order_blocks else None
                if latest_ob:
                    result["order_block"] = {
                        "type": latest_ob.block_type,
                        "price_high": latest_ob.price_high,
                        "price_low": latest_ob.price_low,
                        "signal": latest_ob.signal
                    }
            
            # Find FVGs
            fvgs = find_fvg(highs, lows)
            if fvgs:
                # Get most recent FVG
                latest_fvg = fvgs[-1] if fvgs else None
                if latest_fvg:
                    result["fvg"] = {
                        "type": latest_fvg.gap_type,
                        "gap_high": latest_fvg.gap_high,
                        "gap_low": latest_fvg.gap_low,
                        "signal": latest_fvg.signal
                    }
            
            logger.info(f"Calculated advanced indicators for {bybit_symbol}")
            return result if result else None
            
        except Exception as e:
            logger.error(f"Error calculating advanced indicators: {e}")
            return None
    
    def _calculate_short_term_trend_score(self, short_term_data: Dict) -> float:
        """
        Краткосрочный тренд на основе 5м/15м данных.
        
        Использует:
        - RSI 5м (oversold < 30, overbought > 70)
        - RSI 15м
        - EMA 9/21 crossover на 5м
        - Price momentum (цена сейчас vs 10 мин назад)
        
        Args:
            short_term_data: Краткосрочные индикаторы
        
        Returns: -10 to +10
        """
        if not short_term_data:
            return 0.0
        
        score = 0.0
        
        # RSI 5m score with enhanced extreme levels
        # RSI < 30 = перепродан = ЛОНГ, RSI > 70 = перекуплен = ШОРТ
        rsi_5m = short_term_data.get("rsi_5m")
        if rsi_5m:
            if rsi_5m < 20:
                score += 5  # Сильно перепродан = сильный ЛОНГ
            elif rsi_5m < 30:
                score += 3  # Перепродан = ЛОНГ
            elif rsi_5m > 80:
                score -= 5  # Сильно перекуплен = сильный ШОРТ
            elif rsi_5m > 70:
                score -= 3  # Перекуплен = ШОРТ
            else:
                # Gradient
                score += (50 - rsi_5m) / 20
        
        # RSI 15m score with enhanced extreme levels
        rsi_15m = short_term_data.get("rsi_15m")
        if rsi_15m:
            if rsi_15m < 20:
                score += 4  # Сильно перепродан = сильный ЛОНГ
            elif rsi_15m < 30:
                score += 2  # Перепродан = ЛОНГ
            elif rsi_15m > 80:
                score -= 4  # Сильно перекуплен = сильный ШОРТ
            elif rsi_15m > 70:
                score -= 2  # Перекуплен = ШОРТ
            else:
                score += (50 - rsi_15m) / 30
        
        # EMA crossover score (max ±3)
        ema_crossover = short_term_data.get("ema_crossover")
        if ema_crossover == "bullish":
            score += 3
        elif ema_crossover == "bearish":
            score -= 3
        
        # Price momentum score (max ±2)
        current_price = short_term_data.get("current_price")
        price_10min_ago = short_term_data.get("price_10min_ago")
        if current_price and price_10min_ago:
            price_change_pct = ((current_price - price_10min_ago) / price_10min_ago) * 100
            if price_change_pct > 0.5:
                score += 2
            elif price_change_pct < -0.5:
                score -= 2
            else:
                score += price_change_pct * 4  # Gradient
        
        return clamp(score, -10, 10)
    
    def _calculate_trades_flow_score(self, trades_flow: Optional[Dict]) -> float:
        """
        Score на основе потока сделок.
        
        - flow_ratio > 50 = +10 (экстремальные покупки)
        - flow_ratio > 10 = +9 (очень много покупок)
        - flow_ratio > 5 = +8 (много покупок)
        - flow_ratio > 1.5 = +5..+7 (покупки)
        - flow_ratio < 0.02 = -10 (экстремальные продажи)
        - flow_ratio < 0.1 = -9 (очень много продаж)
        - flow_ratio < 0.2 = -8 (много продаж)
        - flow_ratio < 0.67 = -5..-7 (продажи)
        - Градиент между ними
        
        Args:
            trades_flow: Данные о потоке сделок
        
        Returns: -10 to +10
        """
        if not trades_flow:
            return 0.0
        
        flow_ratio = trades_flow.get("flow_ratio", 1.0)
        
        # Экстремальные покупки
        if flow_ratio > 50:
            score = 10  # Аномально много покупок (как 122:1 в примере BTC)
        elif flow_ratio > 10:
            score = 9
        elif flow_ratio > 5:
            score = 8
        elif flow_ratio > self.TRADES_FLOW_BULLISH_THRESHOLD:
            # Много покупок (1.5 < flow_ratio <= 5)
            score = 7
        # Экстремальные продажи
        elif flow_ratio < 0.02:
            score = -10  # Аномально много продаж
        elif flow_ratio < 0.1:
            score = -9
        elif flow_ratio < 0.2:
            score = -8
        elif flow_ratio < self.TRADES_FLOW_BEARISH_THRESHOLD:
            # Много продаж (0.2 <= flow_ratio < 0.67)
            score = -7
        else:
            # Градиент между thresholds
            # Normalize to -10 to +10
            # flow_ratio: 0.67 -> -10, 1.0 -> 0, 1.5 -> +10
            if flow_ratio >= 1.0:
                bullish_range = self.TRADES_FLOW_BULLISH_THRESHOLD - 1.0
                score = ((flow_ratio - 1.0) / bullish_range) * 10
            else:
                score = ((flow_ratio - 1.0) / self.TRADES_FLOW_NEUTRAL_DIVISOR) * 10
        
        return clamp(score, -10, 10)
    
    def _calculate_liquidations_score(self, liquidations: Optional[Dict]) -> float:
        """
        Score на основе ликвидаций.
        
        - Много лонг ликвидаций = bearish (цена падает, лонги закрываются)
        - Много шорт ликвидаций = bullish (цена растёт, шорты закрываются)
        
        Args:
            liquidations: Данные о ликвидациях
        
        Returns: -10 to +10
        """
        if not liquidations:
            return 0.0
        
        sentiment = liquidations.get("sentiment", "neutral")
        net_liquidations = liquidations.get("net_liquidations", 0)
        
        if sentiment == "bearish":
            # Много лонг ликвидаций
            score = -8
        elif sentiment == "bullish":
            # Много шорт ликвидаций
            score = 8
        else:
            # Нейтрально
            score = 0
        
        return clamp(score, -10, 10)
    
    def _calculate_orderbook_delta_score(self, orderbook_delta: Optional[Dict]) -> float:
        """
        Score на основе изменения order book.
        
        - Bid wall растёт, Ask wall падает = bullish
        - Bid wall падает, Ask wall растёт = bearish
        
        Args:
            orderbook_delta: Изменение order book
        
        Returns: -10 to +10
        """
        if not orderbook_delta:
            return 0.0
        
        delta = orderbook_delta.get("delta", 0)
        
        # Delta > 10% = strong bullish
        # Delta < -10% = strong bearish
        if delta > 10:
            score = 10
        elif delta < -10:
            score = -10
        else:
            # Gradient
            score = delta
        
        return clamp(score, -10, 10)
    
    def _calculate_price_momentum_score(self, current_price: float, price_10min_ago: float) -> float:
        """
        Score на основе движения цены за 10 минут.
        
        - Рост > 0.5% = bullish
        - Падение > 0.5% = bearish
        
        Args:
            current_price: Текущая цена
            price_10min_ago: Цена 10 минут назад
        
        Returns: -10 to +10
        """
        if not current_price or not price_10min_ago:
            return 0.0
        
        price_change_pct = ((current_price - price_10min_ago) / price_10min_ago) * 100
        
        if price_change_pct > 0.5:
            # Strong bullish
            score = min(price_change_pct * 10, 10)
        elif price_change_pct < -0.5:
            # Strong bearish
            score = max(price_change_pct * 10, -10)
        else:
            # Gradient
            score = price_change_pct * 20
        
        return clamp(score, -10, 10)
    
    def _calculate_oi_change_score(self, oi_change: float, price_change: float) -> float:
        """
        Score на основе изменения Open Interest.
        
        Логика:
        - OI растёт + цена растёт = сильный бычий тренд (+10)
        - OI растёт + цена падает = накопление шортов (-5)
        - OI падает + цена растёт = слабый рост (-3)
        - OI падает + цена падает = капитуляция, возможно дно (+3)
        
        Returns: -10 to +10
        """
        if oi_change > 2:  # OI растёт
            if price_change > 0:
                return 10  # Сильный бычий тренд
            else:
                return -5  # Накопление шортов
        elif oi_change < -2:  # OI падает
            if price_change > 0:
                return -3  # Слабый рост
            else:
                return 3  # Капитуляция, возможно дно
        else:
            # Нейтрально
            return 0
    
    def _calculate_coinglass_liquidations_score(self, liq_long: float, liq_short: float) -> float:
        """
        Score на основе ликвидаций Coinglass (улучшенный).
        
        Логика:
        - Много лонг ликвидаций = цена падала, медвежье (-10)
        - Много шорт ликвидаций = цена росла, бычье (+10)
        - Баланс = нейтрально (0)
        
        Returns: -10 to +10
        """
        total = liq_long + liq_short
        if total == 0:
            return 0
        
        # Calculate ratio
        long_ratio = liq_long / total
        
        if long_ratio > 0.7:
            # Много лонг ликвидаций
            return -10
        elif long_ratio > 0.6:
            return -5
        elif long_ratio < 0.3:
            # Много шорт ликвидаций
            return 10
        elif long_ratio < 0.4:
            return 5
        else:
            # Баланс
            return 0
    
    def _calculate_top_traders_score(self, ratio: float) -> float:
        """
        Score на основе позиций топ трейдеров.
        
        Логика:
        - ratio > 2.0 = топы в лонгах, бычье (+8)
        - ratio > 1.5 = умеренно бычье (+4)
        - ratio < 0.67 = топы в шортах, медвежье (-8)
        - ratio < 0.5 = сильно медвежье (-10)
        
        Returns: -10 to +10
        """
        if ratio > 2.0:
            return 8
        elif ratio > 1.5:
            return 4
        elif ratio < 0.5:
            return -10
        elif ratio < 0.67:
            return -8
        else:
            # Градиент между 0.67 и 1.5
            return (ratio - 1.0) * 5
    
    def _calculate_news_sentiment_score(self, sentiment_data: Dict) -> float:
        """
        Score на основе новостного сентимента.
        
        Логика:
        - sentiment_score > 0.5 = очень бычьи новости (+10)
        - sentiment_score > 0.2 = бычьи новости (+5)
        - sentiment_score < -0.2 = медвежьи новости (-5)
        - sentiment_score < -0.5 = очень медвежьи (-10)
        
        Returns: -10 to +10
        """
        if not sentiment_data:
            return 0
        
        sentiment_score = sentiment_data.get("sentiment_score", 0)
        
        if sentiment_score > 0.5:
            return 10
        elif sentiment_score > 0.2:
            return 5
        elif sentiment_score < -0.5:
            return -10
        elif sentiment_score < -0.2:
            return -5
        else:
            # Градиент
            return sentiment_score * 10
    
    def _calculate_tradingview_score(self, tv_data: Dict) -> float:
        """
        Score на основе TradingView рейтинга.
        
        Логика:
        - STRONG_BUY = +10
        - BUY = +5
        - NEUTRAL = 0
        - SELL = -5
        - STRONG_SELL = -10
        
        Returns: -10 to +10
        """
        if not tv_data:
            return 0
        
        recommendation = tv_data.get("recommendation", "NEUTRAL")
        
        if recommendation == "STRONG_BUY":
            return 10
        elif recommendation == "BUY":
            return 5
        elif recommendation == "SELL":
            return -5
        elif recommendation == "STRONG_SELL":
            return -10
        else:
            return 0
    
    def _calculate_whale_alert_score(self, whale_data: Dict) -> float:
        """
        Score на основе Whale Alert транзакций.
        
        Логика:
        - net_flow > $50M = сильный вывод с бирж, бычье (+10)
        - net_flow > $20M = умеренный вывод (+5)
        - net_flow < -$20M = приток на биржи, медвежье (-5)
        - net_flow < -$50M = сильный приток, очень медвежье (-10)
        
        Returns: -10 to +10
        """
        if not whale_data:
            return 0
        
        net_flow = whale_data.get("net_flow", 0)
        
        if net_flow > 50_000_000:
            return 10
        elif net_flow > 20_000_000:
            return 5
        elif net_flow < -50_000_000:
            return -10
        elif net_flow < -20_000_000:
            return -5
        else:
            # Градиент
            return (net_flow / 10_000_000)
    
    def _calculate_social_score(self, social_data: Dict) -> float:
        """
        Score на основе социальных метрик.
        
        Логика:
        - galaxy_score > 70 + sentiment > 0.5 = очень бычье (+10)
        - galaxy_score > 60 + sentiment > 0.3 = бычье (+5)
        - galaxy_score < 40 + sentiment < -0.3 = медвежье (-5)
        - galaxy_score < 30 + sentiment < -0.5 = очень медвежье (-10)
        
        Returns: -10 to +10
        """
        if not social_data:
            return 0
        
        galaxy_score = social_data.get("galaxy_score", 50)
        sentiment = social_data.get("sentiment", 0)
        
        if galaxy_score > 70 and sentiment > 0.5:
            return 10
        elif galaxy_score > 60 and sentiment > 0.3:
            return 5
        elif galaxy_score < 30 and sentiment < -0.5:
            return -10
        elif galaxy_score < 40 and sentiment < -0.3:
            return -5
        else:
            # Комбинированный градиент
            score = ((galaxy_score - 50) / 10) + (sentiment * 5)
            return clamp(score, -10, 10)
    
    
    def _calculate_whale_score(self, whale_data: Dict, exchange_flows: Optional[Dict] = None) -> float:
        """
        Calculate whale score (-10 to +10).
        
        Logic:
        - Withdrawals from exchanges > Deposits to exchanges = POSITIVE score (bullish)
        - Deposits to exchanges > Withdrawals from exchanges = NEGATIVE score (bearish)
        
        Args:
            whale_data: Whale transaction data
            exchange_flows: Exchange flow data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Whale transactions score (max ±6)
        # Positive when withdrawals > deposits (whales accumulating off-exchange = bullish)
        # Negative when deposits > withdrawals (whales sending to exchanges = bearish)
        total_txs = whale_data["withdrawals"] + whale_data["deposits"]
        if total_txs > 0:
            ratio = (whale_data["withdrawals"] - whale_data["deposits"]) / total_txs
            score += ratio * 6
        
        # Exchange flows score (max ±4)
        # net_flow_usd = outflow_volume - inflow_volume
        # Positive net_flow (outflows > inflows) = bullish
        # Negative net_flow (inflows > outflows) = bearish
        if exchange_flows:
            net_flow = exchange_flows.get("net_flow_usd", 0)
            total_flow = exchange_flows.get("inflow_volume_usd", 0) + exchange_flows.get("outflow_volume_usd", 0)
            if total_flow > 0:
                flow_ratio = net_flow / total_flow
                score += flow_ratio * 4
        
        return clamp(score, -10, 10)
    
    def _calculate_trend_score(self, technical_data: Dict) -> float:
        """
        Calculate trend score (-10 to +10).
        Combines RSI, MACD, MA Crossover, RSI Divergence, ADX.
        
        Args:
            technical_data: Technical indicator data
            
        Returns:
            Score from -10 to +10 (clamped)
        """
        score = 0.0
        
        # RSI (max ±4)
        if "rsi" in technical_data:
            rsi_value = technical_data["rsi"]["value"]
            if rsi_value < 30:
                score += 4
            elif rsi_value > 70:
                score -= 4
            else:
                score += (50 - rsi_value) / 20 * 2
        
        # MACD (max ±3)
        if "macd" in technical_data:
            if technical_data["macd"]["signal"] == "bullish":
                score += 3
            elif technical_data["macd"]["signal"] == "bearish":
                score -= 3
        
        # MA Crossover (max ±3)
        if "ma_crossover" in technical_data:
            if technical_data["ma_crossover"]["crossover"] == "golden_cross":
                score += 3
            elif technical_data["ma_crossover"]["crossover"] == "death_cross":
                score -= 3
            elif technical_data["ma_crossover"]["trend"] == "bullish":
                score += 1
            elif technical_data["ma_crossover"]["trend"] == "bearish":
                score -= 1
        
        # RSI Divergence (NEW - scaled to fit within -10/+10)
        divergence_adjustment = 0.0
        if "rsi_divergence" in technical_data:
            div_type = technical_data["rsi_divergence"]["type"]
            if div_type == "bullish":
                divergence_adjustment = 5  # +5 for bullish divergence
            elif div_type == "bearish":
                divergence_adjustment = -5  # -5 for bearish divergence
        
        # ADX Trend Strength (NEW - modifies confidence)
        # ADX < 20: reduce score by 20%, ADX > 40: increase score by 20%
        adx_multiplier = 1.0
        if "adx" in technical_data:
            adx_value = technical_data["adx"]["value"]
            if adx_value < 20:
                adx_multiplier = 0.8  # Reduce by 20% for weak trend
            elif adx_value > 40:
                adx_multiplier = 1.2  # Increase by 20% for strong trend
        
        # Apply ADX multiplier to base score, then add divergence
        score = (score * adx_multiplier) + divergence_adjustment
        
        return clamp(score, -10, 10)  # Clamp to proper range
    
    def _calculate_momentum_score(self, technical_data: Dict) -> float:
        """
        Calculate momentum score (-10 to +10).
        Combines Stochastic RSI, MFI, ROC, Williams %R.
        
        Args:
            technical_data: Technical indicator data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Stochastic RSI (max ±3)
        if "stoch_rsi" in technical_data:
            signal = technical_data["stoch_rsi"]["signal"]
            if signal == "oversold":
                score += 3
            elif signal == "overbought":
                score -= 3
            elif signal == "bullish":
                score += 1.5
            elif signal == "bearish":
                score -= 1.5
        
        # MFI (max ±2.5)
        if "mfi" in technical_data:
            signal = technical_data["mfi"]["signal"]
            if signal == "oversold":
                score += 2.5
            elif signal == "overbought":
                score -= 2.5
        
        # ROC (max ±2.5)
        if "roc" in technical_data:
            momentum = technical_data["roc"]["momentum"]
            if momentum == "strong_up":
                score += 2.5
            elif momentum == "up":
                score += 1.5
            elif momentum == "strong_down":
                score -= 2.5
            elif momentum == "down":
                score -= 1.5
        
        # Williams %R (max ±2)
        if "williams_r" in technical_data:
            signal = technical_data["williams_r"]["signal"]
            if signal == "oversold":
                score += 2
            elif signal == "overbought":
                score -= 2
        
        return clamp(score, -10, 10)
    
    def _calculate_volatility_score(self, technical_data: Dict) -> float:
        """
        Calculate volatility score (-10 to +10).
        Combines Bollinger Bands, ATR, Keltner Channels.
        
        Args:
            technical_data: Technical indicator data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Bollinger Bands (max ±4)
        if "bollinger_bands" in technical_data:
            position = technical_data["bollinger_bands"]["position"]
            if position == "below_lower":
                score += 4
            elif position == "above_upper":
                score -= 4
            elif position == "lower_half":
                score += 1
            elif position == "upper_half":
                score -= 1
        
        # ATR (max ±3)
        if "atr" in technical_data:
            volatility = technical_data["atr"]["volatility"]
            if volatility in ["high", "extreme"]:
                score -= 2  # High volatility is risky
        
        # Keltner Channels (max ±3)
        if "keltner_channels" in technical_data:
            position = technical_data["keltner_channels"]["position"]
            if position == "below":
                score += 3
            elif position == "above":
                score -= 3
        
        return clamp(score, -10, 10)
    
    def _calculate_volume_score(self, technical_data: Dict, ohlcv_data: Optional[List] = None) -> float:
        """
        Calculate volume score (-10 to +10).
        Combines OBV, VWAP, Volume SMA, Volume Spike.
        
        Args:
            technical_data: Technical indicator data
            ohlcv_data: OHLCV candle data
            
        Returns:
            Score from -10 to +10 (clamped)
        """
        score = 0.0
        
        # OBV (max ±4)
        if "obv" in technical_data:
            trend = technical_data["obv"]["trend"]
            if trend == "rising":
                score += 4
            elif trend == "falling":
                score -= 4
        
        # VWAP (max ±3)
        if "vwap" in technical_data:
            position = technical_data["vwap"]["position"]
            deviation = technical_data["vwap"]["deviation_percent"]
            if position == "above":
                score += min(3, deviation / 2)
            else:
                score -= min(3, abs(deviation) / 2)
        
        # Volume SMA (max ±3)
        if "volume_sma" in technical_data:
            status = technical_data["volume_sma"]["status"]
            if status == "high":
                score += 3
            elif status == "low":
                score -= 2
        
        # Volume Spike (NEW - scaled to fit within -10/+10)
        if "volume_spike" in technical_data:
            is_spike = technical_data["volume_spike"]["is_spike"]
            spike_pct = technical_data["volume_spike"]["spike_percentage"]
            if is_spike and spike_pct > 50:  # Only if spike > 50%
                # Scale from +3 to +5 based on spike size (reduced from original)
                # spike_pct of 50-100% = +3, 100-200% = +4, 200%+ = +5
                spike_score = min(5, 3 + (spike_pct / 80))  # Scaling formula
                score += spike_score
        
        return clamp(score, -10, 10)  # Clamp to proper range
    
    def _calculate_market_score(self, market_data: Dict) -> float:
        """
        Calculate market score (-10 to +10).
        Based on price change and volume.
        
        Args:
            market_data: Market data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Price change (max ±7)
        change_24h = market_data.get("change_24h", 0)
        score += min(max(change_24h * 0.7, -7), 7)
        
        # Volume (max ±3)
        volume_24h = market_data.get("volume_24h", 0)
        if volume_24h > self.HIGH_VOLUME_THRESHOLD:
            score += 3
        elif volume_24h < self.HIGH_VOLUME_THRESHOLD * 0.3:
            score -= 2
        
        return clamp(score, -10, 10)
    
    def _calculate_orderbook_score(self, order_book: Optional[Dict]) -> float:
        """
        Calculate order book score (-10 to +10).
        Based on bid/ask imbalance and spread.
        
        Args:
            order_book: Order book data
            
        Returns:
            Score from -10 to +10
        """
        if not order_book:
            return 0.0
        
        score = 0.0
        
        # Imbalance (max ±7)
        imbalance = order_book.get("imbalance", 0)
        score += imbalance * 7
        
        # Spread (max ±3)
        spread = order_book.get("spread", 0)
        if spread < 0.01:  # Tight spread
            score += 2
        elif spread > 0.05:  # Wide spread
            score -= 3
        
        return clamp(score, -10, 10)
    
    def _calculate_derivatives_score(self, futures_data: Optional[Dict], funding_rate: Optional[Dict]) -> float:
        """
        Calculate derivatives score (-10 to +10).
        Based on Open Interest, Long/Short ratio, Funding Rate.
        
        Args:
            futures_data: Futures data
            funding_rate: Funding rate data
            
        Returns:
            Score from -10 to +10
        """
        score = 0.0
        
        # Long/Short Ratio (max ±5)
        if futures_data:
            ls_ratio = futures_data.get("long_short_ratio", 1.0)
            if ls_ratio > 1.5:
                score += 4
            elif ls_ratio > 1.2:
                score += 2
            elif ls_ratio < 0.7:
                score -= 4
            elif ls_ratio < 0.9:
                score -= 2
        
        # Funding Rate (max ±5)
        if funding_rate:
            rate_percent = funding_rate.get("rate_percent", 0)
            if rate_percent < -0.01:
                score += 5
            elif rate_percent > 0.05:
                score -= 5
            else:
                # Gradient
                if rate_percent < 0.02:
                    score += (0.02 - rate_percent) / 0.03 * 3
                else:
                    score -= (rate_percent - 0.02) / 0.03 * 3
        
        return clamp(score, -10, 10)
    
    def _calculate_onchain_score(self, onchain_data: Optional[Dict]) -> float:
        """
        Calculate on-chain score (-10 to +10).
        Based on mempool and hashrate.
        
        Args:
            onchain_data: On-chain data
            
        Returns:
            Score from -10 to +10
        """
        if not onchain_data:
            return 0.0
        
        score = 0.0
        
        # Mempool status (max ±5)
        mempool_status = onchain_data.get("mempool_status", "unknown")
        if mempool_status == "low":
            score += 3  # Low congestion = bullish
        elif mempool_status == "congested":
            score -= 5  # High congestion = bearish
        
        # Hashrate (max ±5)
        # Increasing hashrate is bullish for BTC
        # This would require historical data, so we'll skip for now
        
        return clamp(score, -10, 10)
    
    def _calculate_sentiment_score(self, fear_greed: Optional[Dict]) -> float:
        """
        Calculate sentiment score (-10 to +10).
        Based on Fear & Greed Index.
        
        Args:
            fear_greed: Fear & Greed data
            
        Returns:
            Score from -10 to +10
        """
        if not fear_greed:
            return 0.0
        
        fg_value = fear_greed.get("value", 50)
        
        # Extreme Fear = Buy, Extreme Greed = Sell
        if fg_value < 25:
            return 10
        elif fg_value > 75:
            return -10
        else:
            # Gradient
            return (50 - fg_value) / 5
    
    def _calculate_whale_accumulation_score(self, accumulation_data: Optional[Dict]) -> float:
        """
        Calculate score based on accumulation/distribution phase.
        
        Args:
            accumulation_data: Accumulation/distribution analysis data
            
        Returns:
            Score from -10 to +10
        """
        if not accumulation_data:
            return 0.0
        
        phase = accumulation_data.get("phase", "neutral")
        confidence = accumulation_data.get("confidence", 0) / 100  # 0-1 range
        
        if phase == "accumulation":
            # Accumulation is bullish
            return 10 * confidence
        elif phase == "distribution":
            # Distribution is bearish
            return -10 * confidence
        else:
            return 0.0
    
    def _calculate_exchange_flow_detailed_score(self, exchange_flows_detailed: Optional[Dict]) -> float:
        """
        Calculate score based on detailed per-exchange flows.
        
        Args:
            exchange_flows_detailed: Detailed exchange flow data
            
        Returns:
            Score from -10 to +10
        """
        if not exchange_flows_detailed:
            return 0.0
        
        total_net = exchange_flows_detailed.get("total_net", 0)
        
        # Negative net (outflows > inflows) = bullish (hodling)
        # Positive net (inflows > outflows) = bearish (selling)
        
        # Normalize based on $50M threshold
        if total_net < -50_000_000:
            return 10  # Strong outflow = very bullish
        elif total_net < -10_000_000:
            return 5  # Moderate outflow = bullish
        elif total_net > 50_000_000:
            return -10  # Strong inflow = very bearish
        elif total_net > 10_000_000:
            return -5  # Moderate inflow = bearish
        else:
            # Linear interpolation for intermediate values
            return -(total_net / 10_000_000)
    
    def _calculate_stablecoin_flow_score(self, stablecoin_flows: Optional[Dict]) -> float:
        """
        Calculate score based on stablecoin flows to exchanges.
        
        Args:
            stablecoin_flows: Stablecoin flow data
            
        Returns:
            Score from -10 to +10
        """
        if not stablecoin_flows:
            return 0.0
        
        total_inflow = stablecoin_flows.get("total_inflow", 0)
        
        # Positive inflow = stablecoins to exchanges = buying power = bullish
        # Negative inflow = stablecoins leaving = no buying power = bearish
        
        # Normalize based on $100M threshold
        if total_inflow > 100_000_000:
            return 10  # Strong inflow = very bullish
        elif total_inflow > 50_000_000:
            return 5  # Moderate inflow = bullish
        elif total_inflow < -100_000_000:
            return -10  # Strong outflow = very bearish
        elif total_inflow < -50_000_000:
            return -5  # Moderate outflow = bearish
        else:
            # Linear interpolation
            return total_inflow / 20_000_000
    
    def _calculate_oi_price_correlation_score(self, oi_correlation: Optional[Dict]) -> float:
        """
        Calculate score based on OI/Price correlation analysis.
        
        Args:
            oi_correlation: OI/Price correlation data
            
        Returns:
            Score from -10 to +10
        """
        if not oi_correlation:
            return 0.0
        
        signal = oi_correlation.get("signal", "neutral")
        correlation = oi_correlation.get("correlation", "neutral")
        
        # Strong signals
        if signal == "bullish" and correlation == "bullish":
            return 10
        elif signal == "bearish" and correlation == "bearish":
            return -10
        # Moderate signals
        elif signal == "bullish":
            return 5
        elif signal == "bearish":
            return -5
        else:
            return 0.0
    
    def _calculate_liquidation_levels_score(self, liquidation_levels: Optional[Dict]) -> float:
        """
        Calculate score based on liquidation level clustering.
        
        Args:
            liquidation_levels: Liquidation levels data
            
        Returns:
            Score from -10 to +10
        """
        if not liquidation_levels:
            return 0.0
        
        signal = liquidation_levels.get("signal", "neutral")
        
        if signal == "bullish":
            return 7  # Price close to hunting shorts
        elif signal == "bearish":
            return -7  # Price close to hunting longs
        else:
            return 0.0
    
    def _calculate_ls_ratio_detailed_score(self, ls_ratio_data: Optional[Dict]) -> float:
        """
        Calculate score based on multi-exchange L/S ratios.
        
        Args:
            ls_ratio_data: Long/Short ratio data
            
        Returns:
            Score from -10 to +10 with gradual scaling to prevent over-dominance
        """
        if not ls_ratio_data:
            return 0.0
        
        avg_ratio = ls_ratio_data.get("average_ratio", 1.0)
        
        # Gradual L/S ratio influence with maximum ±10 for extreme values
        # After weighting (1.5x) and capping, max contribution is ±15
        # High ratio (>2.5) = too many longs = bearish (reversal risk)
        # Low ratio (<0.4) = too many shorts = bullish (reversal risk)
        # Moderate ranges provide smaller adjustments
        
        if avg_ratio > 2.5:
            return -10  # Extreme bullish crowd = strong reversal down
        elif avg_ratio > 2.0:
            return -7  # Very many longs
        elif avg_ratio > 1.5:
            return -3  # Many longs
        elif avg_ratio < 0.4:
            return 10  # Extreme bearish crowd = strong reversal up
        elif avg_ratio < 0.5:
            return 7  # Very many shorts
        elif avg_ratio < 0.7:
            return 3  # Many shorts
        else:
            return 0.0  # Neutral zone (0.7 - 1.5)
    
    def _calculate_funding_trend_score(self, funding_history: Optional[Dict]) -> float:
        """
        Calculate score based on funding rate trend.
        
        Args:
            funding_history: Funding rate history data
            
        Returns:
            Score from -10 to +10
        """
        if not funding_history:
            return 0.0
        
        extreme = funding_history.get("extreme", False)
        trend = funding_history.get("trend", "stable")
        current = funding_history.get("current", 0)
        
        # Extreme rates indicate reversal risk
        if extreme:
            if current > 0.1:
                return -10  # Extreme positive = too bullish = bearish signal
            elif current < -0.1:
                return 10  # Extreme negative = too bearish = bullish signal
        
        # Trend analysis
        if trend == "rising" and current > 0.03:
            return -5  # Rising bullish sentiment = reversal risk
        elif trend == "falling" and current < -0.03:
            return 5  # Rising bearish sentiment = reversal risk
        else:
            return 0.0
    
    def _calculate_basis_score(self, basis_data: Optional[Dict]) -> float:
        """
        Calculate score based on futures/spot basis.
        
        Args:
            basis_data: Basis (futures-spot spread) data
            
        Returns:
            Score from -10 to +10
        """
        if not basis_data:
            return 0.0
        
        basis_type = basis_data.get("basis_type", "neutral")
        basis_value = basis_data.get("basis", 0)
        
        # Contango (futures > spot) = bullish sentiment
        # Backwardation (futures < spot) = bearish sentiment
        
        if basis_type == "contango":
            # Positive basis indicates bullish sentiment
            if basis_value > 0.5:
                return 8  # Strong contango
            else:
                return 4  # Moderate contango
        elif basis_type == "backwardation":
            # Negative basis indicates bearish sentiment
            if basis_value < -0.5:
                return -8  # Strong backwardation
            else:
                return -4  # Moderate backwardation
        else:
            return 0.0
    
    def _clamp_block_score(self, score: float, factors: int, multiplier: float = None) -> float:
        """
        Helper method to normalize and clamp block scores to [-10, +10] range.
        
        Args:
            score: Raw accumulated score
            factors: Number of factors that contributed to the score
            multiplier: Scaling multiplier (defaults to BLOCK_SCORE_MULTIPLIER)
            
        Returns:
            Clamped score in range [-10, +10]
        """
        if factors == 0:
            return 0.0
        
        if multiplier is None:
            multiplier = self.BLOCK_SCORE_MULTIPLIER
        
        normalized_score = score / factors * multiplier
        return max(-10, min(10, normalized_score))

    def _cap_factor_contribution(self, raw_score: float, weight: float) -> float:
        """
        Cap individual factor contribution to prevent any single factor from dominating.
        
        Args:
            raw_score: Raw score from factor (-10 to +10)
            weight: Weight to apply to the score
            
        Returns:
            Capped weighted contribution (±MAX_SINGLE_FACTOR_SCORE)
        """
        weighted_score = raw_score * weight
        return max(-self.MAX_SINGLE_FACTOR_SCORE, min(self.MAX_SINGLE_FACTOR_SCORE, weighted_score))

    def apply_total_score_limit(self, score: float) -> float:
        """
        Применить ограничение на итоговый score.
        
        Args:
            score: Итоговый score (любой диапазон)
            
        Returns:
            Ограниченный score (±MAX_TOTAL_SCORE)
        """
        return max(-self.MAX_TOTAL_SCORE, min(self.MAX_TOTAL_SCORE, score))

    def calculate_realistic_probability(self, score: float, factors_count: int, max_factors: int = 30) -> int:
        """
        Рассчитать реалистичную вероятность с консервативной шкалой.
        
        Реалистичная формула вероятности:
        - Учитывает полноту данных (коэффициент 0.5-1.0)
        - Консервативная шкала: максимум 78%
        - Прогрессивное уменьшение роста вероятности с ростом score
        
        Args:
            score: Итоговый score (-100..+100)
            factors_count: Количество доступных факторов
            max_factors: Максимальное количество факторов (по умолчанию 30)
            
        Returns:
            Вероятность 50-78%
        """
        abs_score = abs(score)
        
        # Коэффициент полноты данных (0.5 - 1.0)
        data_completeness = max(0.5, min(1.0, factors_count / max_factors))
        
        # Консервативная шкала вероятности
        if abs_score < 20:
            base_prob = 50 + (abs_score * 0.25)  # 50-55%
        elif abs_score < 40:
            base_prob = 55 + ((abs_score - 20) * 0.3)  # 55-61%
        elif abs_score < 60:
            base_prob = 61 + ((abs_score - 40) * 0.25)  # 61-66%
        elif abs_score < 80:
            base_prob = 66 + ((abs_score - 60) * 0.2)  # 66-70%
        elif abs_score < 100:
            base_prob = 70 + ((abs_score - 80) * 0.15)  # 70-73%
        else:
            base_prob = min(73 + ((abs_score - 100) * 0.05), self.MAX_PROBABILITY)  # max 78%
        
        # Применяем коэффициент полноты данных
        adjusted_prob = 50 + (base_prob - 50) * data_completeness
        
        return int(min(max(adjusted_prob, 50), self.MAX_PROBABILITY))

    def _calc_trend_score(
        self,
        ema_data: Optional[Dict],
        macd_data: Optional[Dict],
        price_change_24h: Optional[float],
        price_change_7d: Optional[float],
    ) -> float:
        """Расчёт score по тренду: EMA 50/200, MACD, изменение цены."""
        score = 0.0
        factors = 0
        
        if ema_data:
            ema_50 = ema_data.get("ema_50")
            ema_200 = ema_data.get("ema_200")
            current_price = ema_data.get("current_price")
            
            if ema_50 and ema_200 and current_price:
                factors += 1
                if current_price > ema_50 > ema_200:
                    score += 10
                elif current_price > ema_50:
                    score += 5
                elif current_price < ema_50 < ema_200:
                    score -= 10
                elif current_price < ema_50:
                    score -= 5
        
        if macd_data:
            macd_signal = macd_data.get("signal")
            factors += 1
            if macd_signal == "bullish":
                score += 7
            elif macd_signal == "bearish":
                score -= 7
        
        if price_change_24h is not None:
            factors += 1
            if price_change_24h > 5:
                score += 5
            elif price_change_24h > 2:
                score += 3
            elif price_change_24h < -5:
                score -= 5
            elif price_change_24h < -2:
                score -= 3
        
        if price_change_7d is not None:
            factors += 1
            if price_change_7d > 10:
                score += 5
            elif price_change_7d > 5:
                score += 3
            elif price_change_7d < -10:
                score -= 5
            elif price_change_7d < -5:
                score -= 3
        
        return self._clamp_block_score(score, factors)

    def _calc_momentum_score(
        self,
        rsi: Optional[float],
        rsi_5m: Optional[float],
        rsi_15m: Optional[float],
        price_momentum_10min: Optional[float],
    ) -> float:
        """Расчёт score по импульсу: RSI разных ТФ."""
        score = 0.0
        factors = 0
        
        # RSI main timeframe with enhanced extreme levels
        # RSI < 30 = перепродан = ЛОНГ, RSI > 70 = перекуплен = ШОРТ
        if rsi is not None:
            factors += 1
            if rsi < 20:
                score += 20  # ОЧЕНЬ перепродан = ОЧЕНЬ СИЛЬНЫЙ ЛОНГ сигнал
            elif rsi < 25:
                score += 15  # Сильно перепродан = СИЛЬНЫЙ ЛОНГ
            elif rsi < 30:
                score += 10  # Перепродан = ЛОНГ
            elif rsi < 40:
                score += 4
            elif rsi > 80:
                score -= 20  # ОЧЕНЬ перекуплен = ОЧЕНЬ СИЛЬНЫЙ ШОРТ сигнал
            elif rsi > 75:
                score -= 15  # Сильно перекуплен = СИЛЬНЫЙ ШОРТ
            elif rsi > 70:
                score -= 10  # Перекуплен = ШОРТ
            elif rsi > 60:
                score -= 4
        
        # RSI 5m with enhanced extreme levels
        if rsi_5m is not None:
            factors += 1
            if rsi_5m < 20:
                score += 10  # ОЧЕНЬ перепродан = СИЛЬНЫЙ ЛОНГ
            elif rsi_5m < 25:
                score += 8   # Сильно перепродан = ЛОНГ
            elif rsi_5m < 30:
                score += 5   # Перепродан = ЛОНГ
            elif rsi_5m > 80:
                score -= 10  # ОЧЕНЬ перекуплен = СИЛЬНЫЙ ШОРТ
            elif rsi_5m > 75:
                score -= 8   # Сильно перекуплен = ШОРТ
            elif rsi_5m > 70:
                score -= 5   # Перекуплен = ШОРТ
        
        # RSI 15m with enhanced extreme levels
        if rsi_15m is not None:
            factors += 1
            if rsi_15m < 20:
                score += 10  # ОЧЕНЬ перепродан = СИЛЬНЫЙ ЛОНГ
            elif rsi_15m < 25:
                score += 8   # Сильно перепродан = ЛОНГ
            elif rsi_15m < 30:
                score += 5   # Перепродан = ЛОНГ
            elif rsi_15m > 80:
                score -= 10  # ОЧЕНЬ перекуплен = СИЛЬНЫЙ ШОРТ
            elif rsi_15m > 75:
                score -= 8   # Сильно перекуплен = ШОРТ
            elif rsi_15m > 70:
                score -= 5   # Перекуплен = ШОРТ
        
        if price_momentum_10min is not None:
            factors += 1
            if price_momentum_10min > 1:
                score += 6
            elif price_momentum_10min > 0.5:
                score += 3
            elif price_momentum_10min < -1:
                score -= 6
            elif price_momentum_10min < -0.5:
                score -= 3
        
        return self._clamp_block_score(score, factors)

    def _calc_whales_score(
        self,
        whale_data: Optional[Dict],
        exchange_netflow: Optional[float],
    ) -> float:
        """Расчёт score по китам: ончейн потоки."""
        score = 0.0
        factors = 0
        
        if whale_data:
            deposits = whale_data.get("deposits", 0)
            withdrawals = whale_data.get("withdrawals", 0)
            
            if deposits > 0 or withdrawals > 0:
                factors += 1
                net_flow = withdrawals - deposits
                
                if net_flow > 5:
                    score += 10
                elif net_flow > 2:
                    score += 6
                elif net_flow < -5:
                    score -= 10
                elif net_flow < -2:
                    score -= 6
        
        if exchange_netflow is not None:
            factors += 1
            if exchange_netflow < -1000000:
                score += 8
            elif exchange_netflow < -100000:
                score += 4
            elif exchange_netflow > 1000000:
                score -= 8
            elif exchange_netflow > 100000:
                score -= 4
        
        return self._clamp_block_score(score, factors)

    def _calc_derivatives_score(
        self,
        oi_change: Optional[float],
        funding_rate: Optional[float],
        long_short_ratio: Optional[float],
        liquidations: Optional[Dict],
        price_change: Optional[float],
    ) -> float:
        """Расчёт score по деривативам с составными правилами."""
        score = 0.0
        factors = 0
        
        oi_up = oi_change is not None and oi_change > 2
        oi_down = oi_change is not None and oi_change < -2
        price_up = price_change is not None and price_change > 0
        price_down = price_change is not None and price_change < 0
        funding_high = funding_rate is not None and funding_rate > 0.03
        funding_normal = funding_rate is not None and -0.01 <= funding_rate <= 0.03
        
        # СОСТАВНЫЕ ПРАВИЛА
        if oi_up and price_up and funding_normal:
            score += 8
            factors += 1
        elif oi_up and price_up and funding_high:
            score -= 3
            factors += 1
        elif oi_up and price_down:
            score += 5
            factors += 1
        elif oi_down and price_down:
            score += 6
            factors += 1
        elif oi_down and price_up:
            score += 2
            factors += 1
        
        if funding_rate is not None:
            factors += 1
            if funding_rate < -0.02:
                score += 7
            elif funding_rate < -0.01:
                score += 4
            elif funding_rate > 0.05:
                score -= 7
            elif funding_rate > 0.03:
                score -= 4
        
        if long_short_ratio is not None:
            factors += 1
            if long_short_ratio < 0.8:
                score += 5
            elif long_short_ratio > 1.5:
                score -= 5
        
        if liquidations:
            long_liqs = liquidations.get("long_liquidations", 0)
            short_liqs = liquidations.get("short_liquidations", 0)
            if long_liqs > 0 or short_liqs > 0:
                factors += 1
                if short_liqs > long_liqs * 2:
                    score += 5
                elif long_liqs > short_liqs * 2:
                    score -= 5
        
        return self._clamp_block_score(score, factors, self.DERIVATIVES_SCORE_MULTIPLIER)

    def _calc_sentiment_score(
        self,
        fear_greed: Optional[int],
        tradingview_rating: Optional[str],
    ) -> float:
        """Расчёт score по настроениям."""
        score = 0.0
        factors = 0
        
        if fear_greed is not None:
            factors += 1
            if fear_greed < 15:
                score += 20  # EXTREME Fear = ОЧЕНЬ СИЛЬНЫЙ ЛОНГ
            elif fear_greed < 25:
                score += 15  # Extreme Fear = СИЛЬНЫЙ ЛОНГ
            elif fear_greed < 35:
                score += 10  # Fear = ЛОНГ
            elif fear_greed > 85:
                score -= 20  # EXTREME Greed = ОЧЕНЬ СИЛЬНЫЙ ШОРТ
            elif fear_greed > 75:
                score -= 15  # Extreme Greed = СИЛЬНЫЙ ШОРТ
            elif fear_greed > 65:
                score -= 10  # Greed = ШОРТ
        
        if tradingview_rating:
            factors += 1
            rating = tradingview_rating.upper()
            if rating == "STRONG_BUY":
                score += 10
            elif rating == "BUY":
                score += 5
            elif rating == "STRONG_SELL":
                score -= 10
            elif rating == "SELL":
                score -= 5
        
        return self._clamp_block_score(score, factors)

    def count_consensus(self, scores: Dict) -> Dict:
        """
        Подсчёт консенсуса факторов.
        
        Args:
            scores: Dictionary containing all factor scores
        
        Returns:
            Dict: {
                "bullish_count": 7,
                "bearish_count": 2,
                "neutral_count": 1,
                "consensus": "bullish"
            }
        """
        bullish = 0
        bearish = 0
        neutral = 0
        
        for key, value in scores.items():
            if key.endswith("_score"):
                if value > 1:
                    bullish += 1
                elif value < -1:
                    bearish += 1
                else:
                    neutral += 1
        
        if bullish > bearish:
            consensus = "bullish"
        elif bearish > bullish:
            consensus = "bearish"
        else:
            consensus = "neutral"
        
        return {
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
            "consensus": consensus
        }
    
    def _detect_signal_conflicts(
        self,
        rsi: Optional[float],
        fear_greed: Optional[int],
        trades_flow_ratio: Optional[float],
        macd_signal: Optional[str],
        total_score: float,
        bullish_count: int,
        bearish_count: int,
        neutral_count: int
    ) -> Tuple[float, str]:
        """
        Обнаружение и разрешение противоречий между сигналами.
        
        ПРАВИЛО 0: RSI EXTREME OVERRIDE (НОВОЕ!)
        - RSI < 20 → АВТОМАТИЧЕСКИЙ ЛОНГ (переопределяет всё)
        - RSI > 80 → АВТОМАТИЧЕСКИЙ ШОРТ (переопределяет всё)
        
        ПРАВИЛО 1: Сильные сигналы переопределяют слабые
        - Если RSI < 25 И Fear & Greed < 25 И trades_flow_ratio > 10 И total_score < 0
          → override to LONG (score adjustment)
        - Если RSI > 75 И Fear & Greed > 75 И trades_flow_ratio < 0.1 И total_score > 0
          → override to SHORT (score adjustment)
        
        ПРАВИЛО 2: Много противоречий = нейтральный
        - Если conflict_ratio > 0.5 → sideways (score → 0)
        
        Args:
            rsi: RSI значение
            fear_greed: Fear & Greed индекс
            trades_flow_ratio: Buy/Sell соотношение
            macd_signal: MACD сигнал ("bullish"/"bearish"/"neutral")
            total_score: Текущий итоговый score
            bullish_count: Количество бычьих факторов
            bearish_count: Количество медвежьих факторов
            neutral_count: Количество нейтральных факторов
            
        Returns:
            Tuple[adjusted_score, conflict_note]
        """
        # Логирование входных данных для отладки
        logger.info(f"Conflict detection inputs: rsi={rsi}, fear_greed={fear_greed}, trades_flow_ratio={trades_flow_ratio}, macd={macd_signal}, score={total_score:.2f}")
        
        # ПРАВИЛО 0: RSI EXTREME OVERRIDE (ПРИОРИТЕТ!)
        # RSI < 20 или RSI > 80 — это ЭКСТРЕМАЛЬНЫЕ значения, которые должны переопределять ВСЁ
        if rsi is not None:
            if rsi < 20:  # Экстремальная перепроданность
                if total_score < 0:
                    # Переопределяем на ЛОНГ
                    adjusted_score = abs(total_score) * self.RSI_EXTREME_OVERRIDE_FACTOR + self.RSI_EXTREME_OVERRIDE_BOOST
                    conflict_note = f"⚠️ RSI Override: RSI={rsi:.1f} экстремально перепродан, переопределяем на ЛОНГ"
                    logger.warning(f"RSI extreme override: RSI={rsi:.1f} < 20, score {total_score:.2f} → {adjusted_score:.2f}")
                    return adjusted_score, conflict_note
            
            elif rsi > 80:  # Экстремальная перекупленность
                if total_score > 0:
                    adjusted_score = -abs(total_score) * self.RSI_EXTREME_OVERRIDE_FACTOR - self.RSI_EXTREME_OVERRIDE_BOOST
                    conflict_note = f"⚠️ RSI Override: RSI={rsi:.1f} экстремально перекуплен, переопределяем на ШОРТ"
                    logger.warning(f"RSI extreme override: RSI={rsi:.1f} > 80, score {total_score:.2f} → {adjusted_score:.2f}")
                    return adjusted_score, conflict_note
        
        # Подсчет сильных бычьих сигналов
        strong_bullish_signals = 0
        if rsi is not None and rsi < 25:
            strong_bullish_signals += 1
        if fear_greed is not None and fear_greed < 25:
            strong_bullish_signals += 1
        if trades_flow_ratio is not None and trades_flow_ratio > 10:
            strong_bullish_signals += 1
        if macd_signal == "bullish":
            strong_bullish_signals += 1
            
        # Подсчет сильных медвежьих сигналов
        strong_bearish_signals = 0
        if rsi is not None and rsi > 75:
            strong_bearish_signals += 1
        if fear_greed is not None and fear_greed > 75:
            strong_bearish_signals += 1
        if trades_flow_ratio is not None and trades_flow_ratio < 0.1:
            strong_bearish_signals += 1
        if macd_signal == "bearish":
            strong_bearish_signals += 1
        
        # Логирование подсчёта сильных сигналов
        logger.info(f"Strong signals count: bullish={strong_bullish_signals}, bearish={strong_bearish_signals}")
        
        # ПРАВИЛО 1: Сильные экстремальные сигналы переопределяют общий score
        conflict_note = ""
        adjusted_score = total_score
        
        # ИЗМЕНЕНО: Снижен порог с 3 до 2 сильных сигналов
        # Если есть 2+ сильных бычьих сигнала, но score отрицательный
        if strong_bullish_signals >= 2 and total_score < 0:
            # Переопределяем на бычий
            adjusted_score = abs(total_score) * self.CONFLICT_SCORE_ADJUSTMENT_FACTOR + self.CONFLICT_SCORE_BOOST  # Умеренно положительный
            conflict_note = f"⚠️ Конфликт разрешен: {strong_bullish_signals} сильных бычьих сигнала переопределяют score"
            logger.warning(f"Signal conflict detected: {strong_bullish_signals} strong bullish signals but score was {total_score:.2f}, adjusted to {adjusted_score:.2f}")
        
        # ИЗМЕНЕНО: Снижен порог с 3 до 2 сильных сигналов
        # Если есть 2+ сильных медвежьих сигнала, но score положительный
        elif strong_bearish_signals >= 2 and total_score > 0:
            # Переопределяем на медвежий
            adjusted_score = -abs(total_score) * self.CONFLICT_SCORE_ADJUSTMENT_FACTOR - self.CONFLICT_SCORE_BOOST  # Умеренно отрицательный
            conflict_note = f"⚠️ Конфликт разрешен: {strong_bearish_signals} сильных медвежьих сигнала переопределяют score"
            logger.warning(f"Signal conflict detected: {strong_bearish_signals} strong bearish signals but score was {total_score:.2f}, adjusted to {adjusted_score:.2f}")
        
        # ПРАВИЛО 2: Много противоречий между факторами = боковик
        # НО ТОЛЬКО если нет сильных экстремальных сигналов (не было override выше)
        total_factors = bullish_count + bearish_count + neutral_count
        if total_factors > 0 and not conflict_note:  # Применяем только если не было override
            # Проверяем, если сигналы слишком разделены
            conflict_ratio = neutral_count / total_factors
            
            # Проверяем консенсус: если бычьих/медвежьих значительно больше, чем противоположных
            bullish_consensus = bullish_count > bearish_count * 2  # Бычьих в 2 раза больше
            bearish_consensus = bearish_count > bullish_count * 2  # Медвежьих в 2 раза больше
            has_consensus = bullish_consensus or bearish_consensus
            
            # Если слишком много нейтральных или равное количество бычьих и медвежьих
            # НО не сглаживаем, если есть сильные сигналы или явный консенсус
            if conflict_ratio > self.CONFLICT_HIGH_NEUTRAL_THRESHOLD or (abs(bullish_count - bearish_count) <= 2 and total_factors >= self.CONFLICT_MIN_FACTORS_FOR_BALANCE):
                should_smooth = True
                
                # Не сглаживаем если:
                # 1. Есть >= 2 сильных экстремальных сигнала
                # 2. Есть явный консенсус факторов (одна сторона в 2 раза больше)
                if (strong_bullish_signals >= 2 or strong_bearish_signals >= 2 or has_consensus):
                    should_smooth = False
                    logger.info(f"Skipping smoothing: strong_bullish={strong_bullish_signals}, strong_bearish={strong_bearish_signals}, has_consensus={has_consensus}")
                
                if should_smooth:
                    adjusted_score = adjusted_score * 0.3
                    conflict_note = f"⚠️ Много противоречий: {neutral_count}/{total_factors} нейтральных факторов"
                    logger.info(f"High conflict ratio: {conflict_ratio:.2f}, score adjusted from {total_score:.2f} to {adjusted_score:.2f}")
        
        return adjusted_score, conflict_note
    
    def _determine_direction_from_score(self, total_score: float) -> str:
        """
        Определить направление строго по score.
        Никаких исключений — данные решают.
        
        Args:
            total_score: Итоговый score (-100..+100)
            
        Returns:
            "short" если score <= -10
            "long" если score >= 10
            "sideways" если -10 < score < 10
        """
        if total_score <= -10:
            return "short"      # Чёткий медвежий сигнал
        elif total_score >= 10:
            return "long"       # Чёткий бычий сигнал
        else:
            return "sideways"   # Нет чёткого направления = боковик
    
    def _calculate_real_probability(
        self,
        total_score: float,
        direction: str,
        bullish_count: int,
        bearish_count: int,
        neutral_count: int
    ) -> int:
        """
        Рассчитать реалистичную вероятность на основе консервативной шкалы.
        
        НОВАЯ РЕАЛИСТИЧНАЯ ФОРМУЛА:
        - Учитывает силу score и консенсус факторов
        - Консервативная шкала: 50-78% (не более!)
        - Учитывает полноту данных через количество факторов
        
        Args:
            total_score: Итоговый score (-100..+100)
            direction: Направление ("long"/"short"/"sideways")
            bullish_count: Количество бычьих факторов
            bearish_count: Количество медвежьих факторов
            neutral_count: Количество нейтральных факторов
            
        Returns:
            Вероятность 50-78%
        """
        # Используем новую реалистичную формулу
        total_factors = bullish_count + bearish_count + neutral_count
        base_prob = self.calculate_realistic_probability(
            score=total_score,
            factors_count=total_factors,
            max_factors=self.TOTAL_FACTORS  # 30 факторов
        )
        
        # Дополнительные корректировки на основе консенсуса факторов
        prob = base_prob
        
        # Бонус за консенсус факторов (до +3%)
        if direction == "long" and bullish_count > bearish_count:
            consensus_bonus = min(3, bullish_count - bearish_count)
            prob = min(self.MAX_PROBABILITY, prob + consensus_bonus)
        elif direction == "short" and bearish_count > bullish_count:
            consensus_bonus = min(3, bearish_count - bullish_count)
            prob = min(self.MAX_PROBABILITY, prob + consensus_bonus)
        elif direction == "sideways":
            # Для боковика: много нейтральных = хорошо
            if neutral_count > (bullish_count + bearish_count):
                prob = min(self.MAX_PROBABILITY, prob + 2)
        
        # Штраф за противоречивые данные (до -3%)
        if direction == "long" and bearish_count > bullish_count:
            prob = max(50, prob - 3)  # Данные противоречат направлению
        elif direction == "short" and bullish_count > bearish_count:
            prob = max(50, prob - 3)
        
        return int(max(50, min(self.MAX_PROBABILITY, prob)))
    
    def calculate_signal_strength(self, score: float) -> int:
        """
        Вычислить силу сигнала на основе score с реалистичной шкалой.
        
        Реалистичная шкала силы сигнала (рассчитывается от 130 для реализма):
        - ±100+ score = 77%+ (сильный)
        - ±80 score = 62% (хороший)
        - ±60 score = 46% (средний)
        - ±40 score = 31% (слабый)
        
        Args:
            score: Итоговый score (-100..+100, ограничен после всех корректировок)
            
        Returns:
            Сила сигнала 0-100%
        """
        abs_score = abs(score)
        
        # Реалистичная сила: рассчитываем как если бы максимум был 130,
        # чтобы 100% был редким достижением
        strength = min(int(abs_score / self.MAX_TOTAL_SCORE * 100), 100)
        
        return strength
    
    def _calculate_probability_from_score(self, score: float) -> int:
        """
        Вычислить базовую вероятность на основе score с плавной шкалой.
        
        Плавная шкала вероятности вместо фиксированных значений:
        - abs_score < 15: слабый сигнал → 50-54%
        - 15-30: умеренный сигнал → 55-64%
        - 30-60: сильный сигнал → 65-74%
        - 60-100: очень сильный сигнал → 75-84%
        - 100+: экстремальный сигнал → 85-95%
        
        Args:
            score: Итоговый score (-100..+100)
            
        Returns:
            Вероятность 50-95%
        """
        abs_score = abs(score)
        
        if abs_score < 15:
            # Слабый сигнал: 50-54%
            probability = 50 + int(abs_score * 0.27)  # 0.27 ≈ 4/15
        elif abs_score < 30:
            # Умеренный сигнал: 55-64%
            probability = 55 + int((abs_score - 15) * 0.6)
        elif abs_score < 60:
            # Сильный сигнал: 65-74%
            probability = 65 + int((abs_score - 30) * 0.3)
        elif abs_score < 100:
            # Очень сильный сигнал: 75-84%
            probability = 75 + int((abs_score - 60) * 0.225)  # 0.225 ≈ 9/40
        else:
            # Экстремальный сигнал: 85-95%
            probability = min(85 + int((abs_score - 100) * 0.1), 95)
        
        return probability
    
    def _calculate_probability_for_sideways(self, total_score: float) -> int:
        """
        Рассчитать вероятность для боковика на основе score.
        
        Чем ближе score к 0, тем выше уверенность в боковике.
        Чем ближе score к границе dead zone (8-10), тем ниже уверенность.
        
        Args:
            total_score: Итоговый score (-100..+100)
            
        Returns:
            Вероятность 51-62%
        """
        abs_score = abs(total_score)
        
        if abs_score < 2:
            # Очень близко к нулю — высокая уверенность в боковике
            return 62
        elif abs_score < 4:
            # Слабый сигнал — средняя уверенность
            return 58
        elif abs_score < 6:
            # Средний сигнал
            return 55
        elif abs_score < 8:
            # Ближе к границе
            return 53
        else:
            # На грани направления — низкая уверенность в боковике
            return 51
    
    def _calculate_probability(
        self,
        total_score: float,      # -100..+100
        direction: str,          # "long"/"short"/"sideways"
        bullish_count: int,
        bearish_count: int,
        data_sources_count: int,
        total_sources: int,
        trend_score: float,      # -10..+10
        # Новые параметры для полного расчёта
        block_trend_score: float = 0,      # -10..+10
        block_momentum_score: float = 0,   # -10..+10
        block_whales_score: float = 0,     # -10..+10
        block_derivatives_score: float = 0, # -10..+10
        block_sentiment_score: float = 0,  # -10..+10
    ) -> int:
        """
        ПОЛНЫЙ расчёт вероятности на основе ВСЕХ факторов и данных.
        
        Использует плавную шкалу вероятности на основе score с корректировками:
        1. База: плавная шкала от score (50-95%)
        2. Консенсус факторов: до ±5%
        3. Охват данных: до +3%
        4. Против тренда: до -8%
        
        Итого: 50-95%
        """
        
        # ====== БАЗА: ПЛАВНАЯ ШКАЛА ОТ SCORE ======
        # Используем новый метод для расчёта базовой вероятности
        base_prob = self._calculate_probability_from_score(total_score)
        
        # ====== КОРРЕКТИРОВКИ ======
        
        # 1. БОНУС ОТ КОНСЕНСУСА ФАКТОРОВ (до +5%)
        # Чем больше факторов в одном направлении, тем выше вероятность
        total_factors = bullish_count + bearish_count
        if total_factors > 0:
            # Разница между бычьими и медвежьими
            consensus_diff = abs(bullish_count - bearish_count)
            # Нормализуем: если все факторы в одном направлении = 100%
            consensus_ratio = consensus_diff / total_factors
            consensus_bonus = consensus_ratio * 5
        else:
            consensus_bonus = 0
        
        # 2. БОНУС ОТ ОХВАТА ДАННЫХ (до +3%)
        # Чем больше источников данных, тем увереннее сигнал
        coverage = data_sources_count / max(1, total_sources)
        coverage_bonus = coverage * 3
        
        # ====== СУММИРУЕМ БОНУСЫ ======
        prob = base_prob + consensus_bonus + coverage_bonus
        
        # ====== ШТРАФЫ ======
        
        # 1. Конфликт факторов (есть и бычьи и медвежьи)
        if bullish_count > 0 and bearish_count > 0:
            prob -= 3
        
        # 2. Равный консенсус (бычьи == медвежьи) — очень неопределённо
        if bullish_count == bearish_count and bullish_count > 0:
            prob -= 2
        
        # 3. Слабый консенсус (мало факторов)
        if total_factors < 3:
            prob -= 2
        
        # 4. Против тренда
        if direction == "long":
            if trend_score < -3:
                prob -= 8  # Лонг против сильного медвежьего тренда
            elif trend_score < 0:
                prob -= 4  # Лонг против слабого медвежьего тренда
            elif trend_score > 3:
                prob += 2  # Лонг по сильному бычьему тренду
        elif direction == "short":
            if trend_score > 3:
                prob -= 8  # Шорт против сильного бычьего тренда
            elif trend_score > 0:
                prob -= 4  # Шорт против слабого бычьего тренда
            elif trend_score < -3:
                prob += 2  # Шорт по сильному медвежьему тренду
        
        # 5. Боковик — используем специальный расчёт на основе score
        if direction == "sideways":
            # Используем новый метод для расчёта вероятности боковика
            base_sideways_prob = self._calculate_probability_for_sideways(total_score)
            
            # Применяем дополнительные корректировки на основе других факторов
            # (небольшие бонусы/штрафы, но не выходим за пределы 50-62%)
            
            # Бонус за хороший охват данных (до +2%)
            if coverage > 0.8:
                base_sideways_prob = min(62, base_sideways_prob + 2)
            
            # Штраф за конфликт факторов (-2%)
            if bullish_count > 0 and bearish_count > 0:
                base_sideways_prob = max(50, base_sideways_prob - 2)
            
            prob = base_sideways_prob
        
        # ====== ФИНАЛЬНЫЕ ГРАНИЦЫ ======
        prob = int(round(max(50, min(95, prob))))
        
        return prob
    
    def _cross_asset_correlation_check(
        self,
        symbol: str,
        direction: str,
        probability: int,
        total_score: float,
        trend_score: float,
        block_trend_score: float,
        block_momentum_score: float,
        block_whales_score: float,
        block_derivatives_score: float,
        block_sentiment_score: float,
        bullish_count: int,
        bearish_count: int,
        neutral_count: int,
        data_sources_count: int,
    ) -> tuple[str, int, float, bool]:
        """
        Реальный расчёт сигнала с учётом корреляции BTC/ETH/TON.
        
        BTC — ведущий индикатор рынка. Его данные влияют на ETH и TON.
        
        Корреляции (реальные рыночные):
        - BTC/ETH: ~90% → 40% влияние BTC score на ETH
        - BTC/TON: ~70% → 30% влияние BTC score на TON
        
        Возвращает:
        - скорректированное direction (на основе adjusted_total_score)
        - скорректированную probability (пересчитанную по ВСЕМ факторам)
        - скорректированный total_score
        - флаг is_cross_conflict
        """
        is_cross_conflict = False
        
        # BTC рассчитывается без корректировок — он ведущий индикатор
        if symbol == "BTC":
            logger.info(f"Cross-asset: {symbol} is leading indicator, no adjustment")
            return direction, probability, total_score, is_cross_conflict
        
        # Получаем последний сигнал BTC из хранилища корреляции
        btc_signal = self._correlation_signals.get("BTC")
        
        # ЛОГИРОВАНИЕ: что есть в _correlation_signals
        logger.info(f"Cross-asset check for {symbol}: _correlation_signals keys = {list(self._correlation_signals.keys())}")
        
        if not btc_signal:
            # Если BTC ещё не рассчитан, возвращаем без изменений
            logger.warning(f"Cross-asset: No BTC signal found for {symbol} correlation")
            return direction, probability, total_score, is_cross_conflict
        
        # Проверяем свежесть сигнала BTC (не старше 10 минут)
        expires_at = btc_signal.get("expires_at", 0)
        current_time = time.time()
        generated_at = btc_signal.get("generated_at", 0)
        age_seconds = current_time - generated_at
        logger.info(f"Cross-asset: BTC signal age = {age_seconds:.1f}s")
        
        if expires_at < current_time:
            logger.warning(f"Cross-asset: BTC signal expired ({age_seconds:.1f}s > 600s)")
            return direction, probability, total_score, is_cross_conflict
        
        btc_direction = btc_signal["direction"]
        btc_total_score = btc_signal["total_score"]
        btc_trend = btc_signal.get("trend_score", 0)
        
        logger.info(f"Cross-asset: BTC signal = direction={btc_direction}, total_score={btc_total_score}")
        
        # Корреляция только при сильном BTC сигнале
        if abs(btc_total_score) < 10:
            logger.info(f"BTC in sideways (score={btc_total_score:.2f}), no correlation applied to {symbol}")
            return direction, probability, total_score, False
        
        # Не применяем корреляцию при недостатке данных (менее 15 источников из 30)
        if data_sources_count < 15:
            logger.warning(f"Skipping cross-asset correlation for {symbol}: insufficient data sources ({data_sources_count}/30)")
            return direction, probability, total_score, False
        
        # ====== ОПРЕДЕЛЯЕМ СИЛУ КОРРЕЛЯЦИИ ======
        if symbol == "ETH":
            correlation = 0.30  # 30% влияние BTC на ETH (уменьшено с 0.70 для меньшей агрессивности)
        elif symbol == "TON":
            correlation = 0.20  # 20% влияние BTC на TON (уменьшено с 0.30 для меньшей агрессивности)
        else:
            correlation = 0.15  # Для других монет
        
        # ====== КОРРЕКТИРОВКА TOTAL_SCORE ======
        # Добавляем влияние BTC к собственному score монеты
        btc_influence = btc_total_score * correlation
        adjusted_total_score = total_score + btc_influence
        
        logger.info(f"Cross-asset: {symbol} score adjustment: {total_score:.2f} + ({btc_total_score:.2f} * {correlation}) = {adjusted_total_score:.2f}")
        
        # ====== ПРАВИЛО: ЗАПРЕТ ПРОТИВОПОЛОЖНЫХ СИГНАЛОВ ======
        # Если BTC сильный ШОРТ (score < -30), а ETH получается ЛОНГ → делаем НЕЙТРАЛЬНЫЙ
        # Если BTC сильный ЛОНГ (score > 30), а ETH получается ШОРТ → делаем НЕЙТРАЛЬНЫЙ
        if btc_total_score < -30 and adjusted_total_score >= 10:
            # BTC сильный шорт, но ETH хочет быть лонгом
            # Переводим в нейтральный/слабый шорт
            adjusted_total_score = min(adjusted_total_score, 0)
            logger.info(f"Cross-asset OVERRIDE: BTC strong SHORT, forcing {symbol} to neutral/short (score: {adjusted_total_score:.2f})")
        
        elif btc_total_score > 30 and adjusted_total_score <= -10:
            # BTC сильный лонг, но ETH хочет быть шортом
            # Переводим в нейтральный/слабый лонг
            adjusted_total_score = max(adjusted_total_score, 0)
            logger.info(f"Cross-asset OVERRIDE: BTC strong LONG, forcing {symbol} to neutral/long (score: {adjusted_total_score:.2f})")
        
        # ====== ПЕРЕСЧЁТ НАПРАВЛЕНИЯ по adjusted_total_score ======
        # Используем единственный источник правды для определения направления
        new_direction = self._determine_direction_from_score(adjusted_total_score)
        
        # ====== ОПРЕДЕЛЯЕМ КОНФЛИКТ ======
        # Конфликт если направление изменилось с long на short или наоборот
        if direction in ("long", "short") and new_direction in ("long", "short"):
            if direction != new_direction:
                is_cross_conflict = True
        
        # ====== ПЕРЕСЧЁТ ВЕРОЯТНОСТИ ======
        # Используем новый метод для реальной вероятности
        new_probability = self._calculate_real_probability(
            total_score=adjusted_total_score,
            direction=new_direction,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            neutral_count=neutral_count
        )
        
        # ЛОГИРОВАНИЕ РЕЗУЛЬТАТА
        logger.info(f"Cross-asset RESULT for {symbol}: direction {direction} → {new_direction}, probability {probability} → {new_probability}, score {total_score:.2f} → {adjusted_total_score:.2f}, conflict={is_cross_conflict}")
        
        return new_direction, new_probability, adjusted_total_score, is_cross_conflict

    def calculate_probability(self, 
        total_score: float,
        data_sources_count: int,
        consensus_count: int,
        total_factors: int = 10
    ) -> Dict:
        """
        Расчёт вероятности исполнения сигнала.
        
        Args:
            total_score: Итоговый score (-100 to +100)
            data_sources_count: Сколько источников данных доступно
            consensus_count: Сколько факторов указывают в одном направлении
            total_factors: Всего факторов (10)
        
        Returns:
            Dict: {
                "probability": 72,  # Вероятность в %
                "direction": "up",  # up/down
                "confidence": "high",  # high/medium/low
                "data_quality": 0.8  # Качество данных (0-1)
            }
        
        Формула:
        1. Base probability = 50% (нейтральный рынок)
        2. Score adjustment = total_score * 0.4 (макс ±40%)
        3. Data quality bonus = (sources/10) * 5% (макс +5%)
        4. Consensus bonus = (consensus/10) * 5% (макс +5%)
        
        Max probability = 50 + 40 + 5 + 5 = 100%
        Min probability = 50 - 40 = 10%
        """
        # Base probability
        base = 50.0
        
        # Score adjustment (±40%)
        score_adj = (total_score / 100) * 40
        
        # Data quality (0-5%)
        data_quality = data_sources_count / 10
        data_bonus = data_quality * 5
        
        # Consensus bonus (0-5%)
        consensus_ratio = consensus_count / total_factors
        consensus_bonus = consensus_ratio * 5
        
        # Direction and probability calculation
        if total_score > 0:
            direction = "up"
            # For bullish: higher score = higher probability of going up
            probability = base + abs(score_adj) + data_bonus + consensus_bonus
        else:
            direction = "down"
            # For bearish: more negative score = higher probability of going down
            probability = base + abs(score_adj) + data_bonus + consensus_bonus
        
        # Clamp to 20-95% (never 100% certain)
        probability = max(20, min(95, probability))
        
        # Confidence level
        if probability >= 75 or probability <= 25:
            confidence = "high"
        elif probability >= 60 or probability <= 40:
            confidence = "medium"
        else:
            confidence = "low"
        
        return {
            "probability": round(probability),
            "direction": direction,
            "confidence": confidence,
            "data_quality": round(data_quality, 2)
        }
    
    async def calculate_signal(self, symbol: str, whale_data: Dict, market_data: Dict, technical_data: Optional[Dict] = None, 
                        fear_greed: Optional[Dict] = None, funding_rate: Optional[Dict] = None,
                        order_book: Optional[Dict] = None, trades: Optional[Dict] = None,
                        futures_data: Optional[Dict] = None, onchain_data: Optional[Dict] = None,
                        exchange_flows: Optional[Dict] = None, ohlcv_data: Optional[List] = None,
                        short_term_data: Optional[Dict] = None, trades_flow: Optional[Dict] = None,
                        liquidations: Optional[Dict] = None, orderbook_delta: Optional[Dict] = None,
                        # New data sources
                        coinglass_data: Optional[Dict] = None,
                        news_sentiment: Optional[Dict] = None,
                        tradingview_rating: Optional[Dict] = None,
                        whale_alert: Optional[Dict] = None,
                        social_data: Optional[Dict] = None,
                        # Deep whale analysis (Phase 2)
                        deep_whale_data: Optional[Dict] = None,
                        # Deep derivatives analysis (Phase 2)
                        deep_derivatives_data: Optional[Dict] = None,
                        # Macro analysis (Phase 3.1)
                        macro_data: Optional[Dict] = None,
                        # Options analysis (Phase 3.2)
                        options_data: Optional[Dict] = None,
                        # Social sentiment (Phase 3.3)
                        sentiment_data: Optional[Dict] = None) -> Dict:
        """
        22-факторная система расчёта сигнала.
        
        Веса факторов (100% total):
        Долгосрочные (35%):
        - Whale Score (4%): Whale transactions + Exchange flows
        - Trend Score (5%): RSI + MACD + MA Crossover
        - Momentum Score (4%): Stoch RSI + MFI + ROC + Williams %R
        - Volatility Score (4%): Bollinger Bands + ATR + Keltner
        - Volume Score (4%): OBV + VWAP + Volume SMA
        - Market Score (4%): Price change + Volume
        - Order Book Score (4%): Bid/Ask imbalance + Spread
        - Derivatives Score (3%): OI + Long/Short + Funding
        - On-Chain Score (2%): Mempool + Hashrate
        - Sentiment Score (1%): Fear & Greed Index
        
        Краткосрочные (35%):
        - Short Trend Score (8%): RSI 5м/15м, EMA crossover
        - Trades Flow Score (7%): Buy/Sell flow ratio
        - Liquidations Score (6%): Long/Short liquidations
        - Orderbook Delta Score (7%): Bid/Ask wall changes
        - Price Momentum Score (7%): 10-min price movement
        
        Новые источники (30%):
        - Coinglass OI Score (5%): Open Interest change
        - Top Traders Score (5%): Top traders L/S ratio
        - News Sentiment Score (5%): CryptoPanic news sentiment
        - TradingView Score (6%): TradingView technical rating
        - Whale Alert Score (5%): Large transactions net flow
        - Social Score (4%): LunarCrush social metrics
        
        Each factor gives -10 to +10 points.
        Total score: -100 to +100 (weighted sum).
        Signal strength normalized to 0-100%.
        
        Args:
            whale_data: Whale transaction data
            market_data: Market data
            technical_data: Technical indicators (optional)
            fear_greed: Fear & Greed Index (optional)
            funding_rate: Funding Rate (optional)
            order_book: Order book analysis (optional)
            trades: Recent trades analysis (optional)
            futures_data: Futures data (optional)
            onchain_data: On-chain data (optional)
            exchange_flows: Exchange flows (optional)
            short_term_data: Short-term indicators (optional)
            trades_flow: Trades flow analysis (optional)
            liquidations: Liquidations data (optional)
            orderbook_delta: Orderbook delta analysis (optional)
            coinglass_data: Coinglass OI, liquidations, top traders (optional)
            news_sentiment: CryptoPanic news sentiment (optional)
            tradingview_rating: TradingView technical rating (optional)
            whale_alert: Whale Alert large transactions (optional)
            social_data: LunarCrush social metrics (optional)
            
        Returns:
            Dict with analysis results
        """
        # Очистка устаревших сигналов корреляции
        self._cleanup_expired_signals()
        
        # Calculate 10 long-term factor scores
        whale_score = self._calculate_whale_score(whale_data, exchange_flows)
        
        trend_score = 0.0
        momentum_score = 0.0
        volatility_score = 0.0
        volume_score = 0.0
        if technical_data:
            trend_score = self._calculate_trend_score(technical_data)
            momentum_score = self._calculate_momentum_score(technical_data)
            volatility_score = self._calculate_volatility_score(technical_data)
            volume_score = self._calculate_volume_score(technical_data, ohlcv_data)
        
        market_score = self._calculate_market_score(market_data)
        orderbook_score = self._calculate_orderbook_score(order_book)
        derivatives_score = self._calculate_derivatives_score(futures_data, funding_rate)
        onchain_score = self._calculate_onchain_score(onchain_data)
        sentiment_score = self._calculate_sentiment_score(fear_greed)
        
        # Calculate 5 short-term factor scores
        short_trend_score = self._calculate_short_term_trend_score(short_term_data)
        trades_flow_score = self._calculate_trades_flow_score(trades_flow)
        liquidations_score = self._calculate_liquidations_score(liquidations)
        orderbook_delta_score = self._calculate_orderbook_delta_score(orderbook_delta)
        
        # Price momentum from short_term_data
        price_momentum_score = 0.0
        if short_term_data:
            current_price = short_term_data.get("current_price")
            price_10min_ago = short_term_data.get("price_10min_ago")
            if current_price and price_10min_ago:
                price_momentum_score = self._calculate_price_momentum_score(current_price, price_10min_ago)
        
        # Calculate 7 new data source scores
        coinglass_oi_score = 0.0
        coinglass_top_traders_score = 0.0
        if coinglass_data:
            oi_change = coinglass_data.get("oi_change_24h", 0)
            price_change = market_data.get("change_24h", 0)
            coinglass_oi_score = self._calculate_oi_change_score(oi_change, price_change)
            
            # Note: Coinglass liquidations are available but not used separately
            # as we already have liquidations_score from Bybit real-time data
            # which is more suitable for short-term analysis
            
            ratio = coinglass_data.get("top_traders_ratio", 1.0)
            coinglass_top_traders_score = self._calculate_top_traders_score(ratio)
        
        news_sentiment_score = self._calculate_news_sentiment_score(news_sentiment)
        tradingview_score = self._calculate_tradingview_score(tradingview_rating)
        whale_alert_score = self._calculate_whale_alert_score(whale_alert)
        social_score = self._calculate_social_score(social_data)
        
        # Calculate deep whale analysis scores (Phase 2)
        whale_accumulation_score = 0.0
        exchange_flow_detailed_score = 0.0
        stablecoin_flow_score = 0.0
        if deep_whale_data:
            whale_accumulation_score = self._calculate_whale_accumulation_score(
                deep_whale_data.get("accumulation_distribution")
            )
            exchange_flow_detailed_score = self._calculate_exchange_flow_detailed_score(
                deep_whale_data.get("exchange_flows_detailed")
            )
            stablecoin_flow_score = self._calculate_stablecoin_flow_score(
                deep_whale_data.get("stablecoin_flows")
            )
        
        # Calculate deep derivatives analysis scores (Phase 2)
        oi_price_correlation_score = 0.0
        liquidation_levels_score = 0.0
        ls_ratio_detailed_score = 0.0
        funding_trend_score = 0.0
        basis_score = 0.0
        if deep_derivatives_data:
            oi_price_correlation_score = self._calculate_oi_price_correlation_score(
                deep_derivatives_data.get("oi_price_correlation")
            )
            liquidation_levels_score = self._calculate_liquidation_levels_score(
                deep_derivatives_data.get("liquidation_levels")
            )
            ls_ratio_detailed_score = self._calculate_ls_ratio_detailed_score(
                deep_derivatives_data.get("ls_ratio_by_exchange")
            )
            funding_trend_score = self._calculate_funding_trend_score(
                deep_derivatives_data.get("funding_rate_history")
            )
            basis_score = self._calculate_basis_score(
                deep_derivatives_data.get("basis")
            )
        
        # Calculate weighted total score (30 factors total)
        # Each factor contribution is capped at ±MAX_SINGLE_FACTOR_SCORE
        total_score = (
            # Long-term (35%)
            self._cap_factor_contribution(whale_score, self.WHALE_WEIGHT) +
            self._cap_factor_contribution(trend_score, self.TREND_WEIGHT) +
            self._cap_factor_contribution(momentum_score, self.MOMENTUM_WEIGHT) +
            self._cap_factor_contribution(volatility_score, self.VOLATILITY_WEIGHT) +
            self._cap_factor_contribution(volume_score, self.VOLUME_WEIGHT) +
            self._cap_factor_contribution(market_score, self.MARKET_WEIGHT) +
            self._cap_factor_contribution(orderbook_score, self.ORDERBOOK_WEIGHT) +
            self._cap_factor_contribution(derivatives_score, self.DERIVATIVES_WEIGHT) +
            self._cap_factor_contribution(onchain_score, self.ONCHAIN_WEIGHT) +
            self._cap_factor_contribution(sentiment_score, self.SENTIMENT_WEIGHT) +
            # Short-term (35%)
            self._cap_factor_contribution(short_trend_score, self.SHORT_TREND_WEIGHT) +
            self._cap_factor_contribution(trades_flow_score, self.TRADES_FLOW_WEIGHT) +
            self._cap_factor_contribution(liquidations_score, self.LIQUIDATIONS_WEIGHT) +
            self._cap_factor_contribution(orderbook_delta_score, self.ORDERBOOK_DELTA_WEIGHT) +
            self._cap_factor_contribution(price_momentum_score, self.PRICE_MOMENTUM_WEIGHT) +
            # New sources (30%)
            self._cap_factor_contribution(coinglass_oi_score, self.COINGLASS_OI_WEIGHT) +
            self._cap_factor_contribution(coinglass_top_traders_score, self.COINGLASS_TOP_TRADERS_WEIGHT) +
            self._cap_factor_contribution(news_sentiment_score, self.NEWS_SENTIMENT_WEIGHT) +
            self._cap_factor_contribution(tradingview_score, self.TRADINGVIEW_WEIGHT) +
            self._cap_factor_contribution(whale_alert_score, self.WHALE_ALERT_WEIGHT) +
            self._cap_factor_contribution(social_score, self.SOCIAL_WEIGHT) +
            # Deep whale analysis (Phase 2)
            self._cap_factor_contribution(whale_accumulation_score, self.WHALE_ACCUMULATION_WEIGHT) +
            self._cap_factor_contribution(exchange_flow_detailed_score, self.EXCHANGE_FLOW_DETAILED_WEIGHT) +
            self._cap_factor_contribution(stablecoin_flow_score, self.STABLECOIN_FLOW_WEIGHT) +
            # Deep derivatives analysis (Phase 2)
            self._cap_factor_contribution(oi_price_correlation_score, self.OI_PRICE_CORRELATION_WEIGHT) +
            self._cap_factor_contribution(liquidation_levels_score, self.LIQUIDATION_LEVELS_WEIGHT) +
            self._cap_factor_contribution(ls_ratio_detailed_score, self.LS_RATIO_DETAILED_WEIGHT) +
            self._cap_factor_contribution(funding_trend_score, self.FUNDING_TREND_WEIGHT) +
            self._cap_factor_contribution(basis_score, self.BASIS_WEIGHT)
        ) * self.SCORE_SCALE_FACTOR  # Scale to -100 to +100
        
        # Сглаживание score для стабильности
        new_score = total_score
        prev_score = self.previous_scores.get(symbol)
        
        if prev_score is not None:
            total_score = self.SMOOTHING_ALPHA * new_score + (1 - self.SMOOTHING_ALPHA) * prev_score
        
        # Применяем ограничение на общий score (±MAX_TOTAL_SCORE)
        total_score = self.apply_total_score_limit(total_score)
        
        # Macro analysis (Phase 3.1)
        if macro_data and macro_data.get('score', 0) != 0:
            macro_score = macro_data['score']
            total_score += macro_score
            logger.info(f"Added macro score: {macro_score}")
        
        # Options analysis (Phase 3.2, BTC/ETH only)
        if options_data and options_data.get('score', 0) != 0:
            options_score = options_data['score']
            total_score += options_score
            logger.info(f"Added options score: {options_score}")
        
        # Social sentiment (Phase 3.3)
        if sentiment_data and sentiment_data.get('score', 0) != 0:
            sentiment_score = sentiment_data['score']
            total_score += sentiment_score
            logger.info(f"Added sentiment score: {sentiment_score}")
        
        # Сохраняем для следующего раза
        self.previous_scores[symbol] = total_score
        
        # РАСЧЁТ 5 БЛОКОВ для нового расчёта вероятности
        # Подготовка данных для блоков
        
        # 1. Trend block data
        ema_data = None
        if technical_data and "ma_crossover" in technical_data:
            # Extract EMA data if available
            ema_data = {
                "ema_50": technical_data.get("ema_50"),
                "ema_200": technical_data.get("ema_200"),
                "current_price": market_data.get("price_usd"),
            }
        
        macd_data = None
        if technical_data and "macd" in technical_data:
            macd_data = {"signal": technical_data["macd"].get("signal")}
        
        price_change_24h = market_data.get("change_24h") or market_data.get("price_change_24h")
        price_change_7d = market_data.get("change_7d") or market_data.get("price_change_7d")
        
        block_trend_score = self._calc_trend_score(ema_data, macd_data, price_change_24h, price_change_7d)
        
        # 2. Momentum block data
        rsi = None
        rsi_5m = None
        rsi_15m = None
        if technical_data and "rsi" in technical_data:
            rsi = technical_data["rsi"].get("value")
        if short_term_data:
            rsi_5m = short_term_data.get("rsi_5m")
            rsi_15m = short_term_data.get("rsi_15m")
        
        price_momentum_10min = None
        if short_term_data:
            current_price_st = short_term_data.get("current_price")
            price_10min_ago = short_term_data.get("price_10min_ago")
            if current_price_st and price_10min_ago and price_10min_ago > 0:
                price_momentum_10min = ((current_price_st - price_10min_ago) / price_10min_ago) * 100
        
        block_momentum_score = self._calc_momentum_score(rsi, rsi_5m, rsi_15m, price_momentum_10min)
        
        # 3. Whales block data
        exchange_netflow_value = None
        if exchange_flows:
            exchange_netflow_value = exchange_flows.get("net_flow_usd")
        
        block_whales_score = self._calc_whales_score(whale_data, exchange_netflow_value)
        
        # 4. Derivatives block data
        oi_change_value = None
        if coinglass_data:
            oi_change_value = coinglass_data.get("oi_change_24h")
        
        funding_rate_value = None
        if funding_rate:
            funding_rate_value = funding_rate.get("rate") or funding_rate.get("rate_percent")
        
        long_short_ratio_value = None
        if futures_data:
            long_short_ratio_value = futures_data.get("long_short_ratio")
        
        liquidations_data = liquidations
        price_change_for_deriv = market_data.get("change_24h") or market_data.get("price_change_24h")
        
        block_derivatives_score = self._calc_derivatives_score(
            oi_change_value, funding_rate_value, long_short_ratio_value, liquidations_data, price_change_for_deriv
        )
        
        # 5. Sentiment block data
        fear_greed_value = None
        if fear_greed:
            fear_greed_value = fear_greed.get("value")
        
        tradingview_rating_value = None
        if tradingview_rating:
            summary = tradingview_rating.get("summary", {})
            tradingview_rating_value = summary.get("RECOMMENDATION")
        
        block_sentiment_score = self._calc_sentiment_score(fear_greed_value, tradingview_rating_value)
        
        # Apply weights to 5 blocks (total should equal 1.0)
        weights = {
            "trend": 0.25,
            "momentum": 0.20,
            "whales": 0.20,
            "derivatives": 0.25,
            "sentiment": 0.10
        }
        
        factor_score = (
            block_trend_score * weights["trend"] +
            block_momentum_score * weights["momentum"] +
            block_whales_score * weights["whales"] +
            block_derivatives_score * weights["derivatives"] +
            block_sentiment_score * weights["sentiment"]
        )
        
        # Scale to -100..+100 for compatibility
        raw_total_score_5blocks = factor_score * 10
        
        # Count consensus (22 factors)
        all_scores = {
            # Long-term
            "whale_score": whale_score,
            "trend_score": trend_score,
            "momentum_score": momentum_score,
            "volatility_score": volatility_score,
            "volume_score": volume_score,
            "market_score": market_score,
            "orderbook_score": orderbook_score,
            "derivatives_score": derivatives_score,
            "onchain_score": onchain_score,
            "sentiment_score": sentiment_score,
            # Short-term
            "short_trend_score": short_trend_score,
            "trades_flow_score": trades_flow_score,
            "liquidations_score": liquidations_score,
            "orderbook_delta_score": orderbook_delta_score,
            "price_momentum_score": price_momentum_score,
            # New sources
            "coinglass_oi_score": coinglass_oi_score,
            "coinglass_top_traders_score": coinglass_top_traders_score,
            "news_sentiment_score": news_sentiment_score,
            "tradingview_score": tradingview_score,
            "whale_alert_score": whale_alert_score,
            "social_score": social_score,
        }
        consensus_data = self.count_consensus(all_scores)
        
        # Count available data sources (22 total)
        data_sources_available = sum([
            # Long-term
            whale_data is not None and whale_data.get("transaction_count", 0) > 0,
            market_data is not None,
            technical_data is not None,
            fear_greed is not None,
            funding_rate is not None,
            order_book is not None,
            trades is not None,
            futures_data is not None,
            onchain_data is not None,
            exchange_flows is not None,
            # Short-term
            short_term_data is not None,
            trades_flow is not None,
            liquidations is not None,
            orderbook_delta is not None,
            short_term_data is not None and short_term_data.get("current_price") is not None,
            # New sources
            coinglass_data is not None,
            news_sentiment is not None,
            tradingview_rating is not None,
            whale_alert is not None,
            social_data is not None,
        ])
        
        # ====== ОБНАРУЖЕНИЕ КОНФЛИКТОВ СИГНАЛОВ ======
        # Собираем данные для проверки конфликтов
        macd_signal_value = None
        if technical_data and "macd" in technical_data:
            macd_signal_value = technical_data["macd"].get("signal")
        
        trades_flow_ratio_value = None
        if trades_flow:
            trades_flow_ratio_value = trades_flow.get("flow_ratio")
        
        # Применяем фильтр конфликтов
        adjusted_score_conflict, conflict_note = self._detect_signal_conflicts(
            rsi=rsi,
            fear_greed=fear_greed_value,
            trades_flow_ratio=trades_flow_ratio_value,
            macd_signal=macd_signal_value,
            total_score=total_score,
            bullish_count=consensus_data["bullish_count"],
            bearish_count=consensus_data["bearish_count"],
            neutral_count=consensus_data["neutral_count"]
        )
        
        # Применяем корректировку score после обнаружения конфликтов
        if adjusted_score_conflict != total_score:
            logger.info(f"Conflict detection adjusted score from {total_score:.2f} to {adjusted_score_conflict:.2f}")
            total_score = adjusted_score_conflict
        
        # ====== МЕЖМОНЕТНАЯ КОРРЕЛЯЦИЯ ======
        # Корректируем сигнал с учётом BTC (ведущий индикатор рынка)
        logger.info(f"Applying cross-asset correlation for {symbol}...")
        
        # NOTE: Cross-asset correlation uses the OLD total_score system for backward compatibility
        # but we'll override with weighted_score after correlation checks
        # Определяем начальное направление по OLD score (для корреляции)
        initial_direction = self._determine_direction_from_score(total_score)
        
        # Initial probability for correlation check (not used, will be recalculated)
        INITIAL_PROBABILITY = 50  # Neutral baseline before honest probability calculation
        
        adjusted_direction, adjusted_probability, adjusted_total_score, is_cross_conflict = self._cross_asset_correlation_check(
            symbol=symbol,
            direction=initial_direction,
            probability=INITIAL_PROBABILITY,
            total_score=total_score,
            trend_score=block_trend_score,
            block_trend_score=block_trend_score,
            block_momentum_score=block_momentum_score,
            block_whales_score=block_whales_score,
            block_derivatives_score=block_derivatives_score,
            block_sentiment_score=block_sentiment_score,
            bullish_count=consensus_data["bullish_count"],
            bearish_count=consensus_data["bearish_count"],
            neutral_count=consensus_data["neutral_count"],
            data_sources_count=data_sources_available,
        )
        
        # ЛОГИРОВАНИЕ результата корреляции
        logger.info(f"Cross-asset result: direction {initial_direction} → {adjusted_direction}, score {total_score:.2f} → {adjusted_total_score:.2f}")
        
        # Применяем корректировки к OLD score (for backward compatibility with correlation system)
        raw_direction = adjusted_direction
        total_score = adjusted_total_score
        
        # Final score limit (after all adjustments including Phase 3 and correlation)
        total_score = max(min(total_score, 100), -100)
        
        # ====== CONSENSUS PROTECTION (applied to old score) ======
        # If consensus is strongly bullish but signal is short, adjust score to be less bearish
        # If consensus is strongly bearish but signal is long, adjust score to be less bullish
        # Применяется для ВСЕХ монет (BTC, ETH, TON)
        bullish_count = consensus_data["bullish_count"]
        bearish_count = consensus_data["bearish_count"]
        
        # ИЗМЕНЕНО: Добавлена проверка порога score для более точного срабатывания
        # Consensus protection применяется только при сильном противоречии (score < -20 или > 20)
        if bullish_count > bearish_count * 2:
            if total_score < -20:  # Сильный медвежий сигнал при бычьем консенсусе
                old_score = total_score
                total_score = total_score * 0.3  # Уменьшить на 70%
                logger.warning(f"Consensus override: {symbol} has bullish consensus ({bullish_count} vs {bearish_count}) but bearish signal (score: {old_score:.2f}), reducing bearish strength")
                logger.info(f"Adjusted score after consensus protection: {total_score:.2f}")
                # Recalculate direction based on adjusted score
                raw_direction = self._determine_direction_from_score(total_score)
        elif bearish_count > bullish_count * 2:
            if total_score > 20:  # Сильный бычий сигнал при медвежьем консенсусе
                old_score = total_score
                total_score = total_score * 0.3
                logger.warning(f"Consensus override: {symbol} has bearish consensus ({bearish_count} vs {bullish_count}) but bullish signal (score: {old_score:.2f}), reducing bullish strength")
                logger.info(f"Adjusted score after consensus protection: {total_score:.2f}")
                # Recalculate direction based on adjusted score
                raw_direction = self._determine_direction_from_score(total_score)
        
        # ====== FINALIZE OLD SCORES FOR BACKWARD COMPATIBILITY ======
        # OLD direction and probability (not used for final signal, kept for logging)
        old_final_direction = raw_direction
        old_final_probability = self._calculate_real_probability(
            total_score=total_score,
            direction=old_final_direction,
            bullish_count=consensus_data["bullish_count"],
            bearish_count=consensus_data["bearish_count"],
            neutral_count=consensus_data["neutral_count"]
        )
        
        logger.info(f"OLD signal (30-factor) for {symbol}: direction={old_final_direction}, score={total_score:.2f}, probability={old_final_probability}%")
        
        # Calculate signal strength using OLD method (for logging)
        old_strength_percent = self.calculate_signal_strength(total_score)
        
        # ====== NEW: WEIGHTED FACTOR SYSTEM (10 factors, 100% total) ======
        # Calculate 10 factor scores for new weighted system
        factor_scores = {}
        
        # 1. Whales (25%) - consolidate whale_score and exchange flows
        factor_scores['whales'] = whale_score  # Already -10 to +10
        
        # 2. Derivatives (20%) - consolidate all derivatives factors
        factor_scores['derivatives'] = derivatives_score  # Already -10 to +10
        
        # 3. Trend (15%) - technical trend indicators
        factor_scores['trend'] = trend_score  # Already -10 to +10
        
        # 4. Momentum (12%) - RSI, MACD, momentum
        factor_scores['momentum'] = momentum_score  # Already -10 to +10
        
        # 5. Volume (10%) - volume analysis
        factor_scores['volume'] = volume_score  # Already -10 to +10
        
        # 6. ADX (5%) - trend strength from technical_data
        adx_factor_score = 0.0
        if technical_data and "adx" in technical_data:
            adx_value = technical_data["adx"]["value"]
            adx_direction = technical_data["adx"].get("direction", "neutral")
            if adx_value > 40:
                adx_factor_score = 7.0 if adx_direction == "bullish" else -7.0
            elif adx_value > 25:
                adx_factor_score = 4.0 if adx_direction == "bullish" else -4.0
            elif adx_value < 20:
                adx_factor_score = -3.0  # Weak trend is negative
        factor_scores['adx'] = adx_factor_score
        
        # 7. Divergence (5%) - RSI divergence from technical_data
        divergence_factor_score = 0.0
        if technical_data and "rsi_divergence" in technical_data:
            div_type = technical_data["rsi_divergence"]["type"]
            if div_type == "bullish":
                divergence_factor_score = 10.0
            elif div_type == "bearish":
                divergence_factor_score = -10.0
        factor_scores['divergence'] = divergence_factor_score
        
        # ====== CANDLESTICK PATTERNS BONUS (4h timeframe) ======
        # Паттерны работают как подтверждение, не как отдельный сигнал
        # Добавляют ±1.5 к weighted_score ТОЛЬКО если совпадают с направлением
        candlestick_bonus = 0.0
        candlestick_patterns_found = []
        
        if ohlcv_data and len(ohlcv_data) >= 3:
            patterns = detect_candlestick_patterns(ohlcv_data)
            if patterns:
                # Определяем предварительное направление для проверки совпадения
                # Используем divergence_factor_score как основу направления
                preliminary_direction = "bullish" if divergence_factor_score > 0 else "bearish" if divergence_factor_score < 0 else "neutral"
                
                # Также учитываем общий trend_factor_score если divergence нейтральный
                if preliminary_direction == "neutral":
                    trend_score = factor_scores.get('trend', 0)
                    preliminary_direction = "bullish" if trend_score > 0 else "bearish" if trend_score < 0 else "neutral"
                
                # Применяем бонус ТОЛЬКО если паттерн совпадает с направлением сигнала
                for pattern in patterns:
                    candlestick_patterns_found.append(pattern.name)
                    
                    # Бонус применяется только если направления совпадают
                    if pattern.type == preliminary_direction:
                        if pattern.type == "bullish":
                            candlestick_bonus += pattern.strength
                        elif pattern.type == "bearish":
                            candlestick_bonus -= pattern.strength
                        
                        logger.info(f"Candlestick pattern for {symbol}: {pattern.name} ({pattern.type}) "
                                  f"+{pattern.strength if pattern.type == 'bullish' else -pattern.strength:.1f} bonus applied")
                    else:
                        logger.info(f"Candlestick pattern for {symbol}: {pattern.name} ({pattern.type}) "
                                  f"ignored (doesn't match signal direction)")
                
                # Ограничиваем общий бонус от паттернов до ±1.5
                candlestick_bonus = max(-1.5, min(1.5, candlestick_bonus))
                
                if candlestick_bonus != 0:
                    logger.info(f"Total candlestick bonus for {symbol}: {candlestick_bonus:+.1f}")
        
        # ====== MACD DIVERGENCE BONUS ======
        # Бонус +3 ТОЛЬКО если RSI Divergence уже есть И MACD Divergence подтверждает
        macd_divergence_bonus = 0.0
        macd_div_detected = None
        
        # Проверяем, есть ли RSI Divergence
        rsi_div_exists = divergence_factor_score != 0.0
        rsi_div_type = None
        if rsi_div_exists and technical_data and "rsi_divergence" in technical_data:
            rsi_div_type = technical_data["rsi_divergence"]["type"]
        
        # Если RSI Divergence есть, проверяем MACD Divergence из technical_data
        if rsi_div_exists and rsi_div_type and technical_data and "macd_divergence" in technical_data:
            macd_div = technical_data["macd_divergence"]
            macd_div_type = macd_div.get("type", "none")
            
            if macd_div_type != "none":
                macd_div_detected = macd_div
                
                # Проверяем, совпадает ли MACD Divergence с RSI Divergence
                if macd_div_type == rsi_div_type:
                    # Оба дивергенции в одном направлении - добавляем бонус +3
                    if macd_div_type == "bullish":
                        macd_divergence_bonus = 3.0
                    elif macd_div_type == "bearish":
                        macd_divergence_bonus = -3.0
                    
                    logger.info(f"MACD Divergence for {symbol}: {macd_div_type} "
                              f"(RSI Div exists, {macd_divergence_bonus:+.1f} bonus applied)")
                    explanation = macd_div.get("explanation", "")
                    if explanation:
                        logger.info(f"  {explanation}")
                else:
                    logger.info(f"MACD Divergence for {symbol}: {macd_div_type} "
                              f"(conflicts with RSI Div {rsi_div_type}, no bonus)")
            else:
                logger.info(f"MACD Divergence for {symbol}: none detected")
        
        # 8. Sentiment (4%) - Fear & Greed
        sentiment_factor_score = 0.0
        if fear_greed:
            fg_value = fear_greed.get("value", 50)
            if fg_value < 25:
                sentiment_factor_score = 10.0  # Extreme fear = contrarian buy
            elif fg_value > 75:
                sentiment_factor_score = -10.0  # Extreme greed = contrarian sell
            elif fg_value < 40:
                sentiment_factor_score = 5.0  # Fear
            elif fg_value > 60:
                sentiment_factor_score = -5.0  # Greed
        factor_scores['sentiment'] = sentiment_factor_score
        
        # 9. Macro (3%) - from macro_data (Phase 3)
        macro_factor_score = 0.0
        if macro_data and macro_data.get('score', 0) != 0:
            # Normalize macro score from wider range to -10/+10 using MACRO_SCORE_NORMALIZER
            macro_factor_score = max(-10, min(10, macro_data['score'] / self.MACRO_SCORE_NORMALIZER))
        factor_scores['macro'] = macro_factor_score
        
        # 10. Options (1%) - from options_data (Phase 3)
        options_factor_score = 0.0
        if options_data and options_data.get('score', 0) != 0:
            options_factor_score = max(-10, min(10, options_data['score']))  # Already -10/+10
        factor_scores['options'] = options_factor_score
        
        # ====== GET DYNAMIC WEIGHTS FOR SYMBOL ======
        # BTC/ETH use FACTOR_WEIGHTS_WITH_WHALES, TON/SOL/XRP use FACTOR_WEIGHTS_NO_WHALES
        symbol_weights = self.get_weights_for_symbol(symbol)
        logger.info(f"Using {'WITH_WHALES' if symbol_weights == self.FACTOR_WEIGHTS_WITH_WHALES else 'NO_WHALES'} weights for {symbol}")
        
        # Calculate weighted score using new system with dynamic weights
        new_weighted_score = self.calculate_weighted_score(factor_scores, weights=symbol_weights)
        
        # ====== APPLY ENHANCERS (Order Flow, Volume Profile, Multi-Exchange) ======
        # Add extra score from enhancers (-25 to +25 range, normalized to match base_score scale)
        enhancer_score = 0.0
        enhancer_extra_data = {}
        
        if self.enhancer:
            try:
                current_price = market_data.get('price_usd', 0)
                if current_price > 0:
                    # Get total score from all enhancers
                    enhancer_raw_score = await self.enhancer.get_total_score(symbol, current_price)
                    
                    # Normalize: enhancer_raw_score is -25 to +25, normalize to same scale as new_weighted_score (-10 to +10)
                    # This gives enhancers approximately 20% weight in final score
                    enhancer_score = (enhancer_raw_score / 25.0) * 2.0  # Scale to ±2 points max
                    
                    # Apply enhancer score to weighted score
                    new_weighted_score += enhancer_score
                    
                    # Get extra data for display
                    enhancer_extra_data = await self.enhancer.get_extra_data(symbol)
                    
                    logger.info(f"Enhancers for {symbol}: raw={enhancer_raw_score:.2f}, normalized={enhancer_score:.2f}")
            except Exception as e:
                logger.warning(f"Enhancers error for {symbol}: {e}")
        
        # ====== APPLY CONFIRMATION BONUSES ======
        # Candlestick patterns and MACD Divergence act as confirmations, not separate signals
        # They strengthen existing signals when they align with the direction
        
        # Apply candlestick pattern bonus (±1.5 max)
        if candlestick_bonus != 0:
            new_weighted_score += candlestick_bonus
            logger.info(f"Applied candlestick bonus to {symbol}: {candlestick_bonus:+.1f} (new score: {new_weighted_score:+.2f})")
        
        # Apply MACD divergence bonus (±3 when RSI div exists and MACD confirms)
        if macd_divergence_bonus != 0:
            new_weighted_score += macd_divergence_bonus
            logger.info(f"Applied MACD divergence bonus to {symbol}: {macd_divergence_bonus:+.1f} (new score: {new_weighted_score:+.2f})")
        
        # ====== COMBINE OLD + NEW SYSTEMS (70% NEW + 30% OLD) ======
        # Normalize both scores to -1 to +1 range using named constants
        old_score_normalized = total_score / self.OLD_SCORE_NORMALIZER  # OLD: -100...+100 → -1...+1
        new_score_normalized = new_weighted_score / self.NEW_SCORE_NORMALIZER  # NEW: -10...+10 → -1...+1
        
        # Combine with configurable weights: 70% NEW + 30% OLD
        combined_normalized = (new_score_normalized * self.NEW_SCORE_WEIGHT) + (old_score_normalized * self.OLD_SCORE_WEIGHT)
        
        # Scale back to -10 to +10 for compatibility with existing logic
        combined_score = combined_normalized * self.COMBINED_SCORE_SCALE
        
        logger.info(f"Score combination for {symbol}: OLD={total_score:.1f} ({old_score_normalized:+.2f}), "
                   f"NEW={new_weighted_score:.2f} ({new_score_normalized:+.2f}), "
                   f"COMBINED={combined_score:.2f}")
        
        # ====== APPLY SIGNAL STABILIZER ======
        # Получаем текущую цену
        current_price = market_data.get('price_usd', 0)
        
        # Определяем предварительное направление на основе combined_score
        # Using named thresholds
        if combined_score > self.DIRECTION_LONG_THRESHOLD:
            preliminary_direction = 'long'
        elif combined_score < self.DIRECTION_SHORT_THRESHOLD:
            preliminary_direction = 'short'
        else:
            preliminary_direction = 'neutral'
        
        # Применяем новый stability manager
        old_direction = self.previous_direction.get(symbol)
        old_score = self.previous_scores.get(symbol, 0)
        
        stable_signal = self.stability_manager.get_stable_signal(
            coin=symbol,
            new_direction=preliminary_direction,
            new_score=combined_score,
            old_direction=old_direction,
            old_score=old_score
        )
        
        stable_direction = stable_signal["direction"]
        stable_score = stable_signal["score"]
        is_updated = stable_signal["changed"]
        
        # Логируем изменения/стабильность сигнала
        if is_updated:
            if old_direction and old_direction != stable_direction:
                logger.info(f"Signal CHANGED for {symbol}: {old_direction} → {stable_direction}")
                logger.info(f"  Reason: score {old_score:.2f} → {stable_score:.2f} (diff: {abs(stable_score - old_score):.2f})")
                logger.info(f"  Price: ${current_price:.2f}")
            else:
                logger.info(f"Signal updated for {symbol}: {stable_direction} (score: {stable_score:.2f})")
        else:
            logger.info(f"Signal STABLE for {symbol}: {stable_direction} (score: {stable_score:.2f}) - {stable_signal['reason']}")
        
        # Используем стабильный score вместо combined
        combined_score = stable_score
        
        # ====== USE COMBINED SCORE FOR DIRECTION (NEW SYSTEM WITH OLD INTEGRATION) ======
        # Override direction based on combined_score (scale -10 to +10)
        # Using ADAPTIVE thresholds for direction determination based on factor conflicts
        bullish_count = consensus_data["bullish_count"]
        bearish_count = consensus_data["bearish_count"]
        
        # Apply adaptive threshold
        weighted_direction, conflict_warning = self.apply_adaptive_threshold(
            combined_score, bullish_count, bearish_count
        )
        
        # Log adaptive threshold info
        threshold, conflict_level = self.calculate_adaptive_threshold(bullish_count, bearish_count)
        logger.info(f"Adaptive threshold for {symbol}: {threshold:.2f} (conflict: {conflict_level})")
        
        # Calculate probability based on direction
        if weighted_direction == 'long':
            weighted_probability = min(85, 50 + combined_score * 3.5)
        elif weighted_direction == 'short':
            weighted_probability = min(85, 50 + abs(combined_score) * 3.5)
        else:
            weighted_probability = 50
        
        # Use weighted direction as final direction
        final_direction = weighted_direction if weighted_direction != 'sideways' else 'neutral'
        final_probability = weighted_probability
        
        # Update text based on weighted direction
        if final_direction == "long":
            if abs(combined_score) >= 5:
                direction = "📈 ЛОНГ"
                strength = "сильный"
            else:
                direction = "📈 Вероятно вверх"
                strength = "средний"
        elif final_direction == "short":
            if abs(combined_score) >= 5:
                direction = "📉 ШОРТ"
                strength = "сильный"
            else:
                direction = "📉 Вероятно вниз"
                strength = "средний"
        else:  # neutral/sideways
            direction = "➡️ Боковик"
            strength = "слабый"
        
        # Determine confidence based on weighted probability
        if final_probability >= 70:
            confidence = "Высокая"
            confidence_en = "high"
        elif final_probability >= 60:
            confidence = "Средняя"
            confidence_en = "medium"
        else:
            confidence = "Низкая"
            confidence_en = "low"
        
        logger.info(f"WEIGHTED signal for {symbol}: direction={direction}, raw={final_direction}, weighted_score={new_weighted_score:.2f}, probability={final_probability}%")
        
        # Create probability_data with weighted values
        probability_data = {
            "probability": final_probability,
            "direction": "up" if final_direction == "long" else ("down" if final_direction == "short" else "sideways"),
            "confidence": confidence_en,
            "data_quality": round(data_sources_available / self.TOTAL_DATA_SOURCES, 2)
        }
        
        # Save weighted direction for correlation checks
        self.previous_direction[symbol] = final_direction
        
        # Save signal for cross-asset correlation
        current_time = time.time()
        self.last_symbol_signals[symbol] = {
            "direction": final_direction,
            "probability": final_probability,
            "total_score": new_weighted_score * self.WEIGHTED_SCORE_SCALE_FACTOR,  # Scale to -100/+100 for compatibility
            "trend_score": block_trend_score,
            "generated_at": current_time,
        }
        
        self._correlation_signals[symbol] = {
            "direction": final_direction,
            "probability": final_probability,
            "total_score": new_weighted_score * self.WEIGHTED_SCORE_SCALE_FACTOR,  # Scale to -100/+100 for compatibility
            "trend_score": block_trend_score,
            "generated_at": current_time,
            "expires_at": current_time + self.CORRELATION_SIGNAL_TTL,
        }
        logger.info(f"Saved weighted signal for {symbol}: direction={final_direction}, probability={final_probability}, weighted_score={new_weighted_score:.2f}")
        
        # Calculate signal strength from weighted score
        strength_percent = self.calculate_signal_strength(new_weighted_score * self.WEIGHTED_SCORE_SCALE_FACTOR)  # Scale to -100/+100
        
        # ====== NEW: REAL S/R LEVELS ======
        sr_levels = {}
        if ohlcv_data and len(ohlcv_data) > 0:
            current_price = market_data.get("price_usd", 0)
            sr_levels = self.calculate_real_sr_levels(ohlcv_data, current_price)
        else:
            # Fallback if no OHLCV data
            current_price = market_data.get("price_usd", 0)
            sr_levels = {
                'resistances': [],
                'supports': [],
                'nearest_resistance': current_price * 1.02 if current_price > 0 else 0,
                'nearest_support': current_price * 0.98 if current_price > 0 else 0,
            }
        
        # ====== NEW: 4-HOUR PRICE PREDICTION ======
        price_prediction = {}
        if ohlcv_data and len(ohlcv_data) > 0:
            # Get ATR from technical_data
            atr_value = 0.0
            if technical_data and "atr" in technical_data:
                atr_value = technical_data["atr"]["value"]
            else:
                # Fallback: estimate ATR as 1.5% of price
                current_price = market_data.get("price_usd", 0)
                atr_value = current_price * 0.015 if current_price > 0 else 0
            
            current_price = market_data.get("price_usd", 0)
            if current_price > 0 and atr_value > 0:
                price_prediction = self.predict_price_4h(
                    current_price=current_price,
                    weighted_score=new_weighted_score,
                    sr_levels=sr_levels,
                    atr=atr_value
                )
        
        # ====== NEW: REAL TP/SL TARGETS BASED ON S/R LEVELS ======
        real_targets = {}
        if sr_levels and 'resistances' in sr_levels and 'supports' in sr_levels:
            # Get current price and ATR value
            current_price = market_data.get("price_usd", 0)
            atr_value = 0.0
            if technical_data and "atr" in technical_data:
                atr_value = technical_data["atr"]["value"]
            else:
                # Fallback: estimate ATR as 1.5% of price
                atr_value = current_price * 0.015 if current_price > 0 else 0
            
            if current_price > 0 and atr_value > 0:
                # Map direction: "neutral" -> "sideways" for calculate_real_targets
                target_direction = "sideways" if final_direction == "neutral" else final_direction
                
                real_targets = self.calculate_real_targets(
                    direction=target_direction,  # "long", "short", or "sideways"
                    current_price=current_price,
                    resistances=sr_levels.get('resistances', []),
                    supports=sr_levels.get('supports', []),
                    atr=atr_value
                )
        
        return {
            "symbol": symbol,
            "direction": direction,
            "raw_direction": final_direction,  # "long" или "short" или "sideways"
            "strength": strength,
            "strength_percent": round(strength_percent),
            "confidence": confidence,
            "total_score": round(total_score, 2),
            # Long-term scores
            "whale_score": round(whale_score, 2),
            "trend_score": round(trend_score, 2),
            "momentum_score": round(momentum_score, 2),
            "volatility_score": round(volatility_score, 2),
            "volume_score": round(volume_score, 2),
            "market_score": round(market_score, 2),
            "orderbook_score": round(orderbook_score, 2),
            "derivatives_score": round(derivatives_score, 2),
            "onchain_score": round(onchain_score, 2),
            "sentiment_score": round(sentiment_score, 2),
            # Short-term scores
            "short_trend_score": round(short_trend_score, 2),
            "trades_flow_score": round(trades_flow_score, 2),
            "liquidations_score": round(liquidations_score, 2),
            "orderbook_delta_score": round(orderbook_delta_score, 2),
            "price_momentum_score": round(price_momentum_score, 2),
            # New source scores
            "coinglass_oi_score": round(coinglass_oi_score, 2),
            "coinglass_top_traders_score": round(coinglass_top_traders_score, 2),
            "news_sentiment_score": round(news_sentiment_score, 2),
            "tradingview_score": round(tradingview_score, 2),
            "whale_alert_score": round(whale_alert_score, 2),
            "social_score": round(social_score, 2),
            # Add probability data
            "probability": probability_data["probability"],
            "probability_direction": probability_data["direction"],
            "probability_confidence": probability_data["confidence"],
            "data_quality": probability_data["data_quality"],
            # Add consensus data
            "bullish_count": consensus_data["bullish_count"],
            "bearish_count": consensus_data["bearish_count"],
            "neutral_count": consensus_data["neutral_count"],
            "consensus": consensus_data["consensus"],
            "data_sources_count": data_sources_available,
            # Add 5 block scores for display
            "block_trend_score": round(block_trend_score, 2),
            "block_momentum_score": round(block_momentum_score, 2),
            "block_whales_score": round(block_whales_score, 2),
            "block_derivatives_score": round(block_derivatives_score, 2),
            "block_sentiment_score": round(block_sentiment_score, 2),
            # Cross-asset correlation conflict flag
            "is_cross_conflict": is_cross_conflict,
            # Adaptive threshold conflict warning
            "conflict_warning": conflict_warning,
            # Macro analysis (Phase 3.1)
            "macro": macro_data if macro_data else {'score': 0, 'verdict': 'neutral'},
            # Options analysis (Phase 3.2)
            "options": options_data if options_data else {'score': 0, 'verdict': 'neutral'},
            # Social sentiment (Phase 3.3)
            "sentiment": sentiment_data if sentiment_data else {'score': 0, 'verdict': 'neutral'},
            # NEW: Weighted factor system results
            "factor_scores": factor_scores,  # Individual factor scores (-10 to +10)
            "weighted_score": round(combined_score, 2),  # Combined score (70% NEW + 30% OLD) (-10 to +10)
            "new_weighted_score": round(new_weighted_score, 2),  # Pure NEW weighted score for reference
            "old_score": round(total_score, 2),  # OLD system score for reference
            # NEW: Enhancers data
            "enhancer_score": round(enhancer_score, 2),  # Enhancer contribution to score
            "enhancer_data": enhancer_extra_data,  # Extra data from enhancers (POC, CVD, leader)
            # NEW: Real S/R levels
            "sr_levels": sr_levels,
            # NEW: 4-hour price prediction
            "price_prediction": price_prediction,
            # NEW: Real TP/SL targets based on S/R levels
            "real_targets": real_targets,
        }
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Экранирует специальные символы Markdown для безопасного отображения в Telegram.
        
        Args:
            text: Текст для экранирования
            
        Returns:
            Экранированный текст (или исходное значение если None/не строка)
            
        Note:
            - Gracefully handles None and non-string inputs by returning them unchanged.
              This is intentional for defensive programming when dealing with optional
              API responses that may be None or unexpected types.
            - Uses simple string.replace() in a loop for readability and maintainability.
            - Performance is acceptable since we're dealing with short strings (news titles,
              status messages, etc.) typically under 200 characters. For larger texts,
              str.translate() with a translation table would be more efficient.
        """
        if not text or not isinstance(text, str):
            # Return unchanged for None or non-string inputs (defensive programming)
            return text
        
        # Список специальных символов Markdown, которые нужно экранировать
        # Based on Telegram's MarkdownV2 spec: https://core.telegram.org/bots/api#markdownv2-style
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    def format_signal_message(
        self, 
        symbol: str, 
        signal_data: Dict,
        whale_data: Dict,
        market_data: Dict,
        technical_data: Optional[Dict] = None,
        fear_greed: Optional[Dict] = None,
        funding_rate: Optional[Dict] = None,
        order_book: Optional[Dict] = None,
        futures_data: Optional[Dict] = None,
        onchain_data: Optional[Dict] = None,
        exchange_flows: Optional[Dict] = None,
        # Short-term data
        short_term_data: Optional[Dict] = None,
        trades_flow: Optional[Dict] = None,
        liquidations: Optional[Dict] = None,
        orderbook_delta: Optional[Dict] = None,
        # New data sources
        coinglass_data: Optional[Dict] = None,
        news_sentiment: Optional[Dict] = None,
        tradingview_rating: Optional[Dict] = None,
        whale_alert: Optional[Dict] = None,
        social_data: Optional[Dict] = None,
        is_cross_conflict: bool = False,  # НОВЫЙ ПАРАМЕТР
        multi_timeframe_data: Optional[Dict] = None,  # НОВЫЙ ПАРАМЕТР
        advanced_indicators: Optional[Dict] = None,  # НОВЫЙ ПАРАМЕТР
        deep_whale_data: Optional[Dict] = None,  # НОВЫЙ ПАРАМЕТР - Phase 2
        deep_derivatives_data: Optional[Dict] = None,  # НОВЫЙ ПАРАМЕТР - Phase 2
    ) -> str:
        """
        Расширенное форматирование сообщения с AI сигналом.
        
        Включает:
        - Направление сигнала с вероятностью и силой
        - Цена, TP (два уровня), SL
        - Тренд цены (1ч, 24ч, 7д)
        - Рыночные данные (Market Cap, Volume, Vol/MCap)
        - Активность китов (score, транзакции, потоки)
        - Технический анализ (RSI, MACD, BB, EMA)
        - Уровни поддержки/сопротивления
        - Топ 5 причин для сигнала
        - Факторы анализа (бычьи/медвежьи/нейтральные)
        
        Args:
            symbol: Символ монеты
            signal_data: Результаты анализа сигнала
            whale_data: Данные о китах
            market_data: Рыночные данные
            ... (остальные параметры используются для расчёта)
            
        Returns:
            Форматированное сообщение для Telegram (MarkdownV2)
        """
        # Форматирование цены
        def format_price(price: float) -> str:
            if price >= 1000:
                return f"${price:,.0f}"
            elif price >= 1:
                return f"${price:,.2f}"
            else:
                return f"${price:.6f}"
        
        # Форматирование объёмов
        def format_volume(volume: float) -> str:
            if volume >= 1_000_000_000:
                return f"${volume / 1_000_000_000:.1f}B"
            elif volume >= 1_000_000:
                return f"${volume / 1_000_000:.1f}M"
            elif volume >= 1_000:
                return f"${volume / 1_000:.1f}K"
            return f"${volume:.0f}"
        
        # Helper function to clamp scores to [-10, +10] range
        def clamp_score(value: float, min_val: float = -10.0, max_val: float = 10.0) -> float:
            """Clamp score to specified range."""
            return max(min_val, min(max_val, value))
        
        # Helper function to format liquidation price
        def format_liq_price(price: float) -> str:
            """Format liquidation price with appropriate precision."""
            if price < 10:
                return f"${price:.2f}"
            else:
                return f"${price:,.0f}"
        
        # Определяем направление из raw_direction (учитывает sideways)
        raw_direction = signal_data.get('raw_direction', 'sideways')
        probability_direction = signal_data.get('probability_direction', 'up')
        probability = signal_data['probability']
        
        # Текущая цена
        current_price = market_data['price_usd']
        
        # Направление и эмодзи
        if raw_direction == "long":
            direction_text = "ЛОНГ"
            direction_emoji = "📈"
            is_long = True
            is_sideways = False
        elif raw_direction == "short":
            direction_text = "ШОРТ"
            direction_emoji = "📉"
            is_long = False
            is_sideways = False
        else:  # sideways
            direction_text = "Боковик"
            direction_emoji = "➡️"
            is_long = False
            is_sideways = True
        
        # Рассчитываем TP (два уровня) и SL
        if is_sideways:
            # Для боковика показываем диапазон
            range_high = current_price * (1 + self.SIDEWAYS_RANGE_PERCENT / 100)
            range_low = current_price * (1 - self.SIDEWAYS_RANGE_PERCENT / 100)
            tp1_price = None
            tp2_price = None
            sl_price = None
        elif is_long:
            tp1_percent = 1.5
            tp2_percent = 2.0
            sl_percent = -0.6
            tp1_price = current_price * (1 + tp1_percent / 100)
            tp2_price = current_price * (1 + tp2_percent / 100)
            sl_price = current_price * (1 + sl_percent / 100)
            range_high = None
            range_low = None
        else:  # short
            tp1_percent = -1.5
            tp2_percent = -2.0
            sl_percent = 0.6
            tp1_price = current_price * (1 + tp1_percent / 100)
            tp2_price = current_price * (1 + tp2_percent / 100)
            sl_price = current_price * (1 + sl_percent / 100)
            range_high = None
            range_low = None
        
        # Сила сигнала (рассчитывается из total_score, не probability)
        # total_score диапазон: -100 до +100
        # Используем новую реалистичную шкалу
        total_score = signal_data.get('total_score', 0)
        signal_strength = self.calculate_signal_strength(total_score)
        filled_blocks = int(signal_strength / 10)
        empty_blocks = 10 - filled_blocks
        strength_bar = "█" * filled_blocks + "░" * empty_blocks
        
        # ===== НАЧАЛО СООБЩЕНИЯ =====
        text = f"🤖 *AI СИГНАЛ: {symbol} (4ч прогноз)*\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # ===== НАПРАВЛЕНИЕ =====
        text += "📊 *НАПРАВЛЕНИЕ*\n"
        text += f"{direction_emoji} {direction_text} ({probability}% вероятность)\n"
        text += f"Сила: {strength_bar} {signal_strength}%\n"
        
        # Если был конфликт с BTC, добавляем предупреждение
        if is_cross_conflict or signal_data.get("is_cross_conflict", False):
            text += "\n⚠️ _Сигнал скорректирован с учётом корреляции BTC_\n"
        
        text += "\n"
        
        # ===== 4-HOUR FORECAST (NEW) =====
        text += "🎯 *ПРОГНОЗ НА 4 ЧАСА*\n"
        text += f"Текущая: {format_price(current_price)}\n"
        
        if is_sideways:
            # Для боковика показываем ожидаемый диапазон
            text += f"Цель 1: {format_price(range_high)} (+1.0%)\n"
            text += f"Цель 2: {format_price(range_low)} (-1.0%)\n"
            text += f"Стоп: — (боковик)\n"
            text += f"R:R = —\n"
        else:
            # Для ЛОНГ/ШОРТ показываем TP и SL
            tp1_percent_abs = abs(tp1_percent)
            tp2_percent_abs = abs(tp2_percent)
            sl_percent_abs = abs(sl_percent)
            risk_reward = tp1_percent_abs / sl_percent_abs if sl_percent_abs > 0 else 0
            
            text += f"Цель 1: {format_price(tp1_price)} ({tp1_percent:+.1f}%)\n"
            text += f"Цель 2: {format_price(tp2_price)} ({tp2_percent:+.1f}%)\n"
            text += f"Стоп: {format_price(sl_price)} ({sl_percent:+.1f}%)\n"
            text += f"R:R = {risk_reward:.1f}\n"
        
        text += "\n"
        
        # ===== MULTI-TIMEFRAME (NEW) =====
        if multi_timeframe_data:
            text += "📊 *МУЛЬТИ-ТАЙМФРЕЙМ*\n"
            timeframes = multi_timeframe_data.get("timeframes", {})
            consensus = multi_timeframe_data.get("consensus", {})
            
            # 15m timeframe
            tf_15m = timeframes.get("15m", {})
            if tf_15m:
                rsi_15m = tf_15m.get("rsi", 0)
                dir_15m = tf_15m.get("direction", "neutral")
                emoji_15m = "🟢" if dir_15m == "bullish" else "🔴" if dir_15m == "bearish" else "🟡"
                text += f"• 15м: {emoji_15m} {dir_15m} (RSI {rsi_15m:.0f})\n"
            
            # 1h timeframe
            tf_1h = timeframes.get("1h", {})
            if tf_1h:
                rsi_1h = tf_1h.get("rsi", 0)
                dir_1h = tf_1h.get("direction", "neutral")
                emoji_1h = "🟢" if dir_1h == "bullish" else "🔴" if dir_1h == "bearish" else "🟡"
                text += f"• 1ч: {emoji_1h} {dir_1h} (RSI {rsi_1h:.0f})\n"
            
            # 4h timeframe
            tf_4h = timeframes.get("4h", {})
            if tf_4h:
                rsi_4h = tf_4h.get("rsi", 0)
                dir_4h = tf_4h.get("direction", "neutral")
                emoji_4h = "🟢" if dir_4h == "bullish" else "🔴" if dir_4h == "bearish" else "🟡"
                text += f"• 4ч: {emoji_4h} {dir_4h} (RSI {rsi_4h:.0f})\n"
            
            # Consensus
            consensus_text = consensus.get("text", "N/A")
            text += f"Консенсус: {consensus_text}\n"
            text += "\n"
        
        # ===== ADVANCED TECHNICAL ANALYSIS (NEW) =====
        if advanced_indicators:
            text += "📈 *ТЕХНИЧЕСКИЙ АНАЛИЗ*\n"
            
            # Ichimoku
            ichimoku = advanced_indicators.get("ichimoku", {})
            if ichimoku:
                signal = ichimoku.get("signal", "neutral")
                cloud_color = ichimoku.get("cloud_color", "neutral")
                text += f"• Ichimoku: {signal} (облако {cloud_color})\n"
            
            # VWAP (from technical_data if available)
            if technical_data:
                vwap_data = technical_data.get("vwap")
                if vwap_data and hasattr(vwap_data, 'value'):
                    vwap_signal = "выше VWAP" if current_price > vwap_data.value else "ниже VWAP"
                    text += f"• VWAP: {vwap_signal}\n"
            
            # Market Structure
            market_structure = advanced_indicators.get("market_structure", {})
            if market_structure:
                structure = market_structure.get("structure", "neutral")
                text += f"• Market Structure: {structure}\n"
            
            # Volume Profile
            volume_profile = advanced_indicators.get("volume_profile", {})
            if volume_profile:
                poc = volume_profile.get("poc", 0)
                text += f"• Volume Profile: POC {format_price(poc)}\n"
            
            # CVD
            cvd = advanced_indicators.get("cvd", {})
            if cvd:
                trend = cvd.get("trend", "neutral")
                text += f"• CVD: {trend}\n"
            
            # Order Blocks
            order_block = advanced_indicators.get("order_block", {})
            if order_block:
                ob_type = order_block.get("type", "none")
                text += f"• Order Blocks: {ob_type} OB\n"
            
            text += "\n"
        
        # ===== NEW: ВЗВЕШЕННЫЙ АНАЛИЗ (ТОП-10 ФАКТОРОВ) =====
        # Get factor scores and weighted score from signal_data
        factor_scores = signal_data.get('factor_scores', {})
        weighted_score = signal_data.get('weighted_score', 0)
        
        if factor_scores:
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "📊 *ВЗВЕШЕННЫЙ АНАЛИЗ \\(ТОП\\-10 ФАКТОРОВ\\)*\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Helper function for verdict emoji
            def verdict_emoji(score):
                if score > 5:
                    return "🟢"
                elif score < -5:
                    return "🔴"
                else:
                    return "🟡"
            
            # Helper function for verdict text
            def verdict_text(score):
                if score > 7:
                    return "СИЛЬНО БЫЧИЙ"
                elif score > 3:
                    return "БЫЧИЙ"
                elif score < -7:
                    return "СИЛЬНО МЕДВЕЖИЙ"
                elif score < -3:
                    return "МЕДВЕЖИЙ"
                else:
                    return "НЕЙТРАЛЬНЫЙ"
            
            # Determine which weights are being used
            # We can infer this from whether whale_score is 0 or not, or by checking the symbol
            symbol_for_weights = signal_data.get('symbol', '').upper()
            has_whale_data = symbol_for_weights in {'BTC', 'ETH'}
            
            if has_whale_data:
                weights_display = {
                    'whales': '25%',
                    'derivatives': '20%',
                    'trend': '15%',
                    'momentum': '12%',
                    'volume': '10%',
                    'adx': '5%',
                    'divergence': '5%',
                    'sentiment': '4%',
                    'macro': '3%',
                    'options': '1%',
                }
            else:
                weights_display = {
                    'whales': '0%',
                    'derivatives': '28%',
                    'trend': '22%',
                    'momentum': '16%',
                    'volume': '14%',
                    'adx': '6%',
                    'divergence': '6%',
                    'sentiment': '4%',
                    'macro': '3%',
                    'options': '1%',
                }
            
            # 1. КИТЫ
            whale_score = clamp_score(factor_scores.get('whales', 0))
            text += f"🐋 *КИТЫ \\({weights_display['whales']} веса\\)*\n"
            text += f"• Score: {whale_score:+.1f}/10\n"
            if whale_data:
                tx_count = whale_data.get('transaction_count', 0)
                total_vol = whale_data.get('total_volume_usd', 0)
                deposits = whale_data.get('deposits', 0)
                withdrawals = whale_data.get('withdrawals', 0)
                text += f"• Транзакций: {tx_count} \\(${total_vol/1_000_000:.1f}M\\)\n"
                text += f"• На биржи: {deposits} tx \\| С бирж: {withdrawals} tx\n"
            text += f"• Вердикт: {verdict_emoji(whale_score)} {verdict_text(whale_score)}\n\n"
            
            # 2. ДЕРИВАТИВЫ
            derivatives_score_val = clamp_score(factor_scores.get('derivatives', 0))
            text += f"📊 *ДЕРИВАТИВЫ \\({weights_display['derivatives']} веса\\)*\n"
            text += f"• Score: {derivatives_score_val:+.1f}/10\n"
            if funding_rate:
                rate = funding_rate.get('rate_percent', 0)
                text += f"• Funding: {rate:.4f}%\n"
            if deep_derivatives_data and deep_derivatives_data.get('ls_ratio_by_exchange'):
                ls_ratio = deep_derivatives_data['ls_ratio_by_exchange'].get('average_ratio', 1.0)
                text += f"• L/S Ratio: {ls_ratio:.2f}\n"
            text += f"• Вердикт: {verdict_emoji(derivatives_score_val)} {verdict_text(derivatives_score_val)}\n\n"
            
            # 3. ТРЕНД
            trend_score_val = clamp_score(factor_scores.get('trend', 0))
            text += f"📈 *ТРЕНД \\({weights_display['trend']} веса\\)*\n"
            text += f"• Score: {trend_score_val:+.1f}/10\n"
            if technical_data:
                if "macd" in technical_data:
                    macd_signal = technical_data["macd"].get("signal", "neutral")
                    macd_emoji = "✅" if macd_signal == "bullish" else "❌" if macd_signal == "bearish" else "➖"
                    text += f"• MACD: {macd_signal} {macd_emoji}\n"
            text += f"• Вердикт: {verdict_emoji(trend_score_val)} {verdict_text(trend_score_val)}\n\n"
            
            # 4. ИМПУЛЬС
            momentum_score_val = clamp_score(factor_scores.get('momentum', 0))
            text += f"⚡ *ИМПУЛЬС \\({weights_display['momentum']} веса\\)*\n"
            text += f"• Score: {momentum_score_val:+.1f}/10\n"
            if technical_data and "rsi" in technical_data:
                rsi_val = technical_data["rsi"]["value"]
                rsi_status = "перепродан" if rsi_val < 30 else "перекуплен" if rsi_val > 70 else "нейтральный"
                text += f"• RSI\\(14\\): {rsi_val:.0f} \\({rsi_status}\\)\n"
            text += f"• Вердикт: {verdict_emoji(momentum_score_val)} {verdict_text(momentum_score_val)}\n\n"
            
            # 5. ОБЪЁМ
            volume_score_val = clamp_score(factor_scores.get('volume', 0))
            text += f"📊 *ОБЪЁМ \\({weights_display['volume']} веса\\)*\n"
            text += f"• Score: {volume_score_val:+.1f}/10\n"
            vol_24h = market_data.get('volume_24h', 0)
            text += f"• Volume 24h: ${vol_24h/1_000_000_000:.1f}B\n"
            text += f"• Вердикт: {verdict_emoji(volume_score_val)} {verdict_text(volume_score_val)}\n\n"
            
            # 6. СИЛА ТРЕНДА / ADX
            adx_score_val = clamp_score(factor_scores.get('adx', 0))
            text += f"💪 *СИЛА ТРЕНДА \\({weights_display['adx']} веса\\)*\n"
            text += f"• Score: {adx_score_val:+.1f}/10\n"
            if technical_data and "adx" in technical_data:
                adx_value = technical_data["adx"]["value"]
                trend_strength = technical_data["adx"].get("trend_strength", "weak")
                text += f"• ADX: {adx_value:.0f} \\({trend_strength}\\)\n"
            text += f"• Вердикт: {verdict_emoji(adx_score_val)} {verdict_text(adx_score_val)}\n\n"
            
            # 7. ДИВЕРГЕНЦИЯ
            divergence_score_val = clamp_score(factor_scores.get('divergence', 0))
            text += f"📈 *ДИВЕРГЕНЦИЯ \\({weights_display['divergence']} веса\\)*\n"
            text += f"• Score: {divergence_score_val:+.1f}/10\n"
            if technical_data and "rsi_divergence" in technical_data:
                div_type = technical_data["rsi_divergence"]["type"]
                if div_type != "none":
                    text += f"• RSI Divergence: {div_type}\n"
                else:
                    text += "• RSI Divergence: нет\n"
            else:
                text += "• Вердикт: 🟡 НЕТ СИГНАЛА\n"
            text += "\n"
            
            # 8. НАСТРОЕНИЯ
            sentiment_score_val = clamp_score(factor_scores.get('sentiment', 0))
            text += f"😱 *НАСТРОЕНИЯ \\({weights_display['sentiment']} веса\\)*\n"
            text += f"• Score: {sentiment_score_val:+.1f}/10\n"
            if fear_greed:
                fg_value = fear_greed.get('value', 50)
                fg_class = fear_greed.get('classification', 'Neutral')
                text += f"• Fear & Greed: {fg_value} \\({fg_class}\\)\n"
            text += f"• Вердикт: {verdict_emoji(sentiment_score_val)} {verdict_text(sentiment_score_val)}\n\n"
            
            # 9. МАКРО
            macro_score_val = clamp_score(factor_scores.get('macro', 0))
            text += f"🌍 *МАКРО \\({weights_display['macro']} веса\\)*\n"
            text += f"• Score: {macro_score_val:+.1f}/10\n"
            macro = signal_data.get('macro', {})
            if macro and macro.get('dxy'):
                dxy = macro['dxy']
                text += f"• DXY: {dxy.get('value', 0):.1f} \\({dxy.get('change_24h', 0):+.2f}%\\)\n"
            text += f"• Вердикт: {verdict_emoji(macro_score_val)} {verdict_text(macro_score_val)}\n\n"
            
            # 10. ОПЦИОНЫ
            options_score_val = clamp_score(factor_scores.get('options', 0))
            text += f"📈 *ОПЦИОНЫ \\({weights_display['options']} веса\\)*\n"
            text += f"• Score: {options_score_val:+.1f}/10\n"
            options = signal_data.get('options', {})
            if options and options.get('put_call_ratio'):
                pc_ratio = options['put_call_ratio']
                text += f"• Put/Call: {pc_ratio:.2f}\n"
            text += f"• Вердикт: {verdict_emoji(options_score_val)} {verdict_text(options_score_val)}\n\n"
        
        # ===== KEY LEVELS (NEW - Pivot Points) =====
        # Calculate pivot points from technical_data or market_data
        text += "🎯 *КЛЮЧЕВЫЕ УРОВНИ*\n"
        if technical_data and technical_data.get("pivot_points"):
            pivot_points = technical_data["pivot_points"]
            if hasattr(pivot_points, 'r1'):
                text += f"📈 R1: {format_price(pivot_points.r1)} | R2: {format_price(pivot_points.r2)}\n"
                text += f"📉 S1: {format_price(pivot_points.s1)} | S2: {format_price(pivot_points.s2)}\n"
        else:
            # Calculate simple support/resistance based on current price
            r1 = current_price * 1.015
            r2 = current_price * 1.030
            s1 = current_price * 0.985
            s2 = current_price * 0.970
            text += f"📈 R1: {format_price(r1)} | R2: {format_price(r2)}\n"
            text += f"📉 S1: {format_price(s1)} | S2: {format_price(s2)}\n"
        
        text += "\n"
        
        # ===== NEW: РЕАЛЬНЫЕ УРОВНИ S/R =====
        sr_levels = signal_data.get('sr_levels', {})
        if sr_levels:
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "🎯 *РЕАЛЬНЫЕ УРОВНИ S/R*\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            # Resistances
            resistances = sr_levels.get('resistances', [])
            if resistances:
                text += "📈 *СОПРОТИВЛЕНИЯ:*\n"
                for i, r in enumerate(resistances[:3], 1):
                    price = r.get('price', 0)
                    strength = r.get('strength', 1)
                    source = r.get('source', 'calculated')
                    touches = r.get('touches', 0)
                    stars = "⭐" * strength
                    
                    source_text = {
                        'swing_high': 'swing high',
                        'round_number': 'круглый уровень',
                        'prev_high': 'недельный high',
                        'fib_38.2%': 'Fib 38.2%',
                        'fib_50%': 'Fib 50%',
                        'fib_61.8%': 'Fib 61.8%',
                    }.get(source, source)
                    
                    if touches > 0:
                        text += f"• R{i}: {format_price(price)} \\({source_text}, {touches} касания\\) {stars}\n"
                    else:
                        text += f"• R{i}: {format_price(price)} \\({source_text}\\) {stars}\n"
            
            text += "\n"
            
            # Supports
            supports = sr_levels.get('supports', [])
            if supports:
                text += "📉 *ПОДДЕРЖКИ:*\n"
                for i, s in enumerate(supports[:3], 1):
                    price = s.get('price', 0)
                    strength = s.get('strength', 1)
                    source = s.get('source', 'calculated')
                    touches = s.get('touches', 0)
                    stars = "⭐" * strength
                    
                    source_text = {
                        'swing_low': 'swing low',
                        'round_number': 'круглый уровень',
                        'prev_low': 'недельный low',
                        'fib_38.2%': 'Fib 38.2%',
                        'fib_50%': 'Fib 50%',
                        'fib_61.8%': 'Fib 61.8%',
                    }.get(source, source)
                    
                    if touches > 0:
                        text += f"• S{i}: {format_price(price)} \\({source_text}, {touches} касания\\) {stars}\n"
                    else:
                        text += f"• S{i}: {format_price(price)} \\({source_text}\\) {stars}\n"
            
            text += "\n"
            
            # Liquidation levels if available
            if deep_derivatives_data and deep_derivatives_data.get('liquidation_levels'):
                liq_levels = deep_derivatives_data['liquidation_levels']
                nearest_short = liq_levels.get('nearest_short_liq', 0)
                nearest_long = liq_levels.get('nearest_long_liq', 0)
                if nearest_short > 0 or nearest_long > 0:
                    text += "🎯 *ЛИКВИДАЦИИ:*\n"
                    # Format with 2 decimals for low-priced coins, 0 decimals for high-priced
                    if nearest_short > 0:
                        text += f"• Шорты: {format_liq_price(nearest_short)} \\(магнит вверх\\)\n"
                    if nearest_long > 0:
                        text += f"• Лонги: {format_liq_price(nearest_long)} \\(магнит вниз\\)\n"
                    text += "\n"
        
        # ===== NEW: СЦЕНАРИИ НА 4 ЧАСА =====
        price_prediction = signal_data.get('price_prediction', {})
        if price_prediction:
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "📈 *СЦЕНАРИИ НА 4 ЧАСА*\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            predicted_price = price_prediction.get('predicted_price', current_price)
            predicted_change = price_prediction.get('predicted_change_pct', 0)
            
            # Calculate scenario probabilities based on main signal direction (raw_direction)
            # This ensures consistency with the main direction shown at the top
            if raw_direction == "long":
                bull_prob = min(85, probability + 10)
                bear_prob = max(5, 100 - bull_prob - 25)
                side_prob = 100 - bull_prob - bear_prob
            elif raw_direction == "short":
                bear_prob = min(85, probability + 10)
                bull_prob = max(5, 100 - bear_prob - 25)
                side_prob = 100 - bull_prob - bear_prob
            else:  # sideways
                side_prob = min(70, probability + 10)
                bull_prob = (100 - side_prob) // 2
                bear_prob = 100 - side_prob - bull_prob
            
            # Calculate targets for each scenario
            nearest_r = sr_levels.get('nearest_resistance', current_price * 1.02) if sr_levels else current_price * 1.02
            nearest_s = sr_levels.get('nearest_support', current_price * 0.98) if sr_levels else current_price * 0.98
            
            text += f"🟢 *Бычий \\({bull_prob}%\\):* → {format_price(nearest_r)}\n"
            text += f"   Триггер: пробой ${current_price * 1.005:,.0f} \\+ объём\n"
            text += "\n"
            text += f"🟡 *Боковик \\({side_prob}%\\):* → {format_price(current_price * 0.995)}\\-{format_price(current_price * 1.005)}\n"
            text += f"   Триггер: ADX < 20, нет объёма\n"
            text += "\n"
            text += f"🔴 *Медвежий \\({bear_prob}%\\):* → {format_price(nearest_s)}\n"
            text += f"   Триггер: пробой ${current_price * 0.995:,.0f} вниз\n"
            text += "\n"
        
        # ===== DEEP WHALE ANALYSIS (Phase 2) =====
        if deep_whale_data:
            text += "🐋 *ГЛУБОКИЙ WHALE АНАЛИЗ*\n"
            
            # Accumulation/Distribution
            accumulation = deep_whale_data.get("accumulation_distribution", {})
            if accumulation:
                phase = accumulation.get("phase", "neutral")
                confidence = accumulation.get("confidence", 0)
                phase_emoji = "🟢" if phase == "accumulation" else "🔴" if phase == "distribution" else "🟡"
                phase_text = "Накопление" if phase == "accumulation" else "Раздача" if phase == "distribution" else "Нейтрально"
                text += f"• Фаза: {phase_emoji} {phase_text} ({confidence}%)\n"
            
            # Exchange flows detailed
            exchange_flows_detailed = deep_whale_data.get("exchange_flows_detailed", {})
            if exchange_flows_detailed:
                binance = exchange_flows_detailed.get("binance", {})
                coinbase = exchange_flows_detailed.get("coinbase", {})
                total_net = exchange_flows_detailed.get("total_net", 0)
                signal = exchange_flows_detailed.get("signal", "neutral")
                
                if binance.get("net") != 0:
                    direction = "↓ отток" if binance["net"] < 0 else "↑ приток"
                    text += f"• Binance: {format_volume(abs(binance['net']))} {direction}\n"
                
                if coinbase.get("net") != 0:
                    direction = "↓ отток" if coinbase["net"] < 0 else "↑ приток"
                    text += f"• Coinbase: {format_volume(abs(coinbase['net']))} {direction}\n"
            
            # Stablecoin flows
            stablecoin = deep_whale_data.get("stablecoin_flows", {})
            if stablecoin and stablecoin.get("total_inflow", 0) != 0:
                total_inflow = stablecoin.get("total_inflow", 0)
                direction_text = "на биржи" if total_inflow > 0 else "с бирж"
                text += f"• Stablecoin: {format_volume(abs(total_inflow))} {direction_text}\n"
            
            # Verdict
            if exchange_flows_detailed:
                signal = exchange_flows_detailed.get("signal", "neutral")
                signal_emoji = "🟢" if signal == "bullish" else "🔴" if signal == "bearish" else "🟡"
                signal_text = "бычий" if signal == "bullish" else "медвежий" if signal == "bearish" else "нейтральный"
                text += f"• Вердикт: {signal_emoji} {signal_text}\n"
            
            text += "\n"
        
        # ===== DEEP DERIVATIVES ANALYSIS (Phase 2) =====
        if deep_derivatives_data:
            text += "📊 *ДЕРИВАТИВЫ (ГЛУБОКО)*\n"
            
            # OI/Price correlation
            oi_corr = deep_derivatives_data.get("oi_price_correlation", {})
            if oi_corr:
                oi_change = oi_corr.get("oi_change_24h", 0)
                interpretation = oi_corr.get("interpretation", "")
                text += f"• OI 24ч: {oi_change:+.1f}% ({interpretation})\n"
            
            # L/S Ratio
            ls_ratio = deep_derivatives_data.get("ls_ratio_by_exchange", {})
            if ls_ratio:
                avg_ratio = ls_ratio.get("average_ratio", 1.0)
                signal = ls_ratio.get("signal", "neutral")
                signal_emoji = "🟢" if signal == "bullish" else "🔴" if signal == "bearish" else "🟡"
                text += f"• L/S Ratio: {avg_ratio:.2f} {signal_emoji}\n"
            
            # Funding trend
            funding = deep_derivatives_data.get("funding_rate_history", {})
            if funding:
                trend = funding.get("trend", "stable")
                current_rate = funding.get("current", 0)
                trend_text = "растёт" if trend == "rising" else "падает" if trend == "falling" else "стабильно"
                text += f"• Funding: {current_rate:.4f}% ({trend_text})\n"
            
            # Basis
            basis = deep_derivatives_data.get("basis", {})
            if basis:
                basis_value = basis.get("basis", 0)
                basis_type = basis.get("basis_type", "neutral")
                type_text = "контанго" if basis_type == "contango" else "бэквордация" if basis_type == "backwardation" else "нейтрально"
                text += f"• Basis: {basis_value:+.2f}% ({type_text})\n"
            
            # Verdict from OI correlation
            if oi_corr:
                signal = oi_corr.get("signal", "neutral")
                signal_emoji = "🟢" if signal == "bullish" else "🔴" if signal == "bearish" else "🟡"
                signal_text = "бычий" if signal == "bullish" else "медвежий" if signal == "bearish" else "нейтральный"
                text += f"• Вердикт: {signal_emoji} {signal_text}\n"
            
            text += "\n"
        
        # ===== MACRO ANALYSIS (Phase 3.1) =====
        macro = signal_data.get('macro', {})
        if macro and (macro.get('dxy') or macro.get('sp500')):
            text += "📊 *МАКРО АНАЛИЗ*\n"
            if macro.get('dxy'):
                d = macro['dxy']
                e = "🟢" if d['trend'] == 'bearish' else "🔴" if d['trend'] == 'bullish' else "🟡"
                text += f"• DXY: {d['value']:.1f} ({d['change_24h']:+.2f}%) {e}\n"
            if macro.get('sp500'):
                s = macro['sp500']
                e = "🟢" if s['trend'] == 'bullish' else "🔴" if s['trend'] == 'bearish' else "🟡"
                text += f"• S&P500: {s['value']:,.0f} ({s['change_24h']:+.2f}%) {e}\n"
            if macro.get('gold'):
                g = macro['gold']
                text += f"• Gold: ${g['value']:,.0f} ({g['change_24h']:+.2f}%)\n"
            v = "🟢" if macro['verdict'] == 'bullish' else "🔴" if macro['verdict'] == 'bearish' else "🟡"
            text += f"• Вердикт: {v} {macro['verdict']}\n"
            text += "\n"
        
        # ===== OPTIONS ANALYSIS (Phase 3.2) =====
        options = signal_data.get('options', {})
        if options and options.get('put_call_ratio'):
            text += "📈 *ОПЦИОНЫ (Deribit)*\n"
            text += f"• Put/Call Ratio: {options['put_call_ratio']:.2f}\n"
            text += f"• {options.get('interpretation', '')}\n"
            v = "🟢" if 'bullish' in options.get('verdict', '') else "🔴" if 'bearish' in options.get('verdict', '') else "🟡"
            text += f"• Вердикт: {v} {options['verdict']}\n"
            text += "\n"
        
        # ===== SOCIAL SENTIMENT (Phase 3.3) =====
        sentiment = signal_data.get('sentiment', {})
        if sentiment and sentiment.get('bullish_ratio') is not None:
            text += "💬 *СОЦИАЛЬНОЕ НАСТРОЕНИЕ*\n"
            text += f"• Reddit: {sentiment['bullish_ratio']*100:.0f}% бычье / {sentiment['bearish_ratio']*100:.0f}% медвежье\n"
            text += f"• Постов: {sentiment.get('posts_analyzed', 0)}\n"
            v = "🟢" if 'bullish' in sentiment.get('verdict', '') else "🔴" if 'bearish' in sentiment.get('verdict', '') else "🟡"
            text += f"• Вердикт: {v} {sentiment['verdict']}\n"
            text += "\n"
        
        
        # ===== ТРЕНД ЦЕНЫ =====
        # (Moved below but kept for compatibility)
        text += "📈 *ТРЕНД ЦЕНЫ*\n"
        # Получить реальные данные о трендах из market_data
        change_1h = market_data.get('change_1h', 0) or 0
        change_24h = market_data.get('change_24h', 0) or market_data.get('price_change_24h', 0) or 0
        change_7d = market_data.get('change_7d', 0) or market_data.get('price_change_7d', 0) or 0
        
        # Если change_1h недоступен, рассчитать из price history (short_term_data)
        if change_1h == 0 and short_term_data:
            current = short_term_data.get('current_price', 0)
            price_1h = short_term_data.get('price_1h_ago', current)
            if price_1h and price_1h > 0:
                change_1h = ((current - price_1h) / price_1h) * 100
        
        change_1h_emoji = "🟢" if change_1h >= 0 else "🔴"
        change_24h_emoji = "🟢" if change_24h >= 0 else "🔴"
        change_7d_emoji = "🟢" if change_7d >= 0 else "🔴"
        
        text += f"• 1ч: {change_1h:+.1f}% {change_1h_emoji}\n"
        text += f"• 24ч: {change_24h:+.1f}% {change_24h_emoji}\n"
        text += f"• 7д: {change_7d:+.1f}% {change_7d_emoji}\n\n"
        
        # ===== РЫНОЧНЫЕ ДАННЫЕ =====
        text += "📊 *РЫНОЧНЫЕ ДАННЫЕ*\n"
        market_cap = market_data.get('market_cap', 0)
        volume_24h = market_data.get('volume_24h', 0)
        vol_mcap_ratio = (volume_24h / market_cap * 100) if market_cap > 0 else 0
        
        text += f"💰 Market Cap: {format_volume(market_cap)}\n"
        text += f"📊 Volume 24h: {format_volume(volume_24h)}\n"
        text += f"📈 Vol/MCap: {vol_mcap_ratio:.2f}%\n\n"
        
        # ===== АКТИВНОСТЬ КИТОВ =====
        text += "🐋 *АКТИВНОСТЬ КИТОВ*\n"
        whale_score = signal_data.get('factors', {}).get('whale', {}).get('score', 0)
        whale_score_scaled = (whale_score + 10) / 2  # Scale from -10/+10 to 0/10
        whale_score_emoji = "🔥" if whale_score_scaled >= 7 else "⚡" if whale_score_scaled >= 5 else "💧"
        
        tx_count = whale_data.get('transaction_count', 0)
        deposits_count = whale_data.get('deposits', 0)  # Number of deposit transactions
        withdrawals_count = whale_data.get('withdrawals', 0)  # Number of withdrawal transactions
        total_volume = whale_data.get('total_volume_usd', 0)
        
        # Нейтральная активность при нулевых потоках
        if deposits_count == 0 and withdrawals_count == 0:
            net_flow = 0
            net_flow_text = "0"
            net_flow_sentiment = "(нейтрально, явных потоков на/с бирж нет)"
        else:
            net_flow = withdrawals_count - deposits_count
            net_flow_text = f"+{abs(net_flow)}" if net_flow > 0 else f"{net_flow}" if net_flow < 0 else "0"
            net_flow_sentiment = "(бычье)" if net_flow > 0 else "(медвежье)" if net_flow < 0 else ""
        
        text += f"Score: {whale_score_scaled:.1f}/10 {whale_score_emoji}\n"
        text += f"• Транзакций: {tx_count}\n"
        text += f"• Объём: {format_volume(total_volume)}\n"
        text += f"• На биржи: {deposits_count} тx\n"
        text += f"• С бирж: {withdrawals_count} тx\n"
        text += f"• Net Flow: {net_flow_text} tx {net_flow_sentiment}\n\n"
        
        # ===== ENHANCERS: ДОПОЛНИТЕЛЬНЫЙ АНАЛИЗ (Order Flow, Volume Profile, Multi-Exchange) =====
        enhancer_data = signal_data.get('enhancer_data', {})
        if enhancer_data:
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "📊 *ДОПОЛНИТЕЛЬНЫЙ АНАЛИЗ*\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            # Order Flow (CVD)
            order_flow_cvd = enhancer_data.get('order_flow_cvd')
            if order_flow_cvd is not None:
                cvd_sign = "+" if order_flow_cvd >= 0 else ""
                cvd_millions = order_flow_cvd / 1_000_000
                if abs(cvd_millions) >= 1:
                    cvd_formatted = f"${cvd_sign}{cvd_millions:.1f}M"
                else:
                    cvd_thousands = order_flow_cvd / 1_000
                    cvd_formatted = f"${cvd_sign}{cvd_thousands:.0f}K"
                
                if order_flow_cvd > 0:
                    text += f"├ Order Flow: 🟢 Покупатели доминируют \\(CVD {cvd_formatted}\\)\n"
                elif order_flow_cvd < 0:
                    text += f"├ Order Flow: 🔴 Продавцы доминируют \\(CVD {cvd_formatted}\\)\n"
                else:
                    text += f"├ Order Flow: 🟡 Баланс \\(CVD {cvd_formatted}\\)\n"
            
            # Volume Profile (POC)
            volume_profile_levels = enhancer_data.get('volume_profile_levels', {})
            if volume_profile_levels and volume_profile_levels.get('poc'):
                poc = volume_profile_levels['poc']
                current_price = market_data.get('price_usd', 0)
                
                if current_price > 0:
                    distance_pct = abs(current_price - poc) / current_price * 100
                    
                    if current_price < poc:
                        text += f"├ Volume Profile: Цена ниже POC \\(${poc:,.0f}\\) на {distance_pct:.1f}%\n"
                    elif current_price > poc:
                        text += f"├ Volume Profile: Цена выше POC \\(${poc:,.0f}\\) на {distance_pct:.1f}%\n"
                    else:
                        text += f"├ Volume Profile: Цена у POC \\(${poc:,.0f}\\)\n"
            
            # Exchange Leader
            exchange_leader = enhancer_data.get('exchange_leader', 'N/A')
            if exchange_leader != 'N/A':
                text += f"└ Лидер рынка: {exchange_leader}\n"
            
            text += "\n"
        
        # ===== ДОПОЛНИТЕЛЬНЫЙ АНАЛИЗ (NEW) =====
        if technical_data and any(k in technical_data for k in ["rsi_divergence", "volume_spike", "adx"]):
            text += "📈 *ДОПОЛНИТЕЛЬНЫЙ АНАЛИЗ*\n"
            
            # RSI Divergence
            if "rsi_divergence" in technical_data:
                div_data = technical_data["rsi_divergence"]
                div_type = div_data["type"]
                if div_type == "bullish":
                    text += "• 📈 Дивергенция: 🟢 Бычья RSI\n"
                elif div_type == "bearish":
                    text += "• 📈 Дивергенция: 🔴 Медвежья RSI\n"
                else:
                    text += "• 📈 Дивергенция: нет\n"
            
            # Volume Spike
            if "volume_spike" in technical_data:
                vol_spike = technical_data["volume_spike"]
                if vol_spike["is_spike"] and vol_spike["spike_percentage"] > 50:
                    spike_pct = vol_spike["spike_percentage"]
                    text += f"• 📊 Объём: Spike +{spike_pct:.0f}% ⚠️\n"
                else:
                    text += "• 📊 Объём: нормальный\n"
            
            # ADX Trend Strength
            if "adx" in technical_data:
                adx_data = technical_data["adx"]
                adx_value = adx_data["value"]
                trend_strength = adx_data["trend_strength"]
                strength_text = {
                    "weak": "слабый тренд",
                    "medium": "умеренный тренд", 
                    "strong": "сильный тренд",
                    "very_strong": "очень сильный тренд"
                }.get(trend_strength, "тренд")
                text += f"• 💪 ADX: {adx_value:.0f} ({strength_text})\n"
            
            text += "\n"
        
        # ===== ТЕХНИЧЕСКИЙ АНАЛИЗ =====
        text += "⚡ *ТЕХНИЧЕСКИЙ АНАЛИЗ*\n"
        
        if technical_data:
            # RSI
            if "rsi" in technical_data:
                rsi_value = technical_data["rsi"]["value"]
                rsi_status = "перепродан" if rsi_value < 30 else "перекуплен" if rsi_value > 70 else "нейтральный"
                text += f"• RSI(14): {rsi_value:.0f} ({rsi_status})\n"
            
            # MACD
            if "macd" in technical_data:
                macd_signal = technical_data["macd"]["signal"]
                # macd_signal is a string: "bullish", "bearish", or "neutral"
                if isinstance(macd_signal, str):
                    macd_emoji = "✅" if macd_signal in ["bullish", "buy"] else "❌" if macd_signal in ["bearish", "sell"] else "➖"
                    macd_text = "бычье пересечение" if macd_signal in ["bullish", "buy"] else "медвежье пересечение" if macd_signal in ["bearish", "sell"] else "нейтрально"
                else:
                    # Fallback for numeric values (should not happen)
                    macd_emoji = "✅" if macd_signal > 0 else "❌"
                    macd_text = "бычье пересечение" if macd_signal > 0 else "медвежье пересечение"
                text += f"• MACD: {macd_text} {macd_emoji}\n"
            
            # Bollinger Bands
            if "bollinger" in technical_data:
                bb_position = technical_data["bollinger"].get("position", "middle")
                bb_text = "в нижней половине" if bb_position == "lower" else "в верхней половине" if bb_position == "upper" else "в середине"
                text += f"• BB: {bb_text}\n"
            
            # EMA Crossover
            if "ma_crossover" in technical_data:
                # ma_crossover uses "trend" field, not "signal"
                ma_trend = technical_data["ma_crossover"].get("trend", "neutral")
                ma_emoji = "✅" if ma_trend == "bullish" else "❌" if ma_trend == "bearish" else "➖"
                ma_text = "бычий кросс" if ma_trend == "bullish" else "медвежий кросс" if ma_trend == "bearish" else "нейтрально"
                text += f"• EMA 9/21: {ma_text} {ma_emoji}\n"
        
        text += "\n"
        
        # ===== УРОВНИ ПОДДЕРЖКИ/СОПРОТИВЛЕНИЯ =====
        text += "🎯 *УРОВНИ ПОДДЕРЖКИ/СОПРОТИВЛЕНИЯ*\n"
        
        # Вычисляем примерные уровни на основе текущей цены
        r2 = current_price * 1.02
        r1 = current_price * 1.01
        pivot = current_price
        s1 = current_price * 0.99
        s2 = current_price * 0.98
        
        text += f"📈 R2: {format_price(r2)}\n"
        text += f"📈 R1: {format_price(r1)}\n"
        text += f"━━ Pivot: {format_price(pivot)} ━━\n"
        text += f"📉 S1: {format_price(s1)}\n"
        text += f"📉 S2: {format_price(s2)}\n\n"
        
        # ===== ПРИЧИНЫ СИГНАЛА (TOP 5) =====
        text += "🔥 *ПРИЧИНЫ СИГНАЛА (TOP 5)*\n"
        reasons: list[tuple[bool, str]] = []
        
        # Собираем все факторы
        
        # 1. TradingView Rating
        if tradingview_rating:
            summary = tradingview_rating.get('summary', {})
            rating = summary.get('RECOMMENDATION', 'NEUTRAL')
            if rating in ['STRONG_BUY', 'BUY']:
                reasons.append((True, f"✅ TradingView: {rating}"))
            elif rating in ['STRONG_SELL', 'SELL']:
                reasons.append((False, f"❌ TradingView: {rating}"))
        
        # 2. RSI
        if technical_data and "rsi" in technical_data:
            rsi_value = technical_data["rsi"]["value"]
            if rsi_value < 30:
                reasons.append((True, f"✅ RSI перепродан: {rsi_value:.1f}"))
            elif rsi_value > 70:
                reasons.append((False, f"❌ RSI перекуплен: {rsi_value:.1f}"))
        
        # 3. Киты
        if whale_data:
            deposits_count = whale_data.get('deposits', 0)
            withdrawals_count = whale_data.get('withdrawals', 0)
            if withdrawals_count > deposits_count:
                net_diff = withdrawals_count - deposits_count
                reasons.append((True, f"✅ Киты выводят с бирж (+{net_diff} tx)"))
            elif deposits_count > withdrawals_count:
                net_diff = deposits_count - withdrawals_count
                reasons.append((False, f"❌ Киты заводят на биржи (+{net_diff} tx)"))
        
        # 4. Fear & Greed
        if fear_greed:
            fg_value = fear_greed.get('value', 50)
            if fg_value < 25:
                reasons.append((True, f"✅ Extreme Fear: {fg_value} (время покупать)"))
            elif fg_value > 75:
                reasons.append((False, f"❌ Extreme Greed: {fg_value} (осторожность)"))
        
        # 5. MACD
        if technical_data and "macd" in technical_data:
            macd_signal = technical_data["macd"].get("signal", "neutral")
            if macd_signal in ["bullish", "buy"]:
                reasons.append((True, f"✅ MACD бычий сигнал"))
            elif macd_signal in ["bearish", "sell"]:
                reasons.append((False, f"❌ MACD медвежий сигнал"))
        
        # 6. Funding Rate
        if funding_rate:
            rate = funding_rate.get('rate', 0)
            if rate < -0.01:
                reasons.append((True, f"✅ Шорты платят: {rate:.4f}"))
            elif rate > 0.03:
                reasons.append((False, f"❌ Перегретые лонги: {rate:.4f}"))
        
        # 7. Trades Flow
        if trades_flow:
            ratio = trades_flow.get('flow_ratio', 1.0)
            if ratio > 1.5:
                reasons.append((True, f"✅ Buy/Sell ratio: {ratio:.2f} (покупки)"))
            elif ratio < 0.67:
                reasons.append((False, f"❌ Buy/Sell ratio: {ratio:.2f} (продажи)"))
        
        # 8. RSI Divergence (NEW)
        if technical_data and "rsi_divergence" in technical_data:
            div_data = technical_data["rsi_divergence"]
            div_type = div_data["type"]
            if div_type == "bullish":
                reasons.append((True, f"✅ Бычья дивергенция RSI"))
            elif div_type == "bearish":
                reasons.append((False, f"❌ Медвежья дивергенция RSI"))
        
        # 9. Volume Spike (NEW)
        if technical_data and "volume_spike" in technical_data:
            vol_spike = technical_data["volume_spike"]
            if vol_spike["is_spike"] and vol_spike["spike_percentage"] > 50:
                spike_pct = vol_spike["spike_percentage"]
                reasons.append((True, f"✅ Спайк объёма: +{spike_pct:.0f}%"))
        
        # 10. ADX Trend Strength (NEW)
        if technical_data and "adx" in technical_data:
            adx_data = technical_data["adx"]
            adx_value = adx_data["value"]
            if adx_value > 40:
                reasons.append((True, f"✅ Сильный тренд (ADX {adx_value:.0f})"))
            elif adx_value < 20:
                reasons.append((False, f"❌ Слабый тренд (ADX {adx_value:.0f})"))
        
        # Показать топ 5 причин
        for i, (_, reason_text) in enumerate(reasons[:5], 1):
            text += f"{i}. {reason_text}\n"
        
        text += "\n"
        
        # ===== ФАКТОРЫ АНАЛИЗА =====
        text += "📊 *ФАКТОРЫ АНАЛИЗА*\n"
        
        # Get actual factor counts from signal_data (already calculated in calculate_signal)
        bullish_count = signal_data.get('bullish_count', 0)
        bearish_count = signal_data.get('bearish_count', 0)
        neutral_count = signal_data.get('neutral_count', 0)
        
        if bullish_count <= 1 and bearish_count == 0:
            # Слишком мало факторов для бычьего консенсуса
            consensus_text = "НЕЙТРАЛЬНЫЙ ⚠️"
        elif bearish_count <= 1 and bullish_count == 0:
            # Слишком мало факторов для медвежьего консенсуса
            consensus_text = "НЕЙТРАЛЬНЫЙ ⚠️"
        elif bullish_count > bearish_count:
            consensus_text = "БЫЧИЙ ✅"
        elif bearish_count > bullish_count:
            consensus_text = "МЕДВЕЖИЙ ❌"
        else:
            consensus_text = "НЕЙТРАЛЬНЫЙ ⚠️"
        
        text += f"Бычьих: {bullish_count} | Медвежьих: {bearish_count} | Нейтральных: {neutral_count}\n"
        text += f"Консенсус: {consensus_text}\n"
        
        # Add conflict warning if present
        conflict_warning = signal_data.get('conflict_warning')
        if conflict_warning:
            text += f"{conflict_warning}\n"
        
        text += "\n"
        
        # ===== ПРЕДУПРЕЖДЕНИЕ О ТОРГУЕМОСТИ =====
        # Проверяем, торгуем ли сигнал
        data_sources_count = signal_data.get('data_sources_count', 0)
        coverage = data_sources_count / self.TOTAL_DATA_SOURCES
        
        # Определение слабого сигнала
        signal_strength = self.calculate_signal_strength(total_score)
        is_weak = signal_strength < 20 or probability < 60
        
        if is_weak:
            text += "⚠️ *Сигнал слабый. Рекомендуется ПРОПУСТИТЬ этот сетап.*\n\n"
        
        # ===== NEW: ИТОГОВЫЙ РАСЧЁТ (Weighted calculation breakdown) =====
        factor_scores = signal_data.get('factor_scores', {})
        weighted_score = signal_data.get('weighted_score', 0)
        
        if factor_scores:
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "🔥 *ИТОГОВЫЙ РАСЧЁТ*\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            # Determine weights based on symbol using existing method
            symbol_upper = signal_data.get('symbol', '').upper()
            w = self.get_weights_for_symbol(symbol_upper)
            
            # Show calculation for each factor
            whale_s = factor_scores.get('whales', 0)
            derivatives_s = factor_scores.get('derivatives', 0)
            trend_s = factor_scores.get('trend', 0)
            momentum_s = factor_scores.get('momentum', 0)
            volume_s = factor_scores.get('volume', 0)
            adx_s = factor_scores.get('adx', 0)
            divergence_s = factor_scores.get('divergence', 0)
            sentiment_s = factor_scores.get('sentiment', 0)
            macro_s = factor_scores.get('macro', 0)
            options_s = factor_scores.get('options', 0)
            
            # Calculate weighted contributions with correct weights
            whale_contrib = whale_s * w['whales']
            derivatives_contrib = derivatives_s * w['derivatives']
            trend_contrib = trend_s * w['trend']
            momentum_contrib = momentum_s * w['momentum']
            volume_contrib = volume_s * w['volume']
            adx_contrib = adx_s * w['adx']
            divergence_contrib = divergence_s * w['divergence']
            sentiment_contrib = sentiment_s * w['sentiment']
            macro_contrib = macro_s * w['macro']
            options_contrib = options_s * w['options']
            
            # Display with correct percentages
            text += f"• Киты:       {whale_s:+.1f} × {int(w['whales']*100)}% = {whale_contrib:+.2f}\n"
            text += f"• Деривативы: {derivatives_s:+.1f} × {int(w['derivatives']*100)}% = {derivatives_contrib:+.2f}\n"
            text += f"• Тренд:      {trend_s:+.1f} × {int(w['trend']*100)}% = {trend_contrib:+.2f}\n"
            text += f"• Импульс:    {momentum_s:+.1f} × {int(w['momentum']*100)}% = {momentum_contrib:+.2f}\n"
            text += f"• Объём:      {volume_s:+.1f} × {int(w['volume']*100)}% = {volume_contrib:+.2f}\n"
            text += f"• ADX:        {adx_s:+.1f} × {int(w['adx']*100)}%  = {adx_contrib:+.2f}\n"
            text += f"• Дивергенция:{divergence_s:+.1f} × {int(w['divergence']*100)}%  = {divergence_contrib:+.2f}\n"
            text += f"• Настроения: {sentiment_s:+.1f} × {int(w['sentiment']*100)}%  = {sentiment_contrib:+.2f}\n"
            text += f"• Макро:      {macro_s:+.1f} × {int(w['macro']*100)}%  = {macro_contrib:+.2f}\n"
            text += f"• Опционы:    {options_s:+.1f} × {int(w['options']*100)}%  = {options_contrib:+.2f}\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 *ИТОГО: {weighted_score:+.2f}*\n\n"

        
        # ===== FOOTER =====
        text += f"📡 Факторов: {data_sources_count}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "⚠️ *DISCLAIMER*\n"
        text += "_Это НЕ финансовый совет. Сигналы основаны на техническом анализе и могут быть ошибочными. "
        text += "Торгуйте только теми средствами, которые готовы потерять. DYOR._"
        
        return text
    
    def format_signal_message_compact(
        self,
        symbol: str,
        signal_data: Dict,
        market_data: Dict,
        technical_data: Optional[Dict] = None,
        fear_greed: Optional[Dict] = None,
        funding_rate: Optional[Dict] = None,
        deep_derivatives_data: Optional[Dict] = None,
    ) -> str:
        """
        Компактное форматирование сообщения с AI сигналом (15-20 строк).
        
        Использует CompactMessageFormatter для создания краткого и информативного сообщения.
        
        Args:
            symbol: Символ монеты
            signal_data: Результаты анализа сигнала
            market_data: Рыночные данные
            technical_data: Технические индикаторы (для S/R уровней)
            fear_greed: Fear & Greed Index
            funding_rate: Funding Rate
            deep_derivatives_data: Данные деривативов (для ликвидаций)
            
        Returns:
            Компактное форматированное сообщение для Telegram (Markdown)
        """
        # Получаем направление и вероятность
        raw_direction = signal_data.get('raw_direction', 'sideways')
        probability = signal_data.get('probability', 50.0)
        current_price = market_data['price_usd']
        
        # Получаем enhancer_data из signal_data (содержит Volume Profile и другие данные)
        enhancer_extra_data = signal_data.get('enhancer_data', {})
        
        # Получаем уровни поддержки/сопротивления из технических индикаторов
        sr_levels_data = signal_data.get('sr_levels', {})
        resistances = sr_levels_data.get('resistances', [])
        supports = sr_levels_data.get('supports', [])
        
        # Получаем ATR для расчёта targets
        atr_value = 0
        if technical_data and 'atr' in technical_data:
            atr_value = technical_data['atr'].get('value', 0)
        
        # Если ATR не доступен, используем примерное значение (1.5% от цены)
        if not atr_value or atr_value == 0:
            atr_value = current_price * 0.015
        
        # Рассчитываем реальные TP и SL на основе уровней поддержки/сопротивления
        if raw_direction == "sideways":
            # Для боковика показываем диапазон
            tp1 = current_price * (1 + self.SIDEWAYS_RANGE_PERCENT / 100)
            tp2 = current_price * (1 + self.SIDEWAYS_RANGE_PERCENT / 100)
            sl = current_price * (1 - self.SIDEWAYS_RANGE_PERCENT / 100)
            tp1_label = f"+{self.SIDEWAYS_RANGE_PERCENT}%"
            tp2_label = f"+{self.SIDEWAYS_RANGE_PERCENT}%"
            sl_label = f"-{self.SIDEWAYS_RANGE_PERCENT}%"
            rr = None
        else:
            # Используем реальные уровни для LONG/SHORT
            real_targets = self.calculate_real_targets(
                direction=raw_direction,
                current_price=current_price,
                resistances=resistances,
                supports=supports,
                atr=atr_value
            )
            
            tp1 = real_targets.get('tp1', current_price * 1.015)
            tp2 = real_targets.get('tp2', current_price * 1.025)
            sl = real_targets.get('stop_loss', current_price * 0.995)
            rr = real_targets.get('rr_ratio', 0)
            
            # Calculate percentage labels
            tp1_pct = ((tp1 / current_price) - 1) * 100 if tp1 else 0
            tp2_pct = ((tp2 / current_price) - 1) * 100 if tp2 else 0
            sl_pct = ((sl / current_price) - 1) * 100 if sl else 0
            
            tp1_label = f"{tp1_pct:+.1f}%"
            tp2_label = f"{tp2_pct:+.1f}%"
            sl_label = f"{sl_pct:+.1f}%"
        
        # Подготовка targets для компактного формата
        targets = {
            "tp1": tp1,
            "tp1_label": tp1_label,
            "tp2": tp2,
            "tp2_label": tp2_label,
            "sl": sl,
            "sl_label": sl_label,
            "rr": rr
        }
        
        # Подготовка ключевых уровней из Volume Profile и S/R levels
        levels = {}
        
        # Получаем Volume Profile levels из enhancer_data
        volume_profile_levels = enhancer_extra_data.get('volume_profile_levels', {})
        if volume_profile_levels:
            vah = volume_profile_levels.get('vah')  # Value Area High
            val = volume_profile_levels.get('val')  # Value Area Low
            poc = volume_profile_levels.get('poc')  # Point of Control
            
            # Используем VAH и VAL как сопротивление и поддержку
            if vah:
                levels['resistance'] = vah
            if val:
                levels['support'] = val
        
        # Если Volume Profile недоступен, используем ближайшие S/R levels
        if not levels.get('resistance') and resistances:
            levels['resistance'] = resistances[0]['price']
        if not levels.get('support') and supports:
            levels['support'] = supports[0]['price']
        
        # Добавляем второй уровень сопротивления и поддержки
        if resistances and len(resistances) > 1:
            levels['resistance2'] = resistances[1]['price']
        if supports and len(supports) > 1:
            levels['support2'] = supports[1]['price']
        
        # Подготовка enhancer_data для передачи в formatter
        # Это будет использоваться для извлечения "Почему вход" причин
        formatter_enhancer_data = {
            'current_price': current_price,
            'fear_greed': fear_greed,
            'rsi': technical_data.get('rsi') if technical_data else None,
            'macd': technical_data.get('macd') if technical_data else None,
        }
        
        # Добавляем funding только если оно существует
        if funding_rate:
            funding_value = funding_rate.get('funding_rate')
            if funding_value is not None:
                formatter_enhancer_data['funding'] = {'current_funding': funding_value}
        
        # Добавляем TradingView рейтинг из signal_data если есть
        tradingview_rating = signal_data.get('tradingview_rating')
        if tradingview_rating:
            formatter_enhancer_data['tradingview'] = tradingview_rating
        
        # Добавляем данные о ликвидациях из deep_derivatives_data
        if deep_derivatives_data:
            liquidation_levels = deep_derivatives_data.get('liquidation_levels', {})
            if liquidation_levels:
                formatter_enhancer_data['liquidation_zones'] = {
                    'nearest_short': liquidation_levels.get('nearest_short_liq'),
                    'nearest_long': liquidation_levels.get('nearest_long_liq')
                }
        
        # Добавляем Wyckoff phase из signal_data если есть
        wyckoff_phase = signal_data.get('wyckoff_phase')
        if wyckoff_phase:
            formatter_enhancer_data['wyckoff'] = {
                'phase': wyckoff_phase,
                'confidence': signal_data.get('wyckoff_confidence', 0.5)
            }
        
        # Используем CompactMessageFormatter
        message = self.compact_formatter.format_signal(
            coin=symbol,
            direction=raw_direction,
            entry_price=current_price,
            targets=targets,
            confidence=probability,
            timeframe="4H",
            levels=levels if levels else None,
            enhancer_data=formatter_enhancer_data
        )
        
        return message
    
    async def analyze_coin(self, symbol: str) -> str:
        """
        Полный анализ монеты и генерация сигнала с 10-факторной системой.
        
        Args:
            symbol: Символ монеты (BTC, ETH)
            
        Returns:
            Форматированное сообщение с AI сигналом
        """
        symbol = symbol.upper()
        
        # Сбрасываем кэш для получения свежих данных
        self.clear_cache()
        
        # Проверяем поддержку монеты
        if symbol not in self.SUPPORTED_SIGNAL_COINS:
            return (
                f"❌ *Ошибка*\n\n"
                f"AI-сигналы сейчас доступны только для трёх монет:\n"
                f"• BTC\n"
                f"• ETH\n"
                f"• TON\n"
            )
        
        try:
            bybit_symbol = self.bybit_mapping.get(symbol, f"{symbol}USDT")
            
            # Gather all data sources in parallel
            logger.info(f"Gathering all data sources for {symbol}...")
            
            whale_data_task = self.get_whale_data(symbol)
            market_data_task = self.get_market_data(symbol)
            fear_greed_task = self.get_fear_greed_index()
            funding_rate_task = self.get_funding_rate(symbol)
            
            # Gather external data sources
            external_data_task = self.data_source_manager.gather_all_data(
                self.whale_tracker, symbol, bybit_symbol
            )
            
            # Wait for all tasks
            whale_data, market_data, fear_greed, funding_rate, external_data = await asyncio.gather(
                whale_data_task,
                market_data_task,
                fear_greed_task,
                funding_rate_task,
                external_data_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(whale_data, Exception):
                logger.error(f"Error fetching whale data: {whale_data}")
                whale_data = None
            if isinstance(market_data, Exception):
                logger.error(f"Error fetching market data: {market_data}")
                market_data = None
            if isinstance(fear_greed, Exception):
                logger.error(f"Error fetching fear & greed: {fear_greed}")
                fear_greed = None
            if isinstance(funding_rate, Exception):
                logger.error(f"Error fetching funding rate: {funding_rate}")
                funding_rate = None
            if isinstance(external_data, Exception):
                logger.error(f"Error fetching external data: {external_data}")
                external_data = {}
            
            # Check essential data
            if market_data is None:
                return (
                    "❌ *Ошибка получения данных*\n\n"
                    "Не удалось загрузить рыночные данные.\n"
                    "Попробуйте позже."
                )
            
            # Default whale data if unavailable
            if whale_data is None:
                logger.warning(f"Whale data unavailable for {symbol}, using defaults")
                whale_data = {
                    "transaction_count": 0,
                    "total_volume_usd": 0,
                    "deposits": 0,
                    "withdrawals": 0,
                    "largest_transaction": 0,
                    "sentiment": "neutral"
                }
            
            # Extract external data
            ohlcv_data = external_data.get("ohlcv")
            order_book = external_data.get("order_book")
            trades = external_data.get("trades")
            futures_data = external_data.get("futures")
            onchain_data = external_data.get("onchain")
            exchange_flows = external_data.get("exchange_flows")
            
            # Calculate technical indicators with OHLCV data
            technical_data = await self.calculate_technical_indicators(symbol, ohlcv_data)
            
            # Gather SHORT-TERM data (NEW - not cached!)
            logger.info(f"Gathering short-term data for {symbol}...")
            short_term_ohlcv_5m_task = self.get_short_term_ohlcv(symbol, interval="5", limit=50)
            short_term_ohlcv_15m_task = self.get_short_term_ohlcv(symbol, interval="15", limit=50)
            trades_flow_task = self.get_recent_trades_flow(symbol)
            liquidations_task = self.get_liquidations(symbol)
            orderbook_delta_task = self.get_orderbook_delta(symbol)
            
            # Wait for short-term tasks
            short_term_ohlcv_5m, short_term_ohlcv_15m, trades_flow, liquidations, orderbook_delta = await asyncio.gather(
                short_term_ohlcv_5m_task,
                short_term_ohlcv_15m_task,
                trades_flow_task,
                liquidations_task,
                orderbook_delta_task,
                return_exceptions=True
            )
            
            # Handle exceptions for short-term data
            if isinstance(short_term_ohlcv_5m, Exception):
                logger.error(f"Error fetching 5m OHLCV: {short_term_ohlcv_5m}")
                short_term_ohlcv_5m = None
            if isinstance(short_term_ohlcv_15m, Exception):
                logger.error(f"Error fetching 15m OHLCV: {short_term_ohlcv_15m}")
                short_term_ohlcv_15m = None
            if isinstance(trades_flow, Exception):
                logger.error(f"Error fetching trades flow: {trades_flow}")
                trades_flow = None
            if isinstance(liquidations, Exception):
                logger.error(f"Error fetching liquidations: {liquidations}")
                liquidations = None
            if isinstance(orderbook_delta, Exception):
                logger.error(f"Error fetching orderbook delta: {orderbook_delta}")
                orderbook_delta = None
            
            # Calculate short-term indicators
            short_term_data = await self.calculate_short_term_indicators(symbol, short_term_ohlcv_5m, short_term_ohlcv_15m)
            
            # ===== MULTI-TIMEFRAME ANALYSIS (NEW) =====
            logger.info(f"Performing multi-timeframe analysis for {symbol}...")
            multi_timeframe_data = await self.multi_timeframe_analyzer.analyze_multi_timeframe(bybit_symbol)
            if multi_timeframe_data:
                logger.info(f"Multi-timeframe consensus: {multi_timeframe_data.get('consensus', {}).get('text', 'N/A')}")
            
            # ===== ADVANCED TECHNICAL INDICATORS (NEW) =====
            logger.info(f"Calculating advanced technical indicators for {symbol}...")
            advanced_indicators = await self.calculate_advanced_indicators(bybit_symbol, ohlcv_data)
            
            # Gather NEW data sources (7 new sources)
            logger.info(f"Gathering new data sources for {symbol}...")
            coinglass_task = self.get_coinglass_data(symbol)
            news_task = self.get_crypto_news_sentiment(symbol)
            tradingview_task = self.get_tradingview_rating(symbol)
            whale_alert_task = self.get_whale_alert_transactions(symbol)
            social_task = self.get_lunarcrush_data(symbol)
            
            # Wait for new data sources
            coinglass_data, news_sentiment, tradingview_rating, whale_alert, social_data = await asyncio.gather(
                coinglass_task,
                news_task,
                tradingview_task,
                whale_alert_task,
                social_task,
                return_exceptions=True
            )
            
            # Handle exceptions for new data sources
            if isinstance(coinglass_data, Exception):
                logger.error(f"Error fetching Coinglass data: {coinglass_data}")
                coinglass_data = None
            if isinstance(news_sentiment, Exception):
                logger.error(f"Error fetching news sentiment: {news_sentiment}")
                news_sentiment = None
            if isinstance(tradingview_rating, Exception):
                logger.error(f"Error fetching TradingView rating: {tradingview_rating}")
                tradingview_rating = None
            if isinstance(whale_alert, Exception):
                logger.error(f"Error fetching Whale Alert: {whale_alert}")
                whale_alert = None
            if isinstance(social_data, Exception):
                logger.error(f"Error fetching social data: {social_data}")
                social_data = None
            
            # ===== DEEP WHALE ANALYSIS (Phase 2) =====
            logger.info(f"Gathering deep whale analysis for {symbol}...")
            deep_whale_data = {}
            try:
                # Get detailed exchange flows
                exchange_flows_detailed = await self.deep_whale_analyzer.get_exchange_flows_detailed(
                    symbol, self.whale_tracker
                )
                deep_whale_data["exchange_flows_detailed"] = exchange_flows_detailed
                
                # Get accumulation/distribution phase
                if whale_data and whale_data.get("transactions"):
                    accumulation_distribution = self.deep_whale_analyzer.detect_accumulation_distribution(
                        whale_data["transactions"]
                    )
                    deep_whale_data["accumulation_distribution"] = accumulation_distribution
                
                # Get stablecoin flows (ETH only for now, as it's on Ethereum)
                if symbol == "ETH":
                    stablecoin_flows = await self.deep_whale_analyzer.get_stablecoin_flows()
                    deep_whale_data["stablecoin_flows"] = stablecoin_flows
                
                logger.info(f"Deep whale analysis collected for {symbol}")
            except Exception as e:
                logger.error(f"Error in deep whale analysis: {e}")
                deep_whale_data = None
            
            # ===== DEEP DERIVATIVES ANALYSIS (Phase 2) =====
            logger.info(f"Gathering deep derivatives analysis for {symbol}...")
            deep_derivatives_data = {}
            try:
                # Get OI/Price correlation
                oi_correlation = await self.deep_derivatives_analyzer.analyze_oi_price_correlation(bybit_symbol)
                deep_derivatives_data["oi_price_correlation"] = oi_correlation
                
                # Get liquidation levels
                liquidation_levels = await self.deep_derivatives_analyzer.get_liquidation_levels(bybit_symbol)
                deep_derivatives_data["liquidation_levels"] = liquidation_levels
                
                # Get L/S ratio by exchange
                ls_ratio = await self.deep_derivatives_analyzer.get_ls_ratio_by_exchange(bybit_symbol)
                deep_derivatives_data["ls_ratio_by_exchange"] = ls_ratio
                
                # Get funding rate history
                funding_history = await self.deep_derivatives_analyzer.get_funding_rate_history(bybit_symbol)
                deep_derivatives_data["funding_rate_history"] = funding_history
                
                # Get basis (futures/spot spread)
                basis = await self.deep_derivatives_analyzer.get_basis(bybit_symbol)
                deep_derivatives_data["basis"] = basis
                
                logger.info(f"Deep derivatives analysis collected for {symbol}")
            except Exception as e:
                logger.error(f"Error in deep derivatives analysis: {e}")
                deep_derivatives_data = None
            
            # ===== MACRO ANALYSIS (Phase 3.1) =====
            logger.info(f"Collecting macro analysis...")
            macro_data = await self.get_macro_data()
            
            # ===== OPTIONS ANALYSIS (Phase 3.2) =====
            logger.info(f"Collecting options analysis for {symbol}...")
            options_data = await self.get_options_data(symbol)
            
            # ===== SOCIAL SENTIMENT (Phase 3.3) =====
            logger.info(f"Collecting social sentiment for {symbol}...")
            sentiment_data = await self.get_sentiment_data(symbol)
            
            # Log data availability
            data_sources_available = {
                "whale_data": whale_data is not None and whale_data.get("transaction_count", 0) > 0,
                "market_data": market_data is not None,
                "technical_data": technical_data is not None,
                "fear_greed": fear_greed is not None,
                "funding_rate": funding_rate is not None,
                "order_book": order_book is not None,
                "trades": trades is not None,
                "futures_data": futures_data is not None,
                "onchain_data": onchain_data is not None,
                "exchange_flows": exchange_flows is not None,
                # Short-term
                "short_term_data": short_term_data is not None,
                "trades_flow": trades_flow is not None,
                "liquidations": liquidations is not None,
                "orderbook_delta": orderbook_delta is not None,
                # New sources
                "coinglass_data": coinglass_data is not None,
                "news_sentiment": news_sentiment is not None,
                "tradingview_rating": tradingview_rating is not None,
                "whale_alert": whale_alert is not None,
                "social_data": social_data is not None,
            }
            available_count = sum(1 for v in data_sources_available.values() if v)
            total_sources = len(data_sources_available)
            logger.info(f"Data sources available: {available_count}/{total_sources} for {symbol}")
            
            # Calculate signal with all available data (30-factor system)
            signal_data = await self.calculate_signal(
                symbol=symbol,
                whale_data=whale_data,
                market_data=market_data,
                technical_data=technical_data,
                fear_greed=fear_greed,
                funding_rate=funding_rate,
                order_book=order_book,
                trades=trades,
                futures_data=futures_data,
                onchain_data=onchain_data,
                exchange_flows=exchange_flows,
                ohlcv_data=ohlcv_data,
                # Short-term data
                short_term_data=short_term_data,
                trades_flow=trades_flow,
                liquidations=liquidations,
                orderbook_delta=orderbook_delta,
                # New data sources
                coinglass_data=coinglass_data,
                news_sentiment=news_sentiment,
                tradingview_rating=tradingview_rating,
                whale_alert=whale_alert,
                social_data=social_data,
                # Deep analysis (Phase 2)
                deep_whale_data=deep_whale_data,
                deep_derivatives_data=deep_derivatives_data,
                # Macro analysis (Phase 3.1)
                macro_data=macro_data,
                # Options analysis (Phase 3.2)
                options_data=options_data,
                # Social sentiment (Phase 3.3)
                sentiment_data=sentiment_data
            )
            
            # Store signal data for later retrieval (prevents second pass)
            self._last_signal_data[symbol] = {
                'signal_data': signal_data,
                'market_data': market_data,
                'timestamp': time.time()
            }
            
            # Format message with COMPACT formatter (15-20 lines)
            message = self.format_signal_message_compact(
                symbol=symbol,
                signal_data=signal_data,
                market_data=market_data,
                technical_data=technical_data,
                fear_greed=fear_greed,
                funding_rate=funding_rate,
                deep_derivatives_data=deep_derivatives_data
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return (
                "❌ *Ошибка анализа*\n\n"
                f"Произошла ошибка при анализе {symbol}.\n"
                "Попробуйте позже."
            )
    
    async def get_signal_params(self, symbol: str) -> dict:
        """
        Получить параметры сигнала для отслеживания.
        
        ВАЖНО: Этот метод использует кэшированные данные из последнего вызова analyze_coin(),
        чтобы избежать повторного анализа (который может дать другой результат).
        
        Returns:
            {
                "direction": "long",
                "entry_price": 50000.0,
                "target1_price": 50750.0,
                "target2_price": 51000.0,
                "stop_loss_price": 49700.0,
                "probability": 65.0
            }
        """
        symbol = symbol.upper()
        
        try:
            # Проверяем, есть ли сохраненные данные из предыдущего analyze_coin()
            last_signal = self._last_signal_data.get(symbol)
            
            if last_signal:
                # Проверяем, не устарели ли данные (макс 5 минут)
                age = time.time() - last_signal.get('timestamp', 0)
                if age < 300:  # 5 минут
                    # Используем сохраненные данные вместо повторного анализа
                    signal_data = last_signal['signal_data']
                    market_data = last_signal['market_data']
                    
                    current_price = market_data['price_usd']
                    raw_direction = signal_data.get('raw_direction', 'sideways')
                    probability = signal_data.get('probability', 50.0)
                    
                    # Получаем TP/SL из signal_data если есть
                    sr_levels = signal_data.get('sr_levels', {})
                    resistances = sr_levels.get('resistances', [])
                    supports = sr_levels.get('supports', [])
                    
                    # Рассчитываем цены TP и SL
                    if raw_direction == "sideways":
                        tp1_price = current_price * (1 + self.SIDEWAYS_RANGE_PERCENT / 100)
                        tp2_price = current_price * (1 + self.SIDEWAYS_RANGE_PERCENT / 100)
                        sl_price = current_price * (1 - self.SIDEWAYS_RANGE_PERCENT / 100)
                    elif raw_direction == "long":
                        # Используем реальные уровни если доступны
                        if resistances:
                            tp1_price = resistances[0]['price']
                            tp2_price = resistances[1]['price'] if len(resistances) > 1 else current_price * (1 + 2.0 / 100)
                        else:
                            tp1_price = current_price * (1 + 1.5 / 100)
                            tp2_price = current_price * (1 + 2.0 / 100)
                        
                        if supports:
                            sl_price = supports[0]['price'] * 0.995  # Немного ниже поддержки
                        else:
                            sl_price = current_price * (1 - 0.6 / 100)
                    else:  # short
                        # Используем реальные уровни если доступны
                        if supports:
                            tp1_price = supports[0]['price']
                            tp2_price = supports[1]['price'] if len(supports) > 1 else current_price * (1 - 2.0 / 100)
                        else:
                            tp1_price = current_price * (1 - 1.5 / 100)
                            tp2_price = current_price * (1 - 2.0 / 100)
                        
                        if resistances:
                            sl_price = resistances[0]['price'] * 1.005  # Немного выше сопротивления
                        else:
                            sl_price = current_price * (1 + 0.6 / 100)
                    
                    logger.info(f"Using cached signal data for {symbol} (age: {age:.0f}s)")
                    
                    return {
                        "direction": raw_direction,
                        "entry_price": current_price,
                        "target1_price": tp1_price,
                        "target2_price": tp2_price,
                        "stop_loss_price": sl_price,
                        "probability": probability
                    }
            
            # Если нет сохраненных данных, делаем упрощенный анализ (fallback)
            logger.warning(f"No cached signal data for {symbol}, falling back to simplified analysis")
            
            # Получаем рыночные данные для цены
            market_data = await self.get_market_data(symbol)
            if market_data is None:
                logger.error(f"Could not get market data for {symbol}")
                return None
            
            current_price = market_data['price_usd']
            
            # Получаем сигнал (без whale данных для скорости)
            # Используем минимальный набор данных
            whale_data = {
                "transaction_count": 0,
                "total_volume_usd": 0,
                "deposits": 0,
                "withdrawals": 0,
                "largest_transaction": 0,
                "sentiment": "neutral"
            }
            
            # Получаем OHLCV для технического анализа
            try:
                ohlcv_data = await self.data_source_manager.get_ohlcv_data(symbol, limit=100)
            except Exception as e:
                logger.warning(f"Failed to get OHLCV data for {symbol}: {e}")
                ohlcv_data = None
            technical_data = await self.calculate_technical_indicators(symbol, ohlcv_data)
            
            # Рассчитываем сигнал (упрощенный)
            signal_data = await self.calculate_signal(
                symbol=symbol,
                whale_data=whale_data,
                market_data=market_data,
                technical_data=technical_data,
                fear_greed=None,
                funding_rate=None,
                order_book=None,
                trades=None,
                futures_data=None,
                onchain_data=None,
                exchange_flows=None,
                ohlcv_data=ohlcv_data,
                short_term_data=None,
                trades_flow=None,
                liquidations=None,
                orderbook_delta=None,
                coinglass_data=None,
                news_sentiment=None,
                tradingview_rating=None,
                whale_alert=None,
                social_data=None,
                deep_whale_data=None,
                deep_derivatives_data=None,
                macro_data=None,
                options_data=None,
                sentiment_data=None
            )
            
            # Извлекаем направление и вероятность
            raw_direction = signal_data.get('raw_direction', 'sideways')
            probability = signal_data.get('probability', 50.0)
            
            # Рассчитываем цены TP и SL
            if raw_direction == "sideways":
                # For sideways, targets represent range bounds (not separate targets)
                tp1_price = current_price * (1 + self.SIDEWAYS_RANGE_PERCENT / 100)  # Upper bound
                tp2_price = current_price * (1 + self.SIDEWAYS_RANGE_PERCENT / 100)  # Same as tp1 for sideways
                sl_price = current_price * (1 - self.SIDEWAYS_RANGE_PERCENT / 100)   # Lower bound
            elif raw_direction == "long":
                tp1_price = current_price * (1 + 1.5 / 100)  # +1.5%
                tp2_price = current_price * (1 + 2.0 / 100)  # +2.0%
                sl_price = current_price * (1 - 0.6 / 100)   # -0.6%
            else:  # short
                tp1_price = current_price * (1 - 1.5 / 100)  # -1.5%
                tp2_price = current_price * (1 - 2.0 / 100)  # -2.0%
                sl_price = current_price * (1 + 0.6 / 100)   # +0.6%
            
            return {
                "direction": raw_direction,
                "entry_price": current_price,
                "target1_price": tp1_price,
                "target2_price": tp2_price,
                "stop_loss_price": sl_price,
                "probability": probability
            }
            
        except Exception as e:
            logger.error(f"Error getting signal params for {symbol}: {e}", exc_info=True)
            return None
