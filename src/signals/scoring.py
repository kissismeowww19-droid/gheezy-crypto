"""
Scoring Module - расчёт различных score для Smart Signals.
"""

import logging
from typing import Dict, List
import numpy as np

logger = logging.getLogger(__name__)


def clamp(value: float, min_val: float = 0, max_val: float = 10) -> float:
    """
    Ограничивает значение в диапазоне.
    
    Args:
        value: Значение для ограничения
        min_val: Минимальное значение
        max_val: Максимальное значение
        
    Returns:
        Ограниченное значение
    """
    return max(min_val, min(max_val, value))


def normalize_to_range(value: float, min_input: float, max_input: float, 
                       min_output: float = 0, max_output: float = 10) -> float:
    """
    Нормализует значение из одного диапазона в другой.
    
    Args:
        value: Значение для нормализации
        min_input: Минимум входного диапазона
        max_input: Максимум входного диапазона
        min_output: Минимум выходного диапазона
        max_output: Максимум выходного диапазона
        
    Returns:
        Нормализованное значение
    """
    if max_input == min_input:
        return min_output
    
    normalized = ((value - min_input) / (max_input - min_input)) * (max_output - min_output) + min_output
    return clamp(normalized, min_output, max_output)


def calculate_momentum_score(changes: Dict[str, float]) -> float:
    """
    Рассчитывает momentum score на основе изменений цены.
    
    Args:
        changes: Dict с ключами "1h" и "4h" - процентные изменения цены
        
    Returns:
        Momentum score (0-10)
    """
    change_1h = changes.get("1h", 0)
    change_4h = changes.get("4h", 0)
    
    # Нормализуем изменения (предполагаем диапазон -10% до +10%)
    score_1h = normalize_to_range(change_1h, -10, 10, 0, 10)
    score_4h = normalize_to_range(change_4h, -10, 10, 0, 10)
    
    # Взвешенная комбинация
    momentum_score = score_4h * 0.6 + score_1h * 0.4
    
    return clamp(momentum_score, 0, 10)


def calculate_volume_score(volume: float, avg_volume: float) -> float:
    """
    Рассчитывает volume score на основе отношения текущего объёма к среднему.
    
    Args:
        volume: Текущий объём 24h
        avg_volume: Средний объём за последние 20 дней
        
    Returns:
        Volume score (0-10)
    """
    if avg_volume <= 0:
        return 5.0  # Нейтральный score если нет данных
    
    ratio = volume / avg_volume
    
    # Нормализуем отношение (0.5x до 3x)
    score = normalize_to_range(ratio, 0.5, 3.0, 0, 10)
    
    return score


def calculate_trend_score(ema_data: Dict[str, float], adx: float) -> float:
    """
    Рассчитывает trend score на основе EMA crossover и ADX.
    
    Args:
        ema_data: Dict с ключами "ema_short", "ema_long", "price"
        adx: ADX индикатор (0-100)
        
    Returns:
        Trend score (0-10)
    """
    ema_short = ema_data.get("ema_short", 0)
    ema_long = ema_data.get("ema_long", 0)
    price = ema_data.get("price", 0)
    
    # Базовый score на основе позиции EMA
    if ema_long <= 0:
        ema_score = 5.0
    else:
        # Если short > long - бычий тренд
        ema_diff_pct = ((ema_short - ema_long) / ema_long) * 100
        ema_score = normalize_to_range(ema_diff_pct, -5, 5, 0, 10)
    
    # ADX показывает силу тренда (нормализуем 0-100 -> 0-10)
    adx_score = normalize_to_range(adx, 0, 100, 0, 10)
    
    # Комбинируем (направление важнее силы)
    trend_score = ema_score * 0.7 + adx_score * 0.3
    
    return clamp(trend_score, 0, 10)


def calculate_volatility_score(atr_pct: float, bb_width_pct: float) -> float:
    """
    Рассчитывает volatility score на основе ATR и ширины Bollinger Bands.
    
    Args:
        atr_pct: ATR в процентах от цены
        bb_width_pct: Ширина Bollinger Bands в процентах
        
    Returns:
        Volatility score (0-10), где выше = меньше волатильность (лучше)
    """
    # Инвертируем - меньше волатильности = выше score
    # Предполагаем нормальный диапазон ATR 1-5%
    atr_score = normalize_to_range(atr_pct, 5, 1, 0, 10)
    
    # Предполагаем нормальный диапазон BB width 2-10%
    bb_score = normalize_to_range(bb_width_pct, 10, 2, 0, 10)
    
    # Комбинируем
    volatility_score = (atr_score + bb_score) / 2
    
    return clamp(volatility_score, 0, 10)


