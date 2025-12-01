"""
Gheezy Crypto - Технические индикаторы

Расчёт RSI, MACD, Bollinger Bands и других индикаторов.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class RSI:
    """
    Relative Strength Index (RSI).
    
    Индикатор относительной силы для определения
    перекупленности/перепроданности актива.
    
    Attributes:
        value: Значение RSI (0-100)
        period: Период расчёта
    """

    value: float
    period: int = 14

    @property
    def signal(self) -> str:
        """
        Получение торгового сигнала на основе RSI.
        
        Returns:
            str: 'oversold' (перепродан), 'overbought' (перекуплен), или 'neutral'
        """
        if self.value < 30:
            return "oversold"
        elif self.value > 70:
            return "overbought"
        return "neutral"

    @property
    def explanation(self) -> str:
        """
        Объяснение текущего значения RSI на русском.
        
        Returns:
            str: Человекочитаемое объяснение
        """
        if self.value < 30:
            return f"📉 RSI = {self.value:.1f}: Актив перепродан. Возможен разворот вверх."
        elif self.value > 70:
            return f"📈 RSI = {self.value:.1f}: Актив перекуплен. Возможна коррекция вниз."
        elif self.value < 45:
            return f"📊 RSI = {self.value:.1f}: Слабый спрос, ближе к зоне перепроданности."
        elif self.value > 55:
            return f"📊 RSI = {self.value:.1f}: Хороший спрос, ближе к зоне перекупленности."
        return f"📊 RSI = {self.value:.1f}: Нейтральная зона, рынок в равновесии."


@dataclass
class MACD:
    """
    Moving Average Convergence Divergence (MACD).
    
    Индикатор схождения/расхождения скользящих средних
    для определения тренда и импульса.
    
    Attributes:
        macd_line: Линия MACD
        signal_line: Сигнальная линия
        histogram: Гистограмма (разница между MACD и сигнальной линией)
    """

    macd_line: float
    signal_line: float
    histogram: float

    @property
    def signal(self) -> str:
        """
        Получение торгового сигнала на основе MACD.
        
        Returns:
            str: 'bullish' (бычий), 'bearish' (медвежий), или 'neutral'
        """
        if self.histogram > 0 and self.macd_line > self.signal_line:
            return "bullish"
        elif self.histogram < 0 and self.macd_line < self.signal_line:
            return "bearish"
        return "neutral"

    @property
    def explanation(self) -> str:
        """
        Объяснение текущего состояния MACD на русском.
        
        Returns:
            str: Человекочитаемое объяснение
        """
        if self.histogram > 0:
            strength = "сильный" if abs(self.histogram) > 0.5 else "умеренный"
            return f"🟢 MACD: {strength.capitalize()} бычий сигнал. Гистограмма: +{self.histogram:.4f}"
        elif self.histogram < 0:
            strength = "сильный" if abs(self.histogram) > 0.5 else "умеренный"
            return f"🔴 MACD: {strength.capitalize()} медвежий сигнал. Гистограмма: {self.histogram:.4f}"
        return "⚪ MACD: Нейтральный сигнал, ожидаем пересечения."


@dataclass
class BollingerBands:
    """
    Bollinger Bands (Полосы Боллинджера).
    
    Индикатор волатильности и потенциальных точек разворота.
    
    Attributes:
        upper: Верхняя полоса
        middle: Средняя полоса (SMA)
        lower: Нижняя полоса
        current_price: Текущая цена
    """

    upper: float
    middle: float
    lower: float
    current_price: float

    @property
    def position(self) -> str:
        """
        Определение позиции цены относительно полос.
        
        Returns:
            str: 'above_upper', 'below_lower', 'upper_half', 'lower_half'
        """
        if self.current_price > self.upper:
            return "above_upper"
        elif self.current_price < self.lower:
            return "below_lower"
        elif self.current_price > self.middle:
            return "upper_half"
        return "lower_half"

    @property
    def bandwidth(self) -> float:
        """
        Расчёт ширины полос (волатильность).
        
        Returns:
            float: Ширина полос в процентах
        """
        return ((self.upper - self.lower) / self.middle) * 100

    @property
    def percent_b(self) -> float:
        """
        Расчёт %B (положение цены в диапазоне полос).
        
        Returns:
            float: Значение от 0 до 1 (может выходить за пределы)
        """
        band_range = self.upper - self.lower
        if band_range == 0:
            return 0.5
        return (self.current_price - self.lower) / band_range

    @property
    def explanation(self) -> str:
        """
        Объяснение текущего положения относительно полос Боллинджера.
        
        Returns:
            str: Человекочитаемое объяснение
        """
        position = self.position
        bandwidth = self.bandwidth

        if position == "above_upper":
            return (
                f"⬆️ BB: Цена выше верхней полосы. "
                f"Возможна перекупленность. Волатильность: {bandwidth:.1f}%"
            )
        elif position == "below_lower":
            return (
                f"⬇️ BB: Цена ниже нижней полосы. "
                f"Возможна перепроданность. Волатильность: {bandwidth:.1f}%"
            )
        elif position == "upper_half":
            return (
                f"📈 BB: Цена в верхней половине канала. "
                f"Бычий настрой. Волатильность: {bandwidth:.1f}%"
            )
        return (
            f"📉 BB: Цена в нижней половине канала. "
            f"Медвежий настрой. Волатильность: {bandwidth:.1f}%"
        )


def calculate_rsi(
    prices: List[float],
    period: int = 14,
) -> Optional[RSI]:
    """
    Расчёт индикатора RSI.
    
    Args:
        prices: Список цен закрытия
        period: Период расчёта (по умолчанию 14)
    
    Returns:
        RSI: Объект с рассчитанным RSI или None если недостаточно данных
    """
    if len(prices) < period + 1:
        return None

    prices_array = np.array(prices)
    deltas = np.diff(prices_array)

    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        rsi_value = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_value = 100 - (100 / (1 + rs))

    return RSI(value=float(rsi_value), period=period)


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Optional[MACD]:
    """
    Расчёт индикатора MACD.
    
    Args:
        prices: Список цен закрытия
        fast_period: Быстрый период EMA (по умолчанию 12)
        slow_period: Медленный период EMA (по умолчанию 26)
        signal_period: Период сигнальной линии (по умолчанию 9)
    
    Returns:
        MACD: Объект с рассчитанным MACD или None если недостаточно данных
    """
    if len(prices) < slow_period + signal_period:
        return None

    prices_array = np.array(prices)

    def ema(data: np.ndarray, period: int) -> np.ndarray:
        """Расчёт экспоненциальной скользящей средней."""
        alpha = 2 / (period + 1)
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    ema_fast = ema(prices_array, fast_period)
    ema_slow = ema(prices_array, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line

    return MACD(
        macd_line=float(macd_line[-1]),
        signal_line=float(signal_line[-1]),
        histogram=float(histogram[-1]),
    )


def calculate_bollinger_bands(
    prices: List[float],
    period: int = 20,
    num_std: float = 2.0,
) -> Optional[BollingerBands]:
    """
    Расчёт полос Боллинджера.
    
    Args:
        prices: Список цен закрытия
        period: Период SMA (по умолчанию 20)
        num_std: Количество стандартных отклонений (по умолчанию 2)
    
    Returns:
        BollingerBands: Объект с полосами или None если недостаточно данных
    """
    if len(prices) < period:
        return None

    prices_array = np.array(prices[-period:])
    middle = float(np.mean(prices_array))
    std = float(np.std(prices_array))

    return BollingerBands(
        upper=middle + (num_std * std),
        middle=middle,
        lower=middle - (num_std * std),
        current_price=prices[-1],
    )


def calculate_all_indicators(
    prices: List[float],
) -> Tuple[Optional[RSI], Optional[MACD], Optional[BollingerBands]]:
    """
    Расчёт всех технических индикаторов.
    
    Args:
        prices: Список цен закрытия
    
    Returns:
        Tuple: (RSI, MACD, BollingerBands) - любой может быть None
    """
    rsi = calculate_rsi(prices)
    macd = calculate_macd(prices)
    bb = calculate_bollinger_bands(prices)

    return rsi, macd, bb
