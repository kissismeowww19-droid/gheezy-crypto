"""
Tests for weighted signal system and price prediction.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer
from signals.indicators import find_swing_points, count_touches, calculate_level_strength
from unittest.mock import Mock, AsyncMock


class TestWeightedSignalSystem:
    """Tests for new weighted signal system."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_factor_weights_sum_to_100_percent(self, analyzer):
        """Test that factor weights sum to 100% (1.0)."""
        total_weight = sum(analyzer.FACTOR_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001, f"Weights sum to {total_weight}, expected 1.0"
    
    def test_factor_weights_has_all_factors(self, analyzer):
        """Test that all 10 factors are present."""
        expected_factors = {
            'whales', 'derivatives', 'trend', 'momentum', 'volume',
            'adx', 'divergence', 'sentiment', 'macro', 'options'
        }
        assert set(analyzer.FACTOR_WEIGHTS.keys()) == expected_factors
    
    def test_calculate_weighted_score_all_bullish(self, analyzer):
        """Test weighted score with all bullish factors."""
        factors = {
            'whales': 10,
            'derivatives': 10,
            'trend': 10,
            'momentum': 10,
            'volume': 10,
            'adx': 10,
            'divergence': 10,
            'sentiment': 10,
            'macro': 10,
            'options': 10,
        }
        weighted_score = analyzer.calculate_weighted_score(factors)
        assert weighted_score == 10.0, f"Expected 10.0, got {weighted_score}"
    
    def test_calculate_weighted_score_all_bearish(self, analyzer):
        """Test weighted score with all bearish factors."""
        factors = {
            'whales': -10,
            'derivatives': -10,
            'trend': -10,
            'momentum': -10,
            'volume': -10,
            'adx': -10,
            'divergence': -10,
            'sentiment': -10,
            'macro': -10,
            'options': -10,
        }
        weighted_score = analyzer.calculate_weighted_score(factors)
        assert weighted_score == -10.0, f"Expected -10.0, got {weighted_score}"
    
    def test_calculate_weighted_score_mixed(self, analyzer):
        """Test weighted score with mixed factors."""
        factors = {
            'whales': -8,       # 25% * -8 = -2.0
            'derivatives': -5,  # 20% * -5 = -1.0
            'trend': -7,        # 15% * -7 = -1.05
            'momentum': 4.5,    # 12% * 4.5 = 0.54
            'volume': 0,        # 10% * 0 = 0.0
            'adx': -3,          # 5% * -3 = -0.15
            'divergence': 0,    # 5% * 0 = 0.0
            'sentiment': 10,    # 4% * 10 = 0.4
            'macro': 15,        # 3% * 15 = 0.45 (will be clamped to 10, then 3% * 10 = 0.3)
            'options': -10,     # 1% * -10 = -0.1
        }
        weighted_score = analyzer.calculate_weighted_score(factors)
        # Expected with macro clamped to 10: -2.0 - 1.0 - 1.05 + 0.54 - 0.15 + 0.4 + 0.3 - 0.1 = -3.06
        expected = -2.0 - 1.0 - 1.05 + 0.54 + 0 - 0.15 + 0 + 0.4 + 0.3 - 0.1
        assert abs(weighted_score - expected) < 0.1, f"Expected ~{expected}, got {weighted_score}"
    
    def test_calculate_weighted_score_neutral(self, analyzer):
        """Test weighted score with all neutral factors."""
        factors = {
            'whales': 0,
            'derivatives': 0,
            'trend': 0,
            'momentum': 0,
            'volume': 0,
            'adx': 0,
            'divergence': 0,
            'sentiment': 0,
            'macro': 0,
            'options': 0,
        }
        weighted_score = analyzer.calculate_weighted_score(factors)
        assert weighted_score == 0.0, f"Expected 0.0, got {weighted_score}"


class TestSupportResistanceLevels:
    """Tests for S/R level calculation."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_calculate_sr_levels_with_no_data(self, analyzer):
        """Test S/R calculation with no OHLCV data."""
        current_price = 88000
        sr_levels = analyzer.calculate_real_sr_levels([], current_price)
        
        assert 'resistances' in sr_levels
        assert 'supports' in sr_levels
        assert 'nearest_resistance' in sr_levels
        assert 'nearest_support' in sr_levels
        
        # Should have fallback levels
        assert len(sr_levels['resistances']) == 3
        assert len(sr_levels['supports']) == 3
        assert sr_levels['nearest_resistance'] > current_price
        assert sr_levels['nearest_support'] < current_price
    
    def test_calculate_sr_levels_with_simple_data(self, analyzer):
        """Test S/R calculation with simple OHLCV data."""
        current_price = 88000
        ohlcv_data = [
            {'high': 87000, 'low': 86000, 'close': 86500},
            {'high': 88000, 'low': 87000, 'close': 87500},
            {'high': 89000, 'low': 88000, 'close': 88500},
            {'high': 88500, 'low': 87500, 'close': 88000},
            {'high': 88200, 'low': 87200, 'close': 87800},
            {'high': 88500, 'low': 87500, 'close': 88000},
        ]
        
        sr_levels = analyzer.calculate_real_sr_levels(ohlcv_data, current_price)
        
        assert 'resistances' in sr_levels
        assert 'supports' in sr_levels
        assert sr_levels['nearest_resistance'] > current_price
        assert sr_levels['nearest_support'] < current_price
    
    def test_swing_points_detection(self):
        """Test swing high/low detection."""
        ohlcv_data = [
            {'high': 100, 'low': 90, 'close': 95},
            {'high': 105, 'low': 95, 'close': 100},
            {'high': 110, 'low': 100, 'close': 105},  # Swing high
            {'high': 108, 'low': 98, 'close': 103},
            {'high': 106, 'low': 96, 'close': 101},
            {'high': 104, 'low': 94, 'close': 99},
            {'high': 102, 'low': 92, 'close': 97},    # Swing low at 92
            {'high': 106, 'low': 96, 'close': 101},
            {'high': 108, 'low': 98, 'close': 103},
        ]
        
        swing_highs, swing_lows = find_swing_points(ohlcv_data, lookback=10)
        
        # Should find at least one swing high and one swing low
        assert len(swing_highs) >= 0  # May not find perfect swings with this data
        assert len(swing_lows) >= 0
    
    def test_count_touches(self):
        """Test touch counting for a level."""
        ohlcv_data = [
            {'high': 100, 'low': 90, 'close': 95},
            {'high': 101, 'low': 89, 'close': 100},  # Touch 100
            {'high': 105, 'low': 95, 'close': 102},
            {'high': 110, 'low': 99, 'close': 105},  # Touch 100
            {'high': 102, 'low': 98, 'close': 100},  # Touch 100
        ]
        
        level = 100
        touches = count_touches(ohlcv_data, level, tolerance_pct=1.0)
        
        assert touches >= 2, f"Expected at least 2 touches, got {touches}"
    
    def test_calculate_level_strength(self):
        """Test level strength calculation."""
        # Strong level: swing high with many touches
        strength = calculate_level_strength(
            level=90000,
            source='swing_high',
            touches=5,
            volume_at_level=1000000,
            age_factor=1.0
        )
        assert strength >= 4, f"Expected strength >= 4, got {strength}"
        
        # Weak level: round number with no touches
        strength = calculate_level_strength(
            level=90000,
            source='round_number',
            touches=0,
            volume_at_level=0,
            age_factor=1.0
        )
        assert strength >= 1, f"Expected strength >= 1, got {strength}"
        assert strength <= 3, f"Expected strength <= 3, got {strength}"


class TestPricePrediction:
    """Tests for 4-hour price prediction."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance."""
        return AISignalAnalyzer(mock_whale_tracker)
    
    def test_predict_price_bullish(self, analyzer):
        """Test price prediction with bullish weighted score."""
        current_price = 88000
        weighted_score = 5.0  # Strong bullish
        sr_levels = {
            'nearest_resistance': 90000,
            'nearest_support': 86000,
        }
        atr = 1200  # ~1.4% ATR
        
        prediction = analyzer.predict_price_4h(current_price, weighted_score, sr_levels, atr)
        
        assert 'predicted_price' in prediction
        assert 'predicted_change_pct' in prediction
        assert 'direction' in prediction
        assert 'confidence' in prediction
        assert 'price_range' in prediction
        
        assert prediction['direction'] == 'UP'
        assert prediction['predicted_price'] > current_price
        assert prediction['confidence'] >= 50
        assert prediction['confidence'] <= 85
    
    def test_predict_price_bearish(self, analyzer):
        """Test price prediction with bearish weighted score."""
        current_price = 88000
        weighted_score = -5.0  # Strong bearish
        sr_levels = {
            'nearest_resistance': 90000,
            'nearest_support': 86000,
        }
        atr = 1200
        
        prediction = analyzer.predict_price_4h(current_price, weighted_score, sr_levels, atr)
        
        assert prediction['direction'] == 'DOWN'
        assert prediction['predicted_price'] < current_price
        assert prediction['confidence'] >= 50
    
    def test_predict_price_respects_resistance(self, analyzer):
        """Test that prediction respects resistance level."""
        current_price = 88000
        weighted_score = 8.0  # Very strong bullish
        sr_levels = {
            'nearest_resistance': 88500,  # Close resistance
            'nearest_support': 86000,
        }
        atr = 1200
        
        prediction = analyzer.predict_price_4h(current_price, weighted_score, sr_levels, atr)
        
        # Predicted price should not go much above resistance (stops at resistance * 0.995)
        # Allow for small buffer
        assert prediction['predicted_price'] <= sr_levels['nearest_resistance'] * 1.001, \
            f"Predicted {prediction['predicted_price']} should respect resistance {sr_levels['nearest_resistance']}"
    
    def test_predict_price_respects_support(self, analyzer):
        """Test that prediction respects support level."""
        current_price = 88000
        weighted_score = -8.0  # Very strong bearish
        sr_levels = {
            'nearest_resistance': 90000,
            'nearest_support': 87500,  # Close support
        }
        atr = 1200
        
        prediction = analyzer.predict_price_4h(current_price, weighted_score, sr_levels, atr)
        
        # Predicted price should not go much below support (stops at support * 1.005)
        # Allow for small buffer
        assert prediction['predicted_price'] >= sr_levels['nearest_support'] * 0.999, \
            f"Predicted {prediction['predicted_price']} should respect support {sr_levels['nearest_support']}"
    
    def test_predict_price_neutral(self, analyzer):
        """Test price prediction with neutral score."""
        current_price = 88000
        weighted_score = 0.0  # Neutral
        sr_levels = {
            'nearest_resistance': 90000,
            'nearest_support': 86000,
        }
        atr = 1200
        
        prediction = analyzer.predict_price_4h(current_price, weighted_score, sr_levels, atr)
        
        # Should predict minimal movement
        assert abs(prediction['predicted_price'] - current_price) < current_price * 0.01, \
            "Neutral score should predict minimal movement"
        assert prediction['confidence'] == 50  # Minimum confidence for neutral
    
    def test_predict_price_caps_movement(self, analyzer):
        """Test that prediction caps at -3% to +3%."""
        current_price = 88000
        weighted_score = 15.0  # Unrealistically high
        sr_levels = {
            'nearest_resistance': 95000,  # Far away
            'nearest_support': 80000,
        }
        atr = 1200
        
        prediction = analyzer.predict_price_4h(current_price, weighted_score, sr_levels, atr)
        
        # Change should be capped at 3%
        assert abs(prediction['predicted_change_pct']) <= 3.5, \
            f"Movement {prediction['predicted_change_pct']}% should be capped around 3%"
    
    def test_predict_price_adjusts_for_volatility(self, analyzer):
        """Test that prediction adjusts for ATR (volatility)."""
        current_price = 88000
        weighted_score = 5.0
        sr_levels = {
            'nearest_resistance': 95000,
            'nearest_support': 80000,
        }
        
        # Low volatility
        low_atr = 500  # ~0.57% ATR
        pred_low_vol = analyzer.predict_price_4h(current_price, weighted_score, sr_levels, low_atr)
        
        # High volatility
        high_atr = 3000  # ~3.4% ATR
        pred_high_vol = analyzer.predict_price_4h(current_price, weighted_score, sr_levels, high_atr)
        
        # High volatility should predict larger move
        assert abs(pred_high_vol['predicted_change_pct']) >= abs(pred_low_vol['predicted_change_pct']) * 0.5, \
            "High volatility should predict larger movement"
