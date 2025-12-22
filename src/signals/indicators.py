"""
Gheezy Crypto - Технические индикаторы

Расчёт RSI, MACD, Bollinger Bands и других индикаторов.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


# Constants for indicator calculations
RSI_MAX_VALUE = 100.0
RSI_OVERBOUGHT_THRESHOLD = 70
RSI_OVERSOLD_THRESHOLD = 30


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
        rsi_value = RSI_MAX_VALUE
    else:
        rs = avg_gain / avg_loss
        rsi_value = RSI_MAX_VALUE - (RSI_MAX_VALUE / (1 + rs))

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


@dataclass
class MACrossover:
    """MA Crossover (Golden Cross / Death Cross)."""
    ma_short: float  # MA 50
    ma_long: float   # MA 200
    crossover: str   # "golden_cross", "death_cross", "none"
    trend: str       # "bullish", "bearish"


@dataclass
class StochasticRSI:
    """Stochastic RSI."""
    k: float  # 0-100
    d: float  # 0-100
    signal: str  # "oversold", "overbought", "bullish", "bearish", "neutral"


@dataclass
class MFI:
    """Money Flow Index."""
    value: float  # 0-100
    signal: str   # "oversold", "overbought", "neutral"


@dataclass
class ROC:
    """Rate of Change."""
    value: float
    momentum: str  # "strong_up", "up", "neutral", "down", "strong_down"


@dataclass
class WilliamsR:
    """Williams %R."""
    value: float  # -100 to 0
    signal: str   # "oversold", "overbought", "neutral"


@dataclass
class ATR:
    """Average True Range."""
    value: float
    percent: float  # ATR as % of price
    volatility: str  # "low", "medium", "high", "extreme"


@dataclass
class KeltnerChannels:
    """Keltner Channels."""
    upper: float
    middle: float
    lower: float
    position: str  # "above", "inside", "below"


@dataclass
class OBV:
    """On-Balance Volume."""
    value: float
    trend: str  # "rising", "falling", "flat"
    sma: float  # OBV SMA for comparison


@dataclass
class VWAP:
    """Volume Weighted Average Price."""
    value: float
    position: str  # "above", "below"
    deviation_percent: float


@dataclass
class VolumeSMA:
    """Volume SMA."""
    current_volume: float
    sma: float
    ratio: float  # current/sma
    status: str   # "high", "normal", "low"


@dataclass
class VolumeSpike:
    """Volume Spike Detection."""
    is_spike: bool
    spike_percentage: float  # Percentage above average (e.g., 180 means +180%)
    current_volume: float
    average_volume: float


@dataclass
class PivotPoints:
    """Pivot Points."""
    pivot: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float
    current_zone: str  # "above_r1", "pivot_to_r1", "s1_to_pivot", "below_s1", etc.


@dataclass
class FibonacciLevels:
    """Fibonacci Retracement Levels."""
    level_0: float
    level_236: float
    level_382: float
    level_50: float
    level_618: float
    level_786: float
    level_100: float
    nearest_level: str
    nearest_value: float


def calculate_ma_crossover(prices: List[float], short_period: int = 50, long_period: int = 200) -> Optional[MACrossover]:
    """
    Calculate MA Crossover (Golden Cross / Death Cross).
    
    Args:
        prices: List of closing prices
        short_period: Short MA period (default 50)
        long_period: Long MA period (default 200)
        
    Returns:
        MACrossover or None if insufficient data
    """
    if len(prices) < long_period:
        return None
    
    prices_array = np.array(prices)
    ma_short = float(np.mean(prices_array[-short_period:]))
    ma_long = float(np.mean(prices_array[-long_period:]))
    
    # Check for crossover (compare previous values)
    if len(prices) >= long_period + 1:
        prev_ma_short = float(np.mean(prices_array[-(short_period+1):-1]))
        prev_ma_long = float(np.mean(prices_array[-(long_period+1):-1]))
        
        # Golden Cross: short MA crosses above long MA
        if prev_ma_short <= prev_ma_long and ma_short > ma_long:
            crossover = "golden_cross"
        # Death Cross: short MA crosses below long MA
        elif prev_ma_short >= prev_ma_long and ma_short < ma_long:
            crossover = "death_cross"
        else:
            crossover = "none"
    else:
        crossover = "none"
    
    trend = "bullish" if ma_short > ma_long else "bearish"
    
    return MACrossover(
        ma_short=ma_short,
        ma_long=ma_long,
        crossover=crossover,
        trend=trend
    )


def calculate_stochastic_rsi(prices: List[float], period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Optional[StochasticRSI]:
    """
    Calculate Stochastic RSI.
    
    Args:
        prices: List of closing prices
        period: RSI period
        smooth_k: K smoothing period
        smooth_d: D smoothing period
        
    Returns:
        StochasticRSI or None if insufficient data
    """
    if len(prices) < period + smooth_k + smooth_d:
        return None
    
    # Calculate RSI values
    prices_array = np.array(prices)
    deltas = np.diff(prices_array)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    rsi_values = []
    for i in range(period, len(gains)):
        avg_gain = np.mean(gains[i-period:i])
        avg_loss = np.mean(losses[i-period:i])
        if avg_loss == 0:
            rsi_values.append(RSI_MAX_VALUE)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(RSI_MAX_VALUE - (RSI_MAX_VALUE / (1 + rs)))
    
    if len(rsi_values) < smooth_k:
        return None
    
    rsi_array = np.array(rsi_values)
    
    # Calculate Stochastic RSI
    stoch_rsi = []
    for i in range(smooth_k - 1, len(rsi_array)):
        rsi_window = rsi_array[i-smooth_k+1:i+1]
        rsi_min = np.min(rsi_window)
        rsi_max = np.max(rsi_window)
        if rsi_max - rsi_min == 0:
            stoch_rsi.append(0)
        else:
            stoch_rsi.append((rsi_array[i] - rsi_min) / (rsi_max - rsi_min) * 100)
    
    if len(stoch_rsi) < smooth_d:
        return None
    
    stoch_array = np.array(stoch_rsi)
    k = float(stoch_array[-1])
    d = float(np.mean(stoch_array[-smooth_d:]))
    
    # Determine signal
    if k < 20 and d < 20:
        signal = "oversold"
    elif k > 80 and d > 80:
        signal = "overbought"
    elif k > d:
        signal = "bullish"
    elif k < d:
        signal = "bearish"
    else:
        signal = "neutral"
    
    return StochasticRSI(k=k, d=d, signal=signal)


def calculate_mfi(high: List[float], low: List[float], close: List[float], volume: List[float], period: int = 14) -> Optional[MFI]:
    """
    Calculate Money Flow Index.
    
    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        volume: List of volumes
        period: MFI period
        
    Returns:
        MFI or None if insufficient data
    """
    if len(high) < period + 1 or len(high) != len(low) or len(high) != len(close) or len(high) != len(volume):
        return None
    
    high_array = np.array(high)
    low_array = np.array(low)
    close_array = np.array(close)
    volume_array = np.array(volume)
    
    # Calculate typical price
    typical_price = (high_array + low_array + close_array) / 3
    
    # Calculate raw money flow
    raw_money_flow = typical_price * volume_array
    
    # Identify positive and negative money flow
    positive_flow = []
    negative_flow = []
    
    for i in range(1, len(typical_price)):
        if typical_price[i] > typical_price[i-1]:
            positive_flow.append(raw_money_flow[i])
            negative_flow.append(0)
        elif typical_price[i] < typical_price[i-1]:
            positive_flow.append(0)
            negative_flow.append(raw_money_flow[i])
        else:
            positive_flow.append(0)
            negative_flow.append(0)
    
    if len(positive_flow) < period:
        return None
    
    # Calculate MFI
    positive_mf = sum(positive_flow[-period:])
    negative_mf = sum(negative_flow[-period:])
    
    if negative_mf == 0:
        mfi_value = RSI_MAX_VALUE
    else:
        money_ratio = positive_mf / negative_mf
        mfi_value = RSI_MAX_VALUE - (RSI_MAX_VALUE / (1 + money_ratio))
    
    # Determine signal
    if mfi_value < 20:
        signal = "oversold"
    elif mfi_value > 80:
        signal = "overbought"
    else:
        signal = "neutral"
    
    return MFI(value=float(mfi_value), signal=signal)


def calculate_roc(prices: List[float], period: int = 12) -> Optional[ROC]:
    """
    Calculate Rate of Change.
    
    Args:
        prices: List of closing prices
        period: ROC period
        
    Returns:
        ROC or None if insufficient data
    """
    if len(prices) < period + 1:
        return None
    
    current_price = prices[-1]
    past_price = prices[-(period + 1)]
    
    if past_price == 0:
        return None
    
    roc_value = ((current_price - past_price) / past_price) * 100
    
    # Determine momentum
    if roc_value > 5:
        momentum = "strong_up"
    elif roc_value > 1:
        momentum = "up"
    elif roc_value < -5:
        momentum = "strong_down"
    elif roc_value < -1:
        momentum = "down"
    else:
        momentum = "neutral"
    
    return ROC(value=float(roc_value), momentum=momentum)


def calculate_williams_r(high: List[float], low: List[float], close: List[float], period: int = 14) -> Optional[WilliamsR]:
    """
    Calculate Williams %R.
    
    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        period: Williams %R period
        
    Returns:
        WilliamsR or None if insufficient data
    """
    if len(high) < period or len(high) != len(low) or len(high) != len(close):
        return None
    
    high_array = np.array(high[-period:])
    low_array = np.array(low[-period:])
    current_close = close[-1]
    
    highest_high = np.max(high_array)
    lowest_low = np.min(low_array)
    
    if highest_high - lowest_low == 0:
        williams_value = -50.0
    else:
        williams_value = ((highest_high - current_close) / (highest_high - lowest_low)) * -100
    
    # Determine signal
    if williams_value < -80:
        signal = "oversold"
    elif williams_value > -20:
        signal = "overbought"
    else:
        signal = "neutral"
    
    return WilliamsR(value=float(williams_value), signal=signal)


def calculate_atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> Optional[ATR]:
    """
    Calculate Average True Range.
    
    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        period: ATR period
        
    Returns:
        ATR or None if insufficient data
    """
    if len(high) < period + 1 or len(high) != len(low) or len(high) != len(close):
        return None
    
    high_array = np.array(high)
    low_array = np.array(low)
    close_array = np.array(close)
    
    # Calculate True Range
    tr = []
    for i in range(1, len(high_array)):
        h_l = high_array[i] - low_array[i]
        h_c = abs(high_array[i] - close_array[i-1])
        l_c = abs(low_array[i] - close_array[i-1])
        tr.append(max(h_l, h_c, l_c))
    
    if len(tr) < period:
        return None
    
    atr_value = float(np.mean(tr[-period:]))
    current_price = close[-1]
    atr_percent = (atr_value / current_price) * 100
    
    # Determine volatility
    if atr_percent < 1:
        volatility = "low"
    elif atr_percent < 3:
        volatility = "medium"
    elif atr_percent < 5:
        volatility = "high"
    else:
        volatility = "extreme"
    
    return ATR(value=atr_value, percent=float(atr_percent), volatility=volatility)


def calculate_keltner_channels(high: List[float], low: List[float], close: List[float], period: int = 20, multiplier: float = 2.0) -> Optional[KeltnerChannels]:
    """
    Calculate Keltner Channels.
    
    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        period: EMA period
        multiplier: ATR multiplier
        
    Returns:
        KeltnerChannels or None if insufficient data
    """
    if len(close) < period + 1 or len(high) != len(low) or len(high) != len(close):
        return None
    
    # Calculate EMA
    close_array = np.array(close)
    alpha = 2 / (period + 1)
    ema_values = np.zeros_like(close_array)
    ema_values[0] = close_array[0]
    for i in range(1, len(close_array)):
        ema_values[i] = alpha * close_array[i] + (1 - alpha) * ema_values[i - 1]
    
    middle = float(ema_values[-1])
    
    # Calculate ATR
    atr_result = calculate_atr(high, low, close, period)
    if not atr_result:
        return None
    
    atr_value = atr_result.value
    
    upper = middle + (multiplier * atr_value)
    lower = middle - (multiplier * atr_value)
    current_price = close[-1]
    
    # Determine position
    if current_price > upper:
        position = "above"
    elif current_price < lower:
        position = "below"
    else:
        position = "inside"
    
    return KeltnerChannels(upper=upper, middle=middle, lower=lower, position=position)


def calculate_obv(close: List[float], volume: List[float]) -> Optional[OBV]:
    """
    Calculate On-Balance Volume.
    
    Args:
        close: List of closing prices
        volume: List of volumes
        
    Returns:
        OBV or None if insufficient data
    """
    if len(close) < 20 or len(close) != len(volume):
        return None
    
    close_array = np.array(close)
    volume_array = np.array(volume)
    
    obv_values = [0.0]
    for i in range(1, len(close_array)):
        if close_array[i] > close_array[i-1]:
            obv_values.append(obv_values[-1] + volume_array[i])
        elif close_array[i] < close_array[i-1]:
            obv_values.append(obv_values[-1] - volume_array[i])
        else:
            obv_values.append(obv_values[-1])
    
    obv_value = float(obv_values[-1])
    obv_sma = float(np.mean(obv_values[-20:]))
    
    # Determine trend
    if len(obv_values) >= 10:
        recent_obv = obv_values[-10:]
        if recent_obv[-1] > recent_obv[0] * 1.05:
            trend = "rising"
        elif recent_obv[-1] < recent_obv[0] * 0.95:
            trend = "falling"
        else:
            trend = "flat"
    else:
        trend = "flat"
    
    return OBV(value=obv_value, trend=trend, sma=obv_sma)


def calculate_vwap(high: List[float], low: List[float], close: List[float], volume: List[float]) -> Optional[VWAP]:
    """
    Calculate Volume Weighted Average Price.
    
    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        volume: List of volumes
        
    Returns:
        VWAP or None if insufficient data
    """
    if len(high) < 1 or len(high) != len(low) or len(high) != len(close) or len(high) != len(volume):
        return None
    
    high_array = np.array(high)
    low_array = np.array(low)
    close_array = np.array(close)
    volume_array = np.array(volume)
    
    # Calculate typical price
    typical_price = (high_array + low_array + close_array) / 3
    
    # Calculate VWAP
    vwap_value = float(np.sum(typical_price * volume_array) / np.sum(volume_array))
    current_price = close[-1]
    
    position = "above" if current_price > vwap_value else "below"
    deviation_percent = ((current_price - vwap_value) / vwap_value) * 100
    
    return VWAP(value=vwap_value, position=position, deviation_percent=float(deviation_percent))


def calculate_volume_sma(volume: List[float], period: int = 20) -> Optional[VolumeSMA]:
    """
    Calculate Volume SMA.
    
    Args:
        volume: List of volumes
        period: SMA period
        
    Returns:
        VolumeSMA or None if insufficient data
    """
    if len(volume) < period:
        return None
    
    volume_array = np.array(volume)
    current_volume = float(volume_array[-1])
    sma = float(np.mean(volume_array[-period:]))
    
    if sma == 0:
        ratio = 1.0
    else:
        ratio = current_volume / sma
    
    # Determine status
    if ratio > 1.5:
        status = "high"
    elif ratio < 0.5:
        status = "low"
    else:
        status = "normal"
    
    return VolumeSMA(current_volume=current_volume, sma=sma, ratio=float(ratio), status=status)


def detect_volume_spike(volumes: List[float], threshold: float = 2.0, lookback: int = 20) -> Optional[VolumeSpike]:
    """
    Detect abnormal volume spikes.
    
    Compare current volume to average of last 'lookback' candles.
    Spike = current volume > average * threshold
    
    Args:
        volumes: List of volumes
        threshold: Multiplier for spike detection (default 2.0 = 200%)
        lookback: Number of candles to average (default 20)
        
    Returns:
        VolumeSpike: spike_percentage (e.g., 180 means +180% above average) or None if insufficient data
    """
    if len(volumes) < lookback + 1:
        return None
    
    volume_array = np.array(volumes)
    current_volume = float(volume_array[-1])
    # Calculate average of previous candles (excluding current)
    average_volume = float(np.mean(volume_array[-(lookback+1):-1]))
    
    if average_volume == 0:
        return VolumeSpike(
            is_spike=False,
            spike_percentage=0.0,
            current_volume=current_volume,
            average_volume=average_volume
        )
    
    ratio = current_volume / average_volume
    is_spike = ratio > threshold
    # Calculate percentage above average (e.g., ratio of 2.8 = 180% above = (2.8-1)*100)
    spike_percentage = float((ratio - 1.0) * 100)
    
    return VolumeSpike(
        is_spike=is_spike,
        spike_percentage=spike_percentage,
        current_volume=current_volume,
        average_volume=average_volume
    )


def calculate_pivot_points(high: float, low: float, close: float, current_price: float) -> PivotPoints:
    """
    Calculate Pivot Points.
    
    Args:
        high: Previous period high
        low: Previous period low
        close: Previous period close
        current_price: Current price
        
    Returns:
        PivotPoints
    """
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    s1 = (2 * pivot) - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)
    
    # Determine current zone
    if current_price >= r3:
        zone = "above_r3"
    elif current_price >= r2:
        zone = "r2_to_r3"
    elif current_price >= r1:
        zone = "r1_to_r2"
    elif current_price >= pivot:
        zone = "pivot_to_r1"
    elif current_price >= s1:
        zone = "s1_to_pivot"
    elif current_price >= s2:
        zone = "s2_to_s1"
    elif current_price >= s3:
        zone = "s3_to_s2"
    else:
        zone = "below_s3"
    
    return PivotPoints(
        pivot=pivot, r1=r1, r2=r2, r3=r3,
        s1=s1, s2=s2, s3=s3, current_zone=zone
    )


def calculate_fibonacci_levels(high: float, low: float, current_price: float) -> FibonacciLevels:
    """
    Calculate Fibonacci Retracement Levels.
    
    Args:
        high: Period high
        low: Period low
        current_price: Current price
        
    Returns:
        FibonacciLevels
    """
    diff = high - low
    
    level_0 = high
    level_236 = high - (0.236 * diff)
    level_382 = high - (0.382 * diff)
    level_50 = high - (0.5 * diff)
    level_618 = high - (0.618 * diff)
    level_786 = high - (0.786 * diff)
    level_100 = low
    
    # Find nearest level
    levels = {
        "0%": level_0,
        "23.6%": level_236,
        "38.2%": level_382,
        "50%": level_50,
        "61.8%": level_618,
        "78.6%": level_786,
        "100%": level_100
    }
    
    nearest_level = min(levels.items(), key=lambda x: abs(x[1] - current_price))
    
    return FibonacciLevels(
        level_0=level_0,
        level_236=level_236,
        level_382=level_382,
        level_50=level_50,
        level_618=level_618,
        level_786=level_786,
        level_100=level_100,
        nearest_level=nearest_level[0],
        nearest_value=nearest_level[1]
    )


@dataclass
class RSIDivergence:
    """
    RSI Divergence detection.
    
    Attributes:
        type: Type of divergence ('bullish', 'bearish', 'hidden_bullish', 'hidden_bearish', 'none')
        strength: Strength of divergence (0-100)
        explanation: Human-readable explanation
    """
    type: str
    strength: float
    explanation: str


@dataclass
class ADX:
    """
    Average Directional Index (ADX).
    
    Attributes:
        value: ADX value (0-100)
        plus_di: +DI value
        minus_di: -DI value
        trend_strength: Strength of trend ('weak', 'medium', 'strong', 'very_strong')
        direction: Trend direction ('bullish', 'bearish', 'neutral')
    """
    value: float
    plus_di: float
    minus_di: float
    trend_strength: str
    direction: str


@dataclass
class SqueezeMomentum:
    """
    Squeeze Momentum Indicator.
    
    Attributes:
        is_squeezed: Whether Bollinger Bands are inside Keltner Channels
        momentum: Momentum value
        signal: Trading signal ('bullish', 'bearish', 'neutral')
    """
    is_squeezed: bool
    momentum: float
    signal: str


@dataclass
class Supertrend:
    """
    Supertrend Indicator.
    
    Attributes:
        value: Supertrend line value
        direction: Trend direction ('long', 'short')
        is_reversal: Whether there was a reversal
    """
    value: float
    direction: str
    is_reversal: bool


def calculate_rsi_divergence(
    prices: List[float],
    rsi_values: List[float],
    lookback: int = 14
) -> Optional[RSIDivergence]:
    """
    Calculate RSI Divergence (bullish/bearish/hidden).
    
    Args:
        prices: List of closing prices
        rsi_values: List of RSI values
        lookback: Lookback period for detecting divergence
        
    Returns:
        RSIDivergence or None if insufficient data
    """
    # Minimum 5 extra periods needed for reliable peak/trough detection (2 on each side + 1 center)
    MIN_EXTRA_PERIODS = 5
    if len(prices) < lookback + MIN_EXTRA_PERIODS or len(prices) != len(rsi_values):
        return None
    
    prices_array = np.array(prices[-lookback:])
    rsi_array = np.array(rsi_values[-lookback:])
    
    # Strength multiplier for divergence detection
    DIVERGENCE_STRENGTH_MULTIPLIER = 3
    
    # Find local highs and lows
    price_highs = []
    price_lows = []
    rsi_highs = []
    rsi_lows = []
    
    for i in range(2, len(prices_array) - 2):
        # Local high
        if prices_array[i] > prices_array[i-1] and prices_array[i] > prices_array[i+1]:
            if prices_array[i] > prices_array[i-2] and prices_array[i] > prices_array[i+2]:
                price_highs.append((i, prices_array[i]))
                rsi_highs.append((i, rsi_array[i]))
        
        # Local low
        if prices_array[i] < prices_array[i-1] and prices_array[i] < prices_array[i+1]:
            if prices_array[i] < prices_array[i-2] and prices_array[i] < prices_array[i+2]:
                price_lows.append((i, prices_array[i]))
                rsi_lows.append((i, rsi_array[i]))
    
    divergence_type = "none"
    strength = 0.0
    explanation = "No divergence detected"
    
    # Bullish divergence: price makes lower low, RSI makes higher low
    if len(price_lows) >= 2 and len(rsi_lows) >= 2:
        last_price_low = price_lows[-1][1]
        prev_price_low = price_lows[-2][1]
        last_rsi_low = rsi_lows[-1][1]
        prev_rsi_low = rsi_lows[-2][1]
        
        if last_price_low < prev_price_low and last_rsi_low > prev_rsi_low:
            divergence_type = "bullish"
            strength = min(100, abs(last_rsi_low - prev_rsi_low) * DIVERGENCE_STRENGTH_MULTIPLIER)
            explanation = "🟢 Bullish Divergence: Price making lower lows but RSI making higher lows. Potential reversal up."
    
    # Bearish divergence: price makes higher high, RSI makes lower high
    if len(price_highs) >= 2 and len(rsi_highs) >= 2:
        last_price_high = price_highs[-1][1]
        prev_price_high = price_highs[-2][1]
        last_rsi_high = rsi_highs[-1][1]
        prev_rsi_high = rsi_highs[-2][1]
        
        if last_price_high > prev_price_high and last_rsi_high < prev_rsi_high:
            divergence_type = "bearish"
            strength = min(100, abs(last_rsi_high - prev_rsi_high) * DIVERGENCE_STRENGTH_MULTIPLIER)
            explanation = "🔴 Bearish Divergence: Price making higher highs but RSI making lower highs. Potential reversal down."
    
    return RSIDivergence(type=divergence_type, strength=strength, explanation=explanation)


def calculate_adx(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 14
) -> Optional[ADX]:
    """
    Calculate Average Directional Index (ADX).
    
    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        period: Period for calculation
        
    Returns:
        ADX or None if insufficient data
    """
    if len(high) < period + 1 or len(high) != len(low) or len(high) != len(close):
        return None
    
    high_array = np.array(high)
    low_array = np.array(low)
    close_array = np.array(close)
    
    # Calculate True Range and Directional Movement
    tr = []
    plus_dm = []
    minus_dm = []
    
    for i in range(1, len(high_array)):
        h_l = high_array[i] - low_array[i]
        h_c = abs(high_array[i] - close_array[i-1])
        l_c = abs(low_array[i] - close_array[i-1])
        tr.append(max(h_l, h_c, l_c))
        
        up_move = high_array[i] - high_array[i-1]
        down_move = low_array[i-1] - low_array[i]
        
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0)
        
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0)
    
    if len(tr) < period:
        return None
    
    # Smooth the values
    tr_smooth = float(np.mean(tr[-period:]))
    plus_dm_smooth = float(np.mean(plus_dm[-period:]))
    minus_dm_smooth = float(np.mean(minus_dm[-period:]))
    
    # Calculate DI
    plus_di = (plus_dm_smooth / tr_smooth) * 100 if tr_smooth > 0 else 0
    minus_di = (minus_dm_smooth / tr_smooth) * 100 if tr_smooth > 0 else 0
    
    # Calculate DX and ADX
    di_sum = plus_di + minus_di
    dx = abs(plus_di - minus_di) / di_sum * 100 if di_sum > 0 else 0
    
    # NOTE: For simplicity, we use DX as ADX without smoothing.
    # A proper ADX implementation would smooth DX values over the period using EMA.
    # This simplified version is sufficient for basic trend strength detection.
    adx_value = float(dx)
    
    # Determine trend strength
    if adx_value < 20:
        trend_strength = "weak"
    elif adx_value < 40:
        trend_strength = "medium"
    elif adx_value < 60:
        trend_strength = "strong"
    else:
        trend_strength = "very_strong"
    
    # Determine direction
    if plus_di > minus_di:
        direction = "bullish"
    elif minus_di > plus_di:
        direction = "bearish"
    else:
        direction = "neutral"
    
    return ADX(
        value=adx_value,
        plus_di=plus_di,
        minus_di=minus_di,
        trend_strength=trend_strength,
        direction=direction
    )


def calculate_squeeze_momentum(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 20
) -> Optional[SqueezeMomentum]:
    """
    Calculate Squeeze Momentum Indicator.
    
    The squeeze occurs when Bollinger Bands move inside Keltner Channels,
    indicating low volatility that often precedes a breakout.
    
    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        period: Period for calculation
        
    Returns:
        SqueezeMomentum or None if insufficient data
    """
    if len(high) < period + 10 or len(high) != len(low) or len(high) != len(close):
        return None
    
    # Calculate Bollinger Bands
    bb = calculate_bollinger_bands(close, period)
    if not bb:
        return None
    
    # Calculate Keltner Channels
    kc = calculate_keltner_channels(high, low, close, period)
    if not kc:
        return None
    
    # Check if squeeze is on
    is_squeezed = bb.lower > kc.lower and bb.upper < kc.upper
    
    # Calculate momentum (simplified: linear regression of close prices)
    close_array = np.array(close[-period:])
    x = np.arange(len(close_array))
    coeffs = np.polyfit(x, close_array, 1)
    momentum = float(coeffs[0])  # Slope of the line
    
    # Determine signal
    if is_squeezed:
        signal = "neutral"  # Waiting for breakout
    elif momentum > 0:
        signal = "bullish"
    elif momentum < 0:
        signal = "bearish"
    else:
        signal = "neutral"
    
    return SqueezeMomentum(is_squeezed=is_squeezed, momentum=momentum, signal=signal)


def calculate_supertrend(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 10,
    multiplier: float = 3.0
) -> Optional[Supertrend]:
    """
    Calculate Supertrend Indicator.
    
    Supertrend is a trend-following indicator based on ATR.
    
    Args:
        high: List of high prices
        low: List of low prices
        close: List of closing prices
        period: ATR period
        multiplier: ATR multiplier
        
    Returns:
        Supertrend or None if insufficient data
    """
    if len(high) < period + 10 or len(high) != len(low) or len(high) != len(close):
        return None
    
    # Calculate ATR
    atr = calculate_atr(high, low, close, period)
    if not atr:
        return None
    
    # Calculate basic upper and lower bands
    hl_avg = [(h + l) / 2 for h, l in zip(high, low)]
    
    basic_upper = hl_avg[-1] + (multiplier * atr.value)
    basic_lower = hl_avg[-1] - (multiplier * atr.value)
    
    current_close = close[-1]
    prev_close = close[-2] if len(close) > 1 else current_close
    
    # Determine direction
    if current_close > basic_upper:
        direction = "long"
        supertrend_value = basic_lower
    elif current_close < basic_lower:
        direction = "short"
        supertrend_value = basic_upper
    else:
        # Use previous direction or default to short
        if prev_close > basic_upper:
            direction = "long"
            supertrend_value = basic_lower
        else:
            direction = "short"
            supertrend_value = basic_upper
    
    # Check for reversal (only if we have enough data)
    if len(hl_avg) >= 2:
        prev_direction = "short" if prev_close < hl_avg[-2] - (multiplier * atr.value) else "long"
        is_reversal = direction != prev_direction
    else:
        is_reversal = False
    
    return Supertrend(value=supertrend_value, direction=direction, is_reversal=is_reversal)


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
class SwingPoint:
    """
    Swing high/low point.
    
    Attributes:
        price: Price at the swing point
        index: Index in the data array
        type: 'high' or 'low'
        strength: Number of touches (validation count)
    """
    price: float
    index: int
    type: str  # 'high' or 'low'
    strength: int = 1


def find_swing_points(ohlcv_data: List[dict], lookback: int = 50) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Find swing highs and lows in OHLCV data.
    
    A swing high is a candle where the high is higher than 2 candles on each side.
    A swing low is a candle where the low is lower than 2 candles on each side.
    
    Args:
        ohlcv_data: List of OHLCV candles with 'high', 'low', 'close' keys
        lookback: Number of candles to analyze (default 50)
        
    Returns:
        Tuple of (swing_highs, swing_lows) as lists of SwingPoint objects
    """
    if len(ohlcv_data) < 5:
        return [], []
    
    # Use only the most recent candles
    data = ohlcv_data[-lookback:] if len(ohlcv_data) > lookback else ohlcv_data
    
    swing_highs = []
    swing_lows = []
    
    # Need at least 5 candles (2 before, 1 center, 2 after)
    for i in range(2, len(data) - 2):
        # Check for swing high
        if (data[i]['high'] > data[i-1]['high'] and 
            data[i]['high'] > data[i-2]['high'] and
            data[i]['high'] > data[i+1]['high'] and
            data[i]['high'] > data[i+2]['high']):
            
            swing_highs.append(SwingPoint(
                price=data[i]['high'],
                index=i,
                type='high',
                strength=1
            ))
        
        # Check for swing low
        if (data[i]['low'] < data[i-1]['low'] and 
            data[i]['low'] < data[i-2]['low'] and
            data[i]['low'] < data[i+1]['low'] and
            data[i]['low'] < data[i+2]['low']):
            
            swing_lows.append(SwingPoint(
                price=data[i]['low'],
                index=i,
                type='low',
                strength=1
            ))
    
    return swing_highs, swing_lows


