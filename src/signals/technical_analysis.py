"""
Advanced Technical Analysis Indicators.

Implements advanced indicators for crypto market analysis:
- Ichimoku Cloud
- Volume Profile
- CVD (Cumulative Volume Delta)
- Market Structure
- Order Blocks
- FVG (Fair Value Gaps)
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import numpy as np


# Constants for Ichimoku Cloud
ICHIMOKU_TENKAN_PERIOD = 9
ICHIMOKU_KIJUN_PERIOD = 26
ICHIMOKU_SENKOU_PERIOD = 52

# Constants for data validation
MIN_DATA_POINTS_ICHIMOKU = 52
MIN_DATA_POINTS_VOLUME_PROFILE = 10
MIN_DATA_POINTS_CVD = 10
MIN_DATA_POINTS_MARKET_STRUCTURE = 30  # lookback * 3
MIN_DATA_POINTS_ORDER_BLOCKS = 5
MIN_DATA_POINTS_FVG = 3


@dataclass
class IchimokuCloud:
    """
    Ichimoku Cloud indicator.
    
    Components:
    - Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
    - Kijun-sen (Base Line): (26-period high + 26-period low) / 2
    - Senkou Span A: (Tenkan-sen + Kijun-sen) / 2, shifted 26 periods forward
    - Senkou Span B: (52-period high + 52-period low) / 2, shifted 26 periods forward
    - Chikou Span: Close shifted 26 periods back
    """
    tenkan_sen: float
    kijun_sen: float
    senkou_span_a: float
    senkou_span_b: float
    chikou_span: float
    cloud_color: str  # "bullish" or "bearish"
    
    @property
    def signal(self) -> str:
        """Get trading signal based on Ichimoku."""
        if self.cloud_color == "bullish":
            return "bullish"
        elif self.cloud_color == "bearish":
            return "bearish"
        return "neutral"


@dataclass
class VolumeProfile:
    """
    Volume Profile analysis.
    
    - POC (Point of Control): Price level with maximum volume
    - VAH (Value Area High): Upper boundary of 70% volume area
    - VAL (Value Area Low): Lower boundary of 70% volume area
    """
    poc: float  # Point of Control
    vah: float  # Value Area High
    val: float  # Value Area Low
    
    def get_position(self, current_price: float) -> str:
        """Get current price position relative to value area."""
        if current_price > self.vah:
            return "above_value_area"
        elif current_price < self.val:
            return "below_value_area"
        return "in_value_area"


@dataclass
class CVD:
    """
    Cumulative Volume Delta.
    
    Delta = Buy Volume - Sell Volume
    Determines buying/selling pressure based on candle close vs open
    """
    value: float
    trend: str  # "rising", "falling", or "neutral"
    
    @property
    def signal(self) -> str:
        """Get trading signal based on CVD trend."""
        if self.trend == "rising":
            return "bullish"
        elif self.trend == "falling":
            return "bearish"
        return "neutral"


@dataclass
class MarketStructure:
    """
    Market Structure analysis.
    
    - HH (Higher High), HL (Higher Low) → Bullish trend
    - LH (Lower High), LL (Lower Low) → Bearish trend
    """
    structure: str  # "bullish", "bearish", "neutral"
    last_swing_high: Optional[float] = None
    last_swing_low: Optional[float] = None
    
    @property
    def signal(self) -> str:
        """Get trading signal based on market structure."""
        return self.structure


@dataclass
class OrderBlock:
    """
    Order Block detection.
    
    - Bullish OB: Last bearish candle before upward impulse
    - Bearish OB: Last bullish candle before downward impulse
    """
    block_type: str  # "bullish" or "bearish"
    price_high: float
    price_low: float
    index: int  # Candle index where OB formed
    
    @property
    def signal(self) -> str:
        """Get trading signal."""
        return self.block_type


@dataclass
class FVG:
    """
    Fair Value Gap.
    
    - Bullish FVG: low[i] > high[i-2]
    - Bearish FVG: high[i] < low[i-2]
    """
    gap_type: str  # "bullish" or "bearish"
    gap_high: float
    gap_low: float
    index: int  # Candle index where gap formed
    
    @property
    def signal(self) -> str:
        """Get trading signal."""
        return self.gap_type


def calculate_ichimoku(
    high: List[float],
    low: List[float],
    close: List[float],
    current_price: float
) -> Optional[IchimokuCloud]:
    """
    Calculate Ichimoku Cloud indicator.
    
    Args:
        high: List of high prices
        low: List of low prices
        close: List of close prices
        current_price: Current price for position determination
        
    Returns:
        IchimokuCloud object or None if insufficient data
    """
    if len(high) < MIN_DATA_POINTS_ICHIMOKU or len(low) < MIN_DATA_POINTS_ICHIMOKU or len(close) < ICHIMOKU_KIJUN_PERIOD:
        return None
    
    try:
        # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
        tenkan_high = max(high[-ICHIMOKU_TENKAN_PERIOD:])
        tenkan_low = min(low[-ICHIMOKU_TENKAN_PERIOD:])
        tenkan_sen = (tenkan_high + tenkan_low) / 2
        
        # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
        kijun_high = max(high[-ICHIMOKU_KIJUN_PERIOD:])
        kijun_low = min(low[-ICHIMOKU_KIJUN_PERIOD:])
        kijun_sen = (kijun_high + kijun_low) / 2
        
        # Senkou Span A: (Tenkan-sen + Kijun-sen) / 2
        senkou_span_a = (tenkan_sen + kijun_sen) / 2
        
        # Senkou Span B: (52-period high + 52-period low) / 2
        senkou_high = max(high[-ICHIMOKU_SENKOU_PERIOD:])
        senkou_low = min(low[-ICHIMOKU_SENKOU_PERIOD:])
        senkou_span_b = (senkou_high + senkou_low) / 2
        
        # Chikou Span: Current close (shifted back 26 periods in practice)
        chikou_span = close[-1]
        
        # Determine cloud color (bullish if Span A > Span B)
        cloud_color = "bullish" if senkou_span_a > senkou_span_b else "bearish"
        
        return IchimokuCloud(
            tenkan_sen=tenkan_sen,
            kijun_sen=kijun_sen,
            senkou_span_a=senkou_span_a,
            senkou_span_b=senkou_span_b,
            chikou_span=chikou_span,
            cloud_color=cloud_color
        )
    except Exception:
        return None


def calculate_volume_profile(
    close: List[float],
    volume: List[float],
    num_bins: int = 20
) -> Optional[VolumeProfile]:
    """
    Calculate Volume Profile.
    
    Args:
        close: List of close prices
        volume: List of volumes
        num_bins: Number of price bins for volume distribution
        
    Returns:
        VolumeProfile object or None if insufficient data
    """
    if len(close) < MIN_DATA_POINTS_VOLUME_PROFILE or len(volume) < MIN_DATA_POINTS_VOLUME_PROFILE or len(close) != len(volume):
        return None
    
    try:
        # Create price bins
        min_price = min(close)
        max_price = max(close)
        price_range = max_price - min_price
        
        if price_range == 0:
            return None
        
        bin_size = price_range / num_bins
        
        # Distribute volume into bins
        volume_at_price = {}
        for i in range(len(close)):
            bin_index = int((close[i] - min_price) / bin_size)
            if bin_index >= num_bins:
                bin_index = num_bins - 1
            
            bin_price = min_price + (bin_index + 0.5) * bin_size
            volume_at_price[bin_price] = volume_at_price.get(bin_price, 0) + volume[i]
        
        # Find POC (Point of Control)
        poc = max(volume_at_price.keys(), key=lambda k: volume_at_price[k])
        
        # Calculate Value Area (70% of total volume)
        total_volume = sum(volume)
        target_volume = total_volume * 0.7
        
        # Sort prices by volume
        sorted_prices = sorted(volume_at_price.keys(), key=lambda k: volume_at_price[k], reverse=True)
        
        # Find value area
        accumulated_volume = 0
        value_area_prices = []
        for price in sorted_prices:
            accumulated_volume += volume_at_price[price]
            value_area_prices.append(price)
            if accumulated_volume >= target_volume:
                break
        
        vah = max(value_area_prices)
        val = min(value_area_prices)
        
        return VolumeProfile(poc=poc, vah=vah, val=val)
    except Exception:
        return None


def calculate_cvd(
    open_prices: List[float],
    close: List[float],
    volume: List[float]
) -> Optional[CVD]:
    """
    Calculate Cumulative Volume Delta.
    
    Args:
        open_prices: List of open prices
        close: List of close prices
        volume: List of volumes
        
    Returns:
        CVD object or None if insufficient data
    """
    if len(open_prices) < 10 or len(close) < 10 or len(volume) < 10:
        return None
    
    if len(open_prices) != len(close) or len(close) != len(volume):
        return None
    
    try:
        # Calculate delta for each candle
        deltas = []
        for i in range(len(close)):
            if close[i] > open_prices[i]:
                # Bullish candle - assume buy volume
                deltas.append(volume[i])
            elif close[i] < open_prices[i]:
                # Bearish candle - assume sell volume
                deltas.append(-volume[i])
            else:
                # Neutral candle
                deltas.append(0)
        
        # Calculate cumulative sum
        cvd_value = sum(deltas)
        
        # Determine trend by comparing recent CVD vs earlier CVD
        mid_point = len(deltas) // 2
        early_cvd = sum(deltas[:mid_point])
        recent_cvd = sum(deltas[mid_point:])
        
        if recent_cvd > early_cvd * 1.1:
            trend = "rising"
        elif recent_cvd < early_cvd * 0.9:
            trend = "falling"
        else:
            trend = "neutral"
        
        return CVD(value=cvd_value, trend=trend)
    except Exception:
        return None


def calculate_market_structure(
    high: List[float],
    low: List[float],
    lookback: int = 10
) -> Optional[MarketStructure]:
    """
    Calculate Market Structure (HH, HL, LH, LL).
    
    Args:
        high: List of high prices
        low: List of low prices
        lookback: Number of periods to look back for swing points
        
    Returns:
        MarketStructure object or None if insufficient data
    """
    if len(high) < lookback * 3 or len(low) < lookback * 3:
        return None
    
    try:
        # Find swing highs and lows
        swing_highs = []
        swing_lows = []
        
        for i in range(lookback, len(high) - lookback):
            # Check if it's a swing high
            is_swing_high = True
            for j in range(1, lookback + 1):
                if high[i] <= high[i - j] or high[i] <= high[i + j]:
                    is_swing_high = False
                    break
            if is_swing_high:
                swing_highs.append((i, high[i]))
            
            # Check if it's a swing low
            is_swing_low = True
            for j in range(1, lookback + 1):
                if low[i] >= low[i - j] or low[i] >= low[i + j]:
                    is_swing_low = False
                    break
            if is_swing_low:
                swing_lows.append((i, low[i]))
        
        if len(swing_highs) < 2 and len(swing_lows) < 2:
            return MarketStructure(structure="neutral")
        
        # Analyze structure
        bullish_signals = 0
        bearish_signals = 0
        
        # Check for HH (Higher Highs)
        if len(swing_highs) >= 2:
            last_swing_high = swing_highs[-1][1]
            prev_swing_high = swing_highs[-2][1]
            if last_swing_high > prev_swing_high:
                bullish_signals += 1
            else:
                bearish_signals += 1
        
        # Check for HL (Higher Lows)
        if len(swing_lows) >= 2:
            last_swing_low = swing_lows[-1][1]
            prev_swing_low = swing_lows[-2][1]
            if last_swing_low > prev_swing_low:
                bullish_signals += 1
            else:
                bearish_signals += 1
        
        # Determine structure
        if bullish_signals > bearish_signals:
            structure = "bullish"
        elif bearish_signals > bullish_signals:
            structure = "bearish"
        else:
            structure = "neutral"
        
        last_swing_high = swing_highs[-1][1] if swing_highs else None
        last_swing_low = swing_lows[-1][1] if swing_lows else None
        
        return MarketStructure(
            structure=structure,
            last_swing_high=last_swing_high,
            last_swing_low=last_swing_low
        )
    except Exception:
        return None


def find_order_blocks(
    open_prices: List[float],
    high: List[float],
    low: List[float],
    close: List[float],
    impulse_threshold: float = 0.01
) -> List[OrderBlock]:
    """
    Find Order Blocks.
    
    Args:
        open_prices: List of open prices
        high: List of high prices
        low: List of low prices
        close: List of close prices
        impulse_threshold: Minimum price change to consider as impulse (1%)
        
    Returns:
        List of OrderBlock objects
    """
    if len(open_prices) < 5 or len(high) < 5 or len(low) < 5 or len(close) < 5:
        return []
    
    order_blocks = []
    
    try:
        for i in range(1, len(close) - 1):
            # Bullish Order Block: Last bearish candle before upward impulse
            if close[i] < open_prices[i]:  # Bearish candle
                if close[i + 1] > close[i] * (1 + impulse_threshold):  # Upward impulse
                    order_blocks.append(OrderBlock(
                        block_type="bullish",
                        price_high=high[i],
                        price_low=low[i],
                        index=i
                    ))
            
            # Bearish Order Block: Last bullish candle before downward impulse
            if close[i] > open_prices[i]:  # Bullish candle
                if close[i + 1] < close[i] * (1 - impulse_threshold):  # Downward impulse
                    order_blocks.append(OrderBlock(
                        block_type="bearish",
                        price_high=high[i],
                        price_low=low[i],
                        index=i
                    ))
        
        # Return only the most recent order blocks (max 5)
        return order_blocks[-5:] if len(order_blocks) > 5 else order_blocks
    except Exception:
        return []


def find_fvg(
    high: List[float],
    low: List[float]
) -> List[FVG]:
    """
    Find Fair Value Gaps.
    
    Args:
        high: List of high prices
        low: List of low prices
        
    Returns:
        List of FVG objects
    """
    if len(high) < 3 or len(low) < 3:
        return []
    
    fvgs = []
    
    try:
        for i in range(2, len(high)):
            # Bullish FVG: low[i] > high[i-2]
            if low[i] > high[i - 2]:
                fvgs.append(FVG(
                    gap_type="bullish",
                    gap_high=low[i],
                    gap_low=high[i - 2],
                    index=i
                ))
            
            # Bearish FVG: high[i] < low[i-2]
            if high[i] < low[i - 2]:
                fvgs.append(FVG(
                    gap_type="bearish",
                    gap_high=low[i - 2],
                    gap_low=high[i],
                    index=i
                ))
        
        # Return only the most recent FVGs (max 5)
        return fvgs[-5:] if len(fvgs) > 5 else fvgs
    except Exception:
        return []
