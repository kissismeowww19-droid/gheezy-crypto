"""
ML module - Machine learning infrastructure for signal validation.

Provides XGBoost + LightGBM ensemble for validating trading signals
using historical data and enhancer scores.
"""

from .config import ML_CONFIG
from .features import extract_features
from .predictor import predict, load_models
from .ensemble import combine_scores

__all__ = [
    'ML_CONFIG',
    'extract_features',
    'predict',
    'load_models',
    'combine_scores',
]
