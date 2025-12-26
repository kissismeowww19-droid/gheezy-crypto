"""
Tests for ML module.
"""

import pytest
import asyncio
import sys
import os
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ml.config import ML_CONFIG, TRAINING_CONFIG, LABELING_CONFIG, FEATURE_CONFIG
from ml.features import extract_features, extract_features_from_signal_data
from ml.ensemble import combine_scores


class TestMLConfig:
    """Tests for ML configuration."""
    
    def test_ml_config_structure(self):
        """Test ML_CONFIG has required keys."""
        assert 'coins' in ML_CONFIG
        assert 'models' in ML_CONFIG
        assert 'ensemble_weights' in ML_CONFIG
        assert 'thresholds' in ML_CONFIG
        
    def test_ensemble_weights(self):
        """Test ensemble weights sum to 1."""
        weights = ML_CONFIG['ensemble_weights']
        assert weights['rules'] + weights['ml'] == 1.0
        
    def test_thresholds(self):
        """Test thresholds are in correct order."""
        thresholds = ML_CONFIG['thresholds']
        assert thresholds['cancel'] < thresholds['low_confidence']
        assert thresholds['low_confidence'] < thresholds['normal']


class TestFeatureExtraction:
    """Tests for feature extraction."""
    
    def test_extract_features_basic(self):
        """Test basic feature extraction."""
        # Create sample candles
        candles = [
            {'open': 100, 'high': 105, 'low': 95, 'close': 102, 'volume': 1000},
            {'open': 102, 'high': 108, 'low': 101, 'close': 106, 'volume': 1200},
            {'open': 106, 'high': 110, 'low': 104, 'close': 108, 'volume': 1100},
        ]
        
        features = extract_features(candles)
        
        assert not features.empty
        assert 'close' in features.columns
        assert 'volume' in features.columns
        assert len(features) == 3
        
    def test_extract_features_with_indicators(self):
        """Test feature extraction with indicators."""
        candles = [
            {'open': 100, 'high': 105, 'low': 95, 'close': 102, 'volume': 1000},
            {'open': 102, 'high': 108, 'low': 101, 'close': 106, 'volume': 1200},
        ]
        
        indicators = {
            'rsi': 65.0,
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_diff': 0.2,
        }
        
        features = extract_features(candles, indicators=indicators)
        
        assert not features.empty
        assert 'rsi' in features.columns
        assert 'macd' in features.columns
    
    def test_extract_features_with_bollinger_bands_array(self):
        """Test feature extraction with Bollinger Bands as arrays (pandas Series)."""
        candles = [
            {'open': 100, 'high': 105, 'low': 95, 'close': 102, 'volume': 1000},
            {'open': 102, 'high': 108, 'low': 101, 'close': 106, 'volume': 1200},
            {'open': 106, 'high': 110, 'low': 104, 'close': 108, 'volume': 1100},
        ]
        
        # Create indicators with Bollinger Bands as pandas Series (array-like)
        indicators = {
            'rsi': pd.Series([50.0, 55.0, 60.0]),
            'macd': pd.Series([0.3, 0.4, 0.5]),
            'macd_signal': pd.Series([0.2, 0.3, 0.4]),
            'macd_diff': pd.Series([0.1, 0.1, 0.1]),
            'bb_upper': pd.Series([110, 115, 120]),
            'bb_middle': pd.Series([100, 105, 108]),
            'bb_lower': pd.Series([90, 95, 96]),
        }
        
        # This should not raise ValueError about ambiguous array comparison
        features = extract_features(candles, indicators=indicators)
        
        assert not features.empty
        assert 'bb_position' in features.columns
        assert 'bb_upper' in features.columns
        assert 'bb_lower' in features.columns
        # Verify bb_position is calculated correctly
        assert len(features) == 3
        # All bb_position values should be between 0 and 1 (or slightly outside due to price movement)
        assert all(features['bb_position'] >= -0.5)
        assert all(features['bb_position'] <= 1.5)
    
    def test_extract_features_with_zero_bb_range(self):
        """Test feature extraction with zero Bollinger Bands range."""
        candles = [
            {'open': 100, 'high': 105, 'low': 95, 'close': 102, 'volume': 1000},
            {'open': 102, 'high': 108, 'low': 101, 'close': 106, 'volume': 1200},
        ]
        
        # Create indicators where BB range is zero (upper == lower)
        indicators = {
            'rsi': pd.Series([50.0, 55.0]),
            'bb_upper': pd.Series([100, 100]),  # Same as lower
            'bb_middle': pd.Series([100, 100]),
            'bb_lower': pd.Series([100, 100]),  # Same as upper
        }
        
        # This should not raise division by zero error
        features = extract_features(candles, indicators=indicators)
        
        assert not features.empty
        assert 'bb_position' in features.columns
        # When range is zero, position should be 0.5 (neutral)
        assert all(features['bb_position'] == 0.5)
        
    def test_extract_features_empty_candles(self):
        """Test feature extraction with empty candles."""
        features = extract_features([])
        assert features.empty
        
    def test_extract_features_from_signal_data(self):
        """Test feature extraction from signal data."""
        signal_data = {
            'price_change_1h': 1.5,
            'price_change_4h': 2.5,
            'price_change_24h': 5.0,
            'funding_rate': 0.0001,
            'fear_greed': 65,
            'enhancer_data': {
                'order_flow': 2.0,
                'volume_profile': 1.5,
            }
        }
        
        technical_data = {
            'rsi': 60.0,
            'macd': 0.5,
        }
        
        market_data = {
            'price_usd': 50000,
            'volume_24h': 1000000,
        }
        
        features = extract_features_from_signal_data(signal_data, technical_data, market_data)
        
        assert 'close' in features
        assert 'rsi' in features
        assert features['rsi'] == 60.0


