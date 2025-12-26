"""
ML Configuration - settings for machine learning models and training.
"""

import os

# Base directory for models
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# ML Configuration
ML_CONFIG = {
    "coins": ["BTC", "ETH"],
    "models": ["xgboost", "lightgbm"],
    "ensemble_weights": {
        "rules": 0.7,
        "ml": 0.3
    },
    "thresholds": {
        "cancel": 0.4,           # < 40% → WAIT (cancel signal)
        "low_confidence": 0.6,   # 40-60% → ⚠️ Low confidence
        "normal": 0.8,           # 60-80% → ✅ Normal signal
        "strong": 0.8            # > 80% → 🔥 Strong signal
    },
    "retrain": {
        "weekly": True,
        "on_accuracy_drop": 0.6,
        "on_new_signals": 100
    },
    "timeframe": "4h",
    "lookback_days": 365,
    "models_dir": MODELS_DIR
}

# Training configuration
TRAINING_CONFIG = {
    "test_size": 0.2,
    "random_state": 42,
    "xgboost": {
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "objective": "multi:softprob",
        "num_class": 4,  # LONG_WIN, LONG_LOSS, SHORT_WIN, SHORT_LOSS
        "eval_metric": "mlogloss",
        "random_state": 42,
        "tree_method": "auto",  # Will use GPU if available
    },
    "lightgbm": {
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "objective": "multiclass",
        "num_class": 4,
        "metric": "multi_logloss",
        "random_state": 42,
        "device": "cpu",  # Will try GPU if available
    }
}

# Labeling configuration
LABELING_CONFIG = {
    "profit_threshold": 0.015,  # 1.5% price movement
    "loss_threshold": -0.01,    # -1% price movement
    "lookback_candles": 1,      # Check next 1 candle (4H)
}

# Feature configuration
FEATURE_CONFIG = {
    "technical_indicators": [
        "rsi", "macd", "macd_signal", "macd_diff",
        "bb_upper", "bb_middle", "bb_lower",
        "ma_50", "ma_200", "ma_crossover",
        "stoch_rsi", "mfi", "roc", "williams_r",
        "atr", "adx", "obv", "vwap"
    ],
    "market_data": [
        "volume", "funding_rate", "open_interest",
        "price_change_1h", "price_change_4h", "price_change_24h",
        "fear_greed_index"
    ],
    "enhancer_scores": [
        "order_flow", "volume_profile", "multi_exchange",
        "liquidations", "smart_money", "wyckoff",
        "on_chain", "whale_tracker", "funding_advanced",
        "volatility"
    ]
}
