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
            return (
                f"📉 RSI = {self.value:.1f}: Актив перепродан. Возможен разворот вверх."
            )
        elif self.value > 70:
            return (
                f"📈 RSI = {self.value:.1f}: Актив перекуплен. Возможна коррекция вниз."
            )
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


@dataclass
class StochasticRSI:
    """
    Stochastic RSI индикатор.
    
    Комбинирует Stochastic осциллятор и RSI для определения
    перекупленности/перепроданности с большей чувствительностью.
    
    Attributes:
        k: %K линия (0-100)
        d: %D линия (0-100)
        signal: Торговый сигнал
    """
    k: float
    d: float
    
    @property
    def signal(self) -> str:
        """
        Получение торгового сигнала.
        
        Returns:
            str: 'oversold', 'overbought', 'bullish', 'bearish'
        """
        if self.k < 20:
            return "oversold"
        elif self.k > 80:
            return "overbought"
        elif self.k > self.d and self.k < 50:
            return "bullish"
        elif self.k < self.d and self.k > 50:
            return "bearish"
        return "neutral"


@dataclass
class MFI:
    """
    Money Flow Index (MFI).
    
    Индикатор денежного потока, учитывающий цену и объём.
    
    Attributes:
        value: Значение MFI (0-100)
        signal: Торговый сигнал
    """
    value: float
    
    @property
    def signal(self) -> str:
        """
        Получение торгового сигнала.
        
        Returns:
            str: 'oversold', 'overbought', 'neutral'
        """
        if self.value < 20:
            return "oversold"
        elif self.value > 80:
            return "overbought"
        return "neutral"


@dataclass
class OBV:
    """
    On-Balance Volume (OBV).
    
    Индикатор накопительного объёма для определения давления покупателей/продавцов.
    
    Attributes:
        value: Текущее значение OBV
        trend: Тренд OBV
    """
    value: float
    
    @property
    def trend(self) -> str:
        """
        Определение тренда.
        Примечание: Требует исторических данных для точного определения.
        
        Returns:
            str: 'rising', 'falling', 'flat'
        """
        # Базовое определение, требует дополнительной логики
        return "neutral"


@dataclass
class ATR:
    """
    Average True Range (ATR).
    
    Индикатор волатильности рынка.
    
    Attributes:
        value: Значение ATR
        percent: ATR в процентах от цены
    """
    value: float
    percent: float
    
    @property
    def volatility(self) -> str:
        """
        Классификация волатильности.
        
        Returns:
            str: 'low', 'medium', 'high'
        """
        if self.percent < 2:
            return "low"
        elif self.percent < 5:
            return "medium"
        return "high"


@dataclass
class WilliamsR:
    """
    Williams %R индикатор.
    
    Индикатор импульса, показывающий уровень закрытия относительно
    максимума-минимума за период.
    
    Attributes:
        value: Значение Williams %R (-100 до 0)
        signal: Торговый сигнал
    """
    value: float
    
    @property
    def signal(self) -> str:
        """
        Получение торгового сигнала.
        
        Returns:
            str: 'oversold', 'overbought', 'neutral'
        """
        if self.value < -80:
            return "oversold"
        elif self.value > -20:
            return "overbought"
        return "neutral"


@dataclass
class PivotPoints:
    """
    Pivot Points (Точки разворота).
    
    Уровни поддержки и сопротивления на основе предыдущих цен.
    
    Attributes:
        pivot: Центральная точка разворота
        r1, r2: Уровни сопротивления
        s1, s2: Уровни поддержки
    """
    pivot: float
    r1: float
    r2: float
    s1: float
    s2: float


@dataclass
class ROC:
    """
    Rate of Change (ROC).
    
    Индикатор скорости изменения цены.
    
    Attributes:
        value: Значение ROC в процентах
        momentum: Характеристика импульса
    """
    value: float
    
    @property
    def momentum(self) -> str:
        """
        Определение импульса.
        
        Returns:
            str: 'strong_positive', 'positive', 'negative', 'strong_negative', 'neutral'
        """
        if self.value > 5:
            return "strong_positive"
        elif self.value > 1:
            return "positive"
        elif self.value < -5:
            return "strong_negative"
        elif self.value < -1:
            return "negative"
        return "neutral"


def calculate_stochastic_rsi(
    prices: List[float],
    period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3
) -> Optional[StochasticRSI]:
    """
    Расчёт Stochastic RSI.
    
    Args:
        prices: Список цен закрытия
        period: Период RSI
        smooth_k: Период сглаживания %K
        smooth_d: Период сглаживания %D
    
    Returns:
        StochasticRSI или None если недостаточно данных
    """
    if len(prices) < period + smooth_k + smooth_d:
        return None
    
    # Расчёт RSI для каждой точки
    rsi_values = []
    for i in range(period, len(prices)):
        window = prices[i-period:i+1]
        rsi_obj = calculate_rsi(window, period)
        if rsi_obj:
            rsi_values.append(rsi_obj.value)
    
    if len(rsi_values) < smooth_k + smooth_d:
        return None
    
    # Stochastic на RSI
    rsi_array = np.array(rsi_values)
    
    stoch_rsi = []
    for i in range(period, len(rsi_array)):
        window = rsi_array[i-period:i+1]
        lowest = np.min(window)
        highest = np.max(window)
        
        if highest - lowest == 0:
            stoch_rsi.append(0)
        else:
            stoch_rsi.append((rsi_array[i] - lowest) / (highest - lowest) * 100)
    
    if len(stoch_rsi) < smooth_k + smooth_d:
        return None
    
    # Сглаживание %K
    k_array = np.array(stoch_rsi)
    k_value = float(np.mean(k_array[-smooth_k:]))
    
    # Сглаживание %D
    if len(stoch_rsi) >= smooth_d:
        d_value = float(np.mean(k_array[-smooth_d:]))
    else:
        d_value = k_value
    
    return StochasticRSI(k=k_value, d=d_value)


