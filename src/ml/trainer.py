"""
Model trainer for XGBoost and LightGBM ensemble.
"""

import os
import joblib
import logging
from typing import Dict, Tuple
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report

logger = logging.getLogger(__name__)

# Import with fallback
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    logger.warning("XGBoost not available")
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    logger.warning("LightGBM not available")
    LIGHTGBM_AVAILABLE = False


def train_xgboost(X: pd.DataFrame, y: pd.Series, config: Dict = None) -> xgb.Booster:
    """
    Train XGBoost model.
    
    Args:
        X: Features DataFrame
        y: Labels Series
        config: Training configuration
    
    Returns:
        Trained XGBoost model
    """
    if not XGBOOST_AVAILABLE:
        raise ImportError("XGBoost is not installed")
    
    from ml.config import TRAINING_CONFIG
    if config is None:
        config = TRAINING_CONFIG['xgboost']
    
    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=TRAINING_CONFIG['test_size'],
        random_state=TRAINING_CONFIG['random_state'], stratify=y
    )
    
    # Create DMatrix
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dval = xgb.DMatrix(X_val, label=y_val)
    
    # Training parameters
    params = config.copy()
    
    # Train model
    evals = [(dtrain, 'train'), (dval, 'val')]
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=params.get('n_estimators', 100),
        evals=evals,
        early_stopping_rounds=10,
        verbose_eval=False
    )
    
    # Calculate metrics
    y_pred = model.predict(dval)
    y_pred_labels = np.argmax(y_pred, axis=1)
    
    accuracy = accuracy_score(y_val, y_pred_labels)
    logger.info(f"XGBoost Validation Accuracy: {accuracy:.4f}")
    
    return model


def train_lightgbm(X: pd.DataFrame, y: pd.Series, config: Dict = None) -> lgb.Booster:
    """
    Train LightGBM model.
    
    Args:
        X: Features DataFrame
        y: Labels Series
        config: Training configuration
    
    Returns:
        Trained LightGBM model
    """
    if not LIGHTGBM_AVAILABLE:
        raise ImportError("LightGBM is not installed")
    
    from ml.config import TRAINING_CONFIG
    if config is None:
        config = TRAINING_CONFIG['lightgbm']
    
    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=TRAINING_CONFIG['test_size'],
        random_state=TRAINING_CONFIG['random_state'], stratify=y
    )
    
    # Create datasets
    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
    
    # Training parameters
    params = config.copy()
    num_round = params.pop('n_estimators', 100)
    
    # Train model
    model = lgb.train(
        params,
        train_data,
        num_boost_round=num_round,
        valid_sets=[train_data, val_data],
        valid_names=['train', 'val'],
        callbacks=[lgb.early_stopping(stopping_rounds=10), lgb.log_evaluation(period=0)]
    )
    
    # Calculate metrics
    y_pred = model.predict(X_val)
    y_pred_labels = np.argmax(y_pred, axis=1)
    
    accuracy = accuracy_score(y_val, y_pred_labels)
    logger.info(f"LightGBM Validation Accuracy: {accuracy:.4f}")
    
    return model


