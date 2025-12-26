"""
Predictor for ML models - makes predictions for new signals.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Import with fallback
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


def predict(symbol: str, features: Dict) -> Dict:
    """
    Make prediction for new signal.
    
    Args:
        symbol: Symbol (BTC, ETH)
        features: Dict with extracted features
    
    Returns:
        Dict with prediction results:
        {
            "ml_confidence": 0.75,
            "xgboost_pred": 0.78,
            "lightgbm_pred": 0.72,
            "recommendation": "normal",
            "should_cancel": False
        }
    """
    from ml.config import ML_CONFIG
    from ml.trainer import load_models
    
    # Check if symbol is supported
    if symbol not in ML_CONFIG['coins']:
        logger.warning(f"ML not configured for {symbol}")
        return {
            "ml_confidence": 0.5,
            "xgboost_pred": 0.5,
            "lightgbm_pred": 0.5,
            "recommendation": "normal",
            "should_cancel": False
        }
    
    try:
        # Load models
        models_data = load_models(symbol)
        models = models_data.get('models', {})
        
        if not models:
            logger.warning(f"No trained models found for {symbol}")
            return {
                "ml_confidence": 0.5,
                "xgboost_pred": 0.5,
                "lightgbm_pred": 0.5,
                "recommendation": "normal",
                "should_cancel": False
            }
        
        # Prepare features
        feature_names = models_data.get('metadata', {}).get('feature_names', [])
        
        # Convert features dict to DataFrame
        features_df = pd.DataFrame([features])
        
        # Ensure all columns are numeric to avoid dtype errors
        for col in features_df.columns:
            features_df[col] = pd.to_numeric(features_df[col], errors='coerce').fillna(0.0)
        
        # Ensure all required features are present
        for feature_name in feature_names:
            if feature_name not in features_df.columns:
                features_df[feature_name] = 0.0
        
        # Select only required features in correct order
        features_df = features_df[feature_names]
        
        predictions = {}
        
        # XGBoost prediction
        if 'xgboost' in models and XGBOOST_AVAILABLE:
            try:
                dmatrix = xgb.DMatrix(features_df)
                xgb_pred = models['xgboost'].predict(dmatrix)[0]
                
                # Get confidence for LONG_WIN (class 0)
                predictions['xgboost'] = float(xgb_pred[0])
            except Exception as e:
                logger.error(f"XGBoost prediction error: {e}")
                predictions['xgboost'] = 0.5
        
        # LightGBM prediction
        if 'lightgbm' in models and LIGHTGBM_AVAILABLE:
            try:
                lgb_pred = models['lightgbm'].predict(features_df)[0]
                
                # Get confidence for LONG_WIN (class 0)
                predictions['lightgbm'] = float(lgb_pred[0])
            except Exception as e:
                logger.error(f"LightGBM prediction error: {e}")
                predictions['lightgbm'] = 0.5
        
        # Calculate ensemble confidence
        if predictions:
            ml_confidence = np.mean(list(predictions.values()))
        else:
            ml_confidence = 0.5
        
        # Determine recommendation based on thresholds
        thresholds = ML_CONFIG['thresholds']
        
        if ml_confidence < thresholds['cancel']:
            recommendation = "wait"
            should_cancel = True
        elif ml_confidence < thresholds['low_confidence']:
            recommendation = "low_confidence"
            should_cancel = False
        elif ml_confidence <= thresholds['normal']:
            recommendation = "normal"
            should_cancel = False
        else:
            recommendation = "strong"
            should_cancel = False
        
        result = {
            "ml_confidence": float(ml_confidence),
            "xgboost_pred": predictions.get('xgboost', 0.5),
            "lightgbm_pred": predictions.get('lightgbm', 0.5),
            "recommendation": recommendation,
            "should_cancel": should_cancel
        }
        
        logger.info(f"ML prediction for {symbol}: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error making prediction for {symbol}: {e}")
        return {
            "ml_confidence": 0.5,
            "xgboost_pred": 0.5,
            "lightgbm_pred": 0.5,
            "recommendation": "normal",
            "should_cancel": False
        }


def load_models(symbol: str) -> Dict:
    """
    Load trained models for a symbol.
    Wrapper function that imports from trainer.
    
    Args:
        symbol: Symbol (BTC, ETH)
    
    Returns:
        Dict with models and metadata
    """
    from ml.trainer import load_models as _load_models
    return _load_models(symbol)
