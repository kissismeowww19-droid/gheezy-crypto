"""
Tests for advanced technical indicators.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.technical_analysis import (
    calculate_ichimoku,
    calculate_volume_profile,
    calculate_cvd,
    calculate_market_structure,
    find_order_blocks,
    find_fvg
)


def test_ichimoku_calculation():
    """Test Ichimoku Cloud calculation."""
    # Sample data - 60 candles
    high = [100 + i * 0.5 for i in range(60)]
    low = [99 + i * 0.5 for i in range(60)]
    close = [99.5 + i * 0.5 for i in range(60)]
    current_price = close[-1]
    
    result = calculate_ichimoku(high, low, close, current_price)
    
    assert result is not None
    assert hasattr(result, 'tenkan_sen')
    assert hasattr(result, 'kijun_sen')
    assert hasattr(result, 'senkou_span_a')
    assert hasattr(result, 'senkou_span_b')
    assert result.cloud_color in ['bullish', 'bearish']
    assert result.signal in ['bullish', 'bearish', 'neutral']


def test_ichimoku_insufficient_data():
    """Test Ichimoku with insufficient data."""
    high = [100, 101, 102]
    low = [99, 100, 101]
    close = [99.5, 100.5, 101.5]
    current_price = 101.5
    
    result = calculate_ichimoku(high, low, close, current_price)
    
    assert result is None


def test_volume_profile_calculation():
    """Test Volume Profile calculation."""
    close = [100 + i * 0.1 for i in range(50)]
    volume = [1000 + i * 10 for i in range(50)]
    
    result = calculate_volume_profile(close, volume)
    
    assert result is not None
    assert hasattr(result, 'poc')
    assert hasattr(result, 'vah')
    assert hasattr(result, 'val')
    assert result.vah > result.val


def test_volume_profile_position():
    """Test Volume Profile position detection."""
    close = [100 + i * 0.1 for i in range(50)]
    volume = [1000 + i * 10 for i in range(50)]
    
    result = calculate_volume_profile(close, volume)
    
    assert result is not None
    
    # Test position detection
    high_price = result.vah + 10
    position_high = result.get_position(high_price)
    assert position_high == "above_value_area"
    
    low_price = result.val - 10
    position_low = result.get_position(low_price)
    assert position_low == "below_value_area"
    
    mid_price = (result.vah + result.val) / 2
    position_mid = result.get_position(mid_price)
    assert position_mid == "in_value_area"


def test_cvd_calculation():
    """Test CVD calculation."""
    open_prices = [100, 101, 99, 102, 103]
    close = [101, 99, 102, 103, 102]
    volume = [1000, 1100, 1200, 1300, 1400]
    
    result = calculate_cvd(open_prices, close, volume)
    
    assert result is not None
    assert hasattr(result, 'value')
    assert hasattr(result, 'trend')
    assert result.trend in ['rising', 'falling', 'neutral']
    assert result.signal in ['bullish', 'bearish', 'neutral']


def test_cvd_insufficient_data():
    """Test CVD with insufficient data."""
    open_prices = [100, 101]
    close = [101, 99]
    volume = [1000, 1100]
    
    result = calculate_cvd(open_prices, close, volume)
    
    assert result is None


def test_market_structure_calculation():
    """Test Market Structure calculation."""
    # Create bullish structure (higher highs and higher lows)
    high = [100, 102, 98, 104, 101, 106, 103, 108, 105, 110, 107, 112] * 3
    low = [95, 97, 93, 99, 96, 101, 98, 103, 100, 105, 102, 107] * 3
    
    result = calculate_market_structure(high, low, lookback=5)
    
    assert result is not None
    assert hasattr(result, 'structure')
    assert result.structure in ['bullish', 'bearish', 'neutral']
    assert result.signal in ['bullish', 'bearish', 'neutral']


def test_order_blocks_detection():
    """Test Order Blocks detection."""
    # Create pattern with clear order blocks
    open_prices = [100, 101, 102, 101, 100, 99, 98, 97, 99, 101]
    high = [102, 103, 104, 103, 102, 101, 100, 99, 101, 103]
    low = [99, 100, 101, 100, 99, 98, 97, 96, 98, 100]
    close = [101, 102, 101, 100, 99, 98, 97, 99, 101, 102]
    
    result = find_order_blocks(open_prices, high, low, close, impulse_threshold=0.02)
    
    assert isinstance(result, list)
    # May find order blocks or not depending on the pattern
    if len(result) > 0:
        ob = result[0]
        assert hasattr(ob, 'block_type')
        assert ob.block_type in ['bullish', 'bearish']
        assert hasattr(ob, 'price_high')
        assert hasattr(ob, 'price_low')


def test_fvg_detection():
    """Test Fair Value Gap detection."""
    # Create pattern with potential FVG
    high = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118]
    low = [99, 101, 103, 105, 107, 109, 111, 113, 115, 117]
    
    result = find_fvg(high, low)
    
    assert isinstance(result, list)
    # May find FVGs or not depending on the pattern
    if len(result) > 0:
        fvg = result[0]
        assert hasattr(fvg, 'gap_type')
        assert fvg.gap_type in ['bullish', 'bearish']
        assert hasattr(fvg, 'gap_high')
        assert hasattr(fvg, 'gap_low')
        assert fvg.gap_high > fvg.gap_low


def test_fvg_insufficient_data():
    """Test FVG with insufficient data."""
    high = [100, 101]
    low = [99, 100]
    
    result = find_fvg(high, low)
    
    assert isinstance(result, list)
    assert len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