def count_touches(ohlcv_data: List[dict], level: float, tolerance_pct: float = 0.5) -> int:
    """
    Count how many times price has touched a specific level.
    
    A touch is counted when the high or low comes within tolerance_pct of the level.
    
    Args:
        ohlcv_data: List of OHLCV candles
        level: Price level to check
        tolerance_pct: Tolerance as percentage (default 0.5%)
        
    Returns:
        Number of touches
    """
    if not ohlcv_data or level <= 0:
        return 0
    
    tolerance = level * (tolerance_pct / 100.0)
    touches = 0
    
    for candle in ohlcv_data:
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        
        # Check if candle touched the level
        if abs(high - level) <= tolerance or abs(low - level) <= tolerance:
            touches += 1
        # Also count if the level is within the candle range
        elif low <= level <= high:
            touches += 1
    
    return touches


def calculate_level_strength(
    level: float,
    source: str,
    touches: int,
    volume_at_level: float = 0.0,
    age_factor: float = 1.0
) -> int:
    """
    Calculate strength of a support/resistance level.
    
    Strength is scored from 1-5 based on:
    - Source (swing points = higher, round numbers = medium)
    - Number of touches (more = stronger)
    - Volume at level (optional, higher = stronger)
    - Age factor (optional, more recent = stronger)
    
    Args:
        level: Price level
        source: Source type ('swing_high', 'swing_low', 'round_number', 'prev_high', 'prev_low', etc.)
        touches: Number of times price touched this level
        volume_at_level: Volume traded at this level (optional)
        age_factor: Factor for recency (1.0 = recent, 0.5 = old) (optional)
        
    Returns:
        Strength score from 1-5 stars
    """
    strength = 0
    
    # Base strength from source
    source_strength = {
        'swing_high': 3,
        'swing_low': 3,
        'prev_high': 4,
        'prev_low': 4,
        'round_number': 2,
        'fib_level': 3,
        'volume_poc': 4,
    }
    strength = source_strength.get(source, 2)
    
    # Bonus from touches (max +2)
    if touches >= 5:
        strength += 2
    elif touches >= 3:
        strength += 1
    
    # Small bonus from volume (max +1)
    if volume_at_level > 0:
        strength = min(5, strength + 1)
    
    # Apply age factor (reduce if old)
    strength = int(strength * age_factor)
    
    # Ensure within range 1-5
    return max(1, min(5, strength))