class TestEnsemble:
    """Tests for ensemble system."""
    
    def test_combine_scores_basic(self):
        """Test basic score combination."""
        rules_score = 70.0
        ml_prediction = {
            'ml_confidence': 0.8,
            'recommendation': 'strong',
            'should_cancel': False
        }
        
        result = combine_scores(rules_score, ml_prediction)
        
        assert 'final_confidence' in result
        assert 'rules_contribution' in result
        assert 'ml_contribution' in result
        assert 'recommendation' in result
        
    def test_combine_scores_weights(self):
        """Test score combination respects weights."""
        rules_score = 70.0
        ml_prediction = {
            'ml_confidence': 0.8,
            'recommendation': 'strong',
            'should_cancel': False
        }
        
        result = combine_scores(rules_score, ml_prediction)
        
        # Rules: 70 * 0.7 = 49
        # ML: 80 * 0.3 = 24
        # Total: 73
        expected_rules = 70.0 * 0.7
        expected_ml = 80.0 * 0.3
        
        assert abs(result['rules_contribution'] - expected_rules) < 0.1
        assert abs(result['ml_contribution'] - expected_ml) < 0.1
        
    def test_combine_scores_cancel(self):
        """Test score combination with ML cancel."""
        rules_score = 70.0
        ml_prediction = {
            'ml_confidence': 0.3,
            'recommendation': 'wait',
            'should_cancel': True
        }
        
        result = combine_scores(rules_score, ml_prediction)
        
        assert result['should_cancel'] == True
        assert result['recommendation'] == 'wait'


class TestDataCollector:
    """Tests for data collector (mocked)."""
    
    def test_create_labels_long_win(self):
        """Test label creation for LONG_WIN."""
        from ml.data_collector import create_labels
        
        # Create sample data with price going up
        df = pd.DataFrame({
            'close': [100, 102, 105, 110]
        })
        
        labels = create_labels(df, profit_threshold=0.015)
        
        # First label should be LONG_WIN (0) because price went from 100 to 102 (2%)
        assert labels.iloc[0] == 0
        
    def test_create_labels_short_win(self):
        """Test label creation for SHORT_WIN."""
        from ml.data_collector import create_labels
        
        # Create sample data with price going down
        df = pd.DataFrame({
            'close': [100, 95, 92, 90]
        })
        
        labels = create_labels(df, loss_threshold=-0.01)
        
        # First label should be SHORT_WIN (2) because price went down significantly
        assert labels.iloc[0] == 2


@pytest.mark.asyncio
class TestDataCollectorAsync:
    """Async tests for data collector."""
    
    async def test_download_historical_data_structure(self):
        """Test that download returns proper structure (mocked)."""
        # This test would need network access, so we'll just test the structure
        # In real usage, you'd mock the API calls
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