def train_ensemble(symbol: str, X: pd.DataFrame, y: pd.Series) -> Dict:
    """
    Train ensemble of XGBoost and LightGBM.
    
    Args:
        symbol: Symbol (BTC, ETH)
        X: Features DataFrame
        y: Labels Series
    
    Returns:
        Dict with trained models and metrics
    """
    logger.info(f"Training ensemble for {symbol}")
    
    models = {}
    metrics = {}
    
    # Split data for final evaluation
    from ml.config import TRAINING_CONFIG
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TRAINING_CONFIG['test_size'],
        random_state=TRAINING_CONFIG['random_state'], stratify=y
    )
    
    # Train XGBoost
    if XGBOOST_AVAILABLE:
        try:
            logger.info("Training XGBoost...")
            xgb_model = train_xgboost(X, y)
            models['xgboost'] = xgb_model
            
            # Evaluate
            dtest = xgb.DMatrix(X_test)
            y_pred = xgb_model.predict(dtest)
            y_pred_labels = np.argmax(y_pred, axis=1)
            
            metrics['xgboost'] = {
                'accuracy': accuracy_score(y_test, y_pred_labels),
                'precision': precision_score(y_test, y_pred_labels, average='weighted', zero_division=0),
                'recall': recall_score(y_test, y_pred_labels, average='weighted', zero_division=0),
                'f1': f1_score(y_test, y_pred_labels, average='weighted', zero_division=0)
            }
            
            logger.info(f"XGBoost metrics: {metrics['xgboost']}")
        except Exception as e:
            logger.error(f"Error training XGBoost: {e}")
    
    # Train LightGBM
    if LIGHTGBM_AVAILABLE:
        try:
            logger.info("Training LightGBM...")
            lgb_model = train_lightgbm(X, y)
            models['lightgbm'] = lgb_model
            
            # Evaluate
            y_pred = lgb_model.predict(X_test)
            y_pred_labels = np.argmax(y_pred, axis=1)
            
            metrics['lightgbm'] = {
                'accuracy': accuracy_score(y_test, y_pred_labels),
                'precision': precision_score(y_test, y_pred_labels, average='weighted', zero_division=0),
                'recall': recall_score(y_test, y_pred_labels, average='weighted', zero_division=0),
                'f1': f1_score(y_test, y_pred_labels, average='weighted', zero_division=0)
            }
            
            logger.info(f"LightGBM metrics: {metrics['lightgbm']}")
        except Exception as e:
            logger.error(f"Error training LightGBM: {e}")
    
    # Calculate ensemble metrics
    if 'xgboost' in models and 'lightgbm' in models:
        try:
            # Simple average ensemble
            dtest = xgb.DMatrix(X_test)
            xgb_pred = models['xgboost'].predict(dtest)
            lgb_pred = models['lightgbm'].predict(X_test)
            
            ensemble_pred = (xgb_pred + lgb_pred) / 2
            ensemble_labels = np.argmax(ensemble_pred, axis=1)
            
            metrics['ensemble'] = {
                'accuracy': accuracy_score(y_test, ensemble_labels),
                'precision': precision_score(y_test, ensemble_labels, average='weighted', zero_division=0),
                'recall': recall_score(y_test, ensemble_labels, average='weighted', zero_division=0),
                'f1': f1_score(y_test, ensemble_labels, average='weighted', zero_division=0)
            }
            
            logger.info(f"Ensemble metrics: {metrics['ensemble']}")
        except Exception as e:
            logger.error(f"Error calculating ensemble metrics: {e}")
    
    return {
        'models': models,
        'metrics': metrics,
        'feature_names': X.columns.tolist()
    }


def save_models(models_data: Dict, symbol: str):
    """
    Save trained models to disk.
    
    Args:
        models_data: Dict with models and metadata
        symbol: Symbol (BTC, ETH)
    """
    from ml.config import ML_CONFIG
    models_dir = ML_CONFIG['models_dir']
    
    # Create models directory if it doesn't exist
    os.makedirs(models_dir, exist_ok=True)
    
    models = models_data['models']
    
    # Save XGBoost
    if 'xgboost' in models:
        xgb_path = os.path.join(models_dir, f"{symbol.lower()}_xgboost.pkl")
        joblib.dump(models['xgboost'], xgb_path)
        logger.info(f"Saved XGBoost model to {xgb_path}")
    
    # Save LightGBM
    if 'lightgbm' in models:
        lgb_path = os.path.join(models_dir, f"{symbol.lower()}_lightgbm.pkl")
        joblib.dump(models['lightgbm'], lgb_path)
        logger.info(f"Saved LightGBM model to {lgb_path}")
    
    # Save metadata
    metadata = {
        'symbol': symbol,
        'metrics': models_data['metrics'],
        'feature_names': models_data['feature_names']
    }
    metadata_path = os.path.join(models_dir, f"{symbol.lower()}_metadata.pkl")
    joblib.dump(metadata, metadata_path)
    logger.info(f"Saved metadata to {metadata_path}")


def load_models(symbol: str) -> Dict:
    """
    Load trained models from disk.
    
    Args:
        symbol: Symbol (BTC, ETH)
    
    Returns:
        Dict with loaded models and metadata
    """
    from ml.config import ML_CONFIG
    models_dir = ML_CONFIG['models_dir']
    
    models = {}
    
    # Load XGBoost
    xgb_path = os.path.join(models_dir, f"{symbol.lower()}_xgboost.pkl")
    if os.path.exists(xgb_path):
        models['xgboost'] = joblib.load(xgb_path)
        logger.info(f"Loaded XGBoost model from {xgb_path}")
    
    # Load LightGBM
    lgb_path = os.path.join(models_dir, f"{symbol.lower()}_lightgbm.pkl")
    if os.path.exists(lgb_path):
        models['lightgbm'] = joblib.load(lgb_path)
        logger.info(f"Loaded LightGBM model from {lgb_path}")
    
    # Load metadata
    metadata_path = os.path.join(models_dir, f"{symbol.lower()}_metadata.pkl")
    metadata = {}
    if os.path.exists(metadata_path):
        metadata = joblib.load(metadata_path)
        logger.info(f"Loaded metadata from {metadata_path}")
    
    return {
        'models': models,
        'metadata': metadata
    }