def calculate_total_score(metrics: Dict[str, float], weights: Dict[str, float]) -> float:
    """
    Рассчитывает итоговый score по формуле с весами.
    
    Args:
        metrics: Dict с метриками (momentum_4h, momentum_1h, volume_ratio, trend_score, volatility_score)
        weights: Dict с весами для каждой метрики
        
    Returns:
        Итоговый score (0-10)
    """
    # Базовый расчёт
    score = 0.0
    
    # Momentum (взвешенный)
    momentum_4h = metrics.get("momentum_4h", 5.0)
    momentum_1h = metrics.get("momentum_1h", 5.0)
    momentum_combined = momentum_4h * 0.6 + momentum_1h * 0.4
    score += momentum_combined * (weights.get("momentum_4h", 0.30) + weights.get("momentum_1h", 0.20))
    
    # Volume ratio
    volume_score = metrics.get("volume_ratio", 5.0)
    score += volume_score * weights.get("volume_ratio", 0.20)
    
    # Trend
    trend_score = metrics.get("trend_score", 5.0)
    score += trend_score * weights.get("trend_score", 0.15)
    
    # Volatility
    volatility_score = metrics.get("volatility_score", 5.0)
    score += volatility_score * weights.get("volatility_score", 0.15)
    
    # Применяем бонусы/штрафы
    bonuses = metrics.get("bonuses", 0)
    penalties = metrics.get("penalties", 0)
    
    score += bonuses - penalties
    
    return clamp(score, 0, 10)


def apply_score_bonuses(
    score: float,
    funding_rate: float,
    oi_change_pct: float,
    price_change_pct: float,
    btc_correlation: float
) -> tuple[float, List[str]]:
    """
    Применяет бонусы и штрафы к score.
    
    Args:
        score: Базовый score
        funding_rate: Funding rate (напр., 0.0001 = 0.01%)
        oi_change_pct: Изменение Open Interest в процентах
        price_change_pct: Изменение цены в процентах
        btc_correlation: Корреляция с BTC (0-1)
        
    Returns:
        Tuple (adjusted_score, list_of_factors)
    """
    adjusted_score = score
    factors = []
    
    # Проверка экстремального funding (перегрев)
    funding_pct = funding_rate * 100
    if abs(funding_pct) > 0.1:  # Больше 0.1%
        adjusted_score -= 1.0
        factors.append(f"⚠️ Экстремальный funding ({funding_pct:.3f}%)")
    
    # Бонус за растущий OI с растущей ценой
    if oi_change_pct > 5 and price_change_pct > 2:
        adjusted_score += 0.5
        factors.append(f"✅ OI растёт с ценой (+{oi_change_pct:.1f}% OI)")
    
    # Штраф за независимое движение от BTC
    if btc_correlation < 0.3:
        adjusted_score -= 0.5
        factors.append(f"⚠️ Слабая корреляция с BTC ({btc_correlation:.2f})")
    
    return clamp(adjusted_score, 0, 10), factors


def calculate_ema(prices: List[float], period: int) -> float:
    """
    Рассчитывает EMA (Exponential Moving Average).
    
    Args:
        prices: Список цен (от старых к новым)
        period: Период EMA
        
    Returns:
        Значение EMA
    """
    if len(prices) < period:
        return np.mean(prices) if prices else 0
    
    prices_array = np.array(prices)
    ema = prices_array[0]
    multiplier = 2 / (period + 1)
    
    for price in prices_array[1:]:
        ema = (price - ema) * multiplier + ema
    
    return float(ema)


def calculate_adx(high: List[float], low: List[float], close: List[float], period: int = 14) -> float:
    """
    Рассчитывает ADX (Average Directional Index).
    
    Args:
        high: Список максимумов
        low: Список минимумов
        close: Список цен закрытия
        period: Период для расчёта
        
    Returns:
        Значение ADX (0-100)
    """
    if len(high) < period + 1 or len(low) < period + 1 or len(close) < period + 1:
        return 25.0  # Нейтральное значение
    
    try:
        # Упрощённый расчёт ADX
        high_arr = np.array(high)
        low_arr = np.array(low)
        close_arr = np.array(close)
        
        # True Range
        tr1 = high_arr[1:] - low_arr[1:]
        tr2 = np.abs(high_arr[1:] - close_arr[:-1])
        tr3 = np.abs(low_arr[1:] - close_arr[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        # Smoothed TR
        atr = np.mean(tr[-period:])
        
        # +DM and -DM
        dm_plus = np.maximum(high_arr[1:] - high_arr[:-1], 0)
        dm_minus = np.maximum(low_arr[:-1] - low_arr[1:], 0)
        
        # Smooth DM
        dm_plus_smooth = np.mean(dm_plus[-period:])
        dm_minus_smooth = np.mean(dm_minus[-period:])
        
        # Directional Indicators
        if atr > 0:
            di_plus = (dm_plus_smooth / atr) * 100
            di_minus = (dm_minus_smooth / atr) * 100
            
            # ADX
            dx = abs(di_plus - di_minus) / (di_plus + di_minus) * 100 if (di_plus + di_minus) > 0 else 0
            return float(dx)
        else:
            return 25.0
    except Exception as e:
        logger.warning(f"ADX calculation error: {e}")
        return 25.0