def calculate_mfi(
    high: List[float],
    low: List[float],
    close: List[float],
    volume: List[float],
    period: int = 14
) -> Optional[MFI]:
    """
    Расчёт Money Flow Index.
    
    Args:
        high: Список максимумов
        low: Список минимумов
        close: Список цен закрытия
        volume: Список объёмов
        period: Период расчёта
    
    Returns:
        MFI или None если недостаточно данных
    """
    if len(high) < period + 1 or len(high) != len(low) != len(close) != len(volume):
        return None
    
    # Типичная цена
    typical_price = np.array([(h + l + c) / 3 for h, l, c in zip(high, low, close)])
    
    # Денежный поток
    money_flow = typical_price * np.array(volume)
    
    # Положительный и отрицательный денежный поток
    positive_flow = []
    negative_flow = []
    
    for i in range(1, len(typical_price)):
        if typical_price[i] > typical_price[i-1]:
            positive_flow.append(money_flow[i])
            negative_flow.append(0)
        elif typical_price[i] < typical_price[i-1]:
            positive_flow.append(0)
            negative_flow.append(money_flow[i])
        else:
            positive_flow.append(0)
            negative_flow.append(0)
    
    if len(positive_flow) < period:
        return None
    
    # Сумма за период
    positive_sum = sum(positive_flow[-period:])
    negative_sum = sum(negative_flow[-period:])
    
    if negative_sum == 0:
        mfi_value = 100.0
    else:
        money_ratio = positive_sum / negative_sum
        mfi_value = 100 - (100 / (1 + money_ratio))
    
    return MFI(value=float(mfi_value))


def calculate_obv(close: List[float], volume: List[float]) -> Optional[OBV]:
    """
    Расчёт On-Balance Volume.
    
    Args:
        close: Список цен закрытия
        volume: Список объёмов
    
    Returns:
        OBV или None если недостаточно данных
    """
    if len(close) < 2 or len(close) != len(volume):
        return None
    
    obv_value = 0.0
    
    for i in range(1, len(close)):
        if close[i] > close[i-1]:
            obv_value += volume[i]
        elif close[i] < close[i-1]:
            obv_value -= volume[i]
    
    return OBV(value=float(obv_value))


def calculate_atr(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 14
) -> Optional[ATR]:
    """
    Расчёт Average True Range.
    
    Args:
        high: Список максимумов
        low: Список минимумов
        close: Список цен закрытия
        period: Период расчёта
    
    Returns:
        ATR или None если недостаточно данных
    """
    if len(high) < period + 1 or len(high) != len(low) != len(close):
        return None
    
    true_ranges = []
    
    for i in range(1, len(high)):
        tr1 = high[i] - low[i]
        tr2 = abs(high[i] - close[i-1])
        tr3 = abs(low[i] - close[i-1])
        true_ranges.append(max(tr1, tr2, tr3))
    
    if len(true_ranges) < period:
        return None
    
    atr_value = float(np.mean(true_ranges[-period:]))
    current_price = close[-1]
    atr_percent = (atr_value / current_price) * 100 if current_price > 0 else 0
    
    return ATR(value=atr_value, percent=float(atr_percent))


def calculate_williams_r(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 14
) -> Optional[WilliamsR]:
    """
    Расчёт Williams %R.
    
    Args:
        high: Список максимумов
        low: Список минимумов
        close: Список цен закрытия
        period: Период расчёта
    
    Returns:
        WilliamsR или None если недостаточно данных
    """
    if len(high) < period or len(high) != len(low) != len(close):
        return None
    
    highest_high = max(high[-period:])
    lowest_low = min(low[-period:])
    current_close = close[-1]
    
    if highest_high - lowest_low == 0:
        williams_value = -50.0
    else:
        williams_value = ((highest_high - current_close) / (highest_high - lowest_low)) * -100
    
    return WilliamsR(value=float(williams_value))


def calculate_pivot_points(
    high: float,
    low: float,
    close: float
) -> PivotPoints:
    """
    Расчёт Pivot Points.
    
    Args:
        high: Максимум предыдущего периода
        low: Минимум предыдущего периода
        close: Закрытие предыдущего периода
    
    Returns:
        PivotPoints с уровнями поддержки и сопротивления
    """
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    r2 = pivot + (high - low)
    s1 = (2 * pivot) - high
    s2 = pivot - (high - low)
    
    return PivotPoints(
        pivot=float(pivot),
        r1=float(r1),
        r2=float(r2),
        s1=float(s1),
        s2=float(s2)
    )


def calculate_roc(prices: List[float], period: int = 12) -> Optional[ROC]:
    """
    Расчёт Rate of Change.
    
    Args:
        prices: Список цен закрытия
        period: Период расчёта
    
    Returns:
        ROC или None если недостаточно данных
    """
    if len(prices) < period + 1:
        return None
    
    current_price = prices[-1]
    past_price = prices[-period-1]
    
    if past_price == 0:
        return None
    
    roc_value = ((current_price - past_price) / past_price) * 100
    
    return ROC(value=float(roc_value))
