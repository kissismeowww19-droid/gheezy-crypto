# ML Infrastructure for Signal Validation

## Overview

This ML infrastructure adds machine learning validation to trading signals using an XGBoost + LightGBM ensemble. It provides confidence scores and recommendations to improve signal quality.

## Architecture

### Components

1. **Data Collector** (`src/ml/data_collector.py`)
   - Downloads historical OHLCV data from Binance
   - Calculates technical indicators
   - Creates training labels based on price movements

2. **Feature Extractor** (`src/ml/features.py`)
   - Extracts 50+ features from candles and indicators
   - Includes technical indicators (RSI, MACD, BB, etc.)
   - Includes market data (volume, funding, OI)
   - Includes enhancer scores (Order Flow, Volume Profile, etc.)

3. **Trainer** (`src/ml/trainer.py`)
   - Trains XGBoost and LightGBM models
   - Saves models to disk with joblib
   - Calculates performance metrics

4. **Predictor** (`src/ml/predictor.py`)
   - Loads trained models
   - Makes predictions for live signals
   - Returns confidence scores and recommendations

5. **Ensemble** (`src/ml/ensemble.py`)
   - Combines rules-based (70%) + ML (30%) scores
   - Provides final recommendations

## Configuration

### ML Config (`src/ml/config.py`)

```python
ML_CONFIG = {
    "coins": ["BTC", "ETH"],
    "models": ["xgboost", "lightgbm"],
    "ensemble_weights": {"rules": 0.7, "ml": 0.3},
    "thresholds": {
        "cancel": 0.4,           # < 40% → WAIT
        "low_confidence": 0.6,   # 40-60% → ⚠️ Low
        "normal": 0.8,           # 60-80% → ✅ Normal
        "strong": 0.8            # > 80% → 🔥 Strong
    },
    "retrain": {
        "weekly": True,
        "on_accuracy_drop": 0.6,
        "on_new_signals": 100
    },
    "timeframe": "4h",
    "lookback_days": 365
}
```

### Training Config

- **Test size**: 20% validation split
- **XGBoost**: 100 estimators, max_depth=6, learning_rate=0.1
- **LightGBM**: 100 estimators, max_depth=6, learning_rate=0.1
- **Labeling**: 1.5% profit threshold, -1% loss threshold

## Training Models

### Prerequisites

Install ML dependencies:
```bash
pip install xgboost lightgbm scikit-learn joblib pandas numpy
```

### Train for Single Symbol

```bash
# Train BTC model with 1 year of data
python scripts/train_model.py --symbol BTC --days 365

# Train ETH model with 6 months of data
python scripts/train_model.py --symbol ETH --days 180
```

### Train All Models

```bash
# Train models for all configured symbols (BTC, ETH)
python scripts/train_model.py --all
```

### Expected Output

```
============================================================
ML Model trained for BTC:
├ XGBoost Accuracy: 72%
├ LightGBM Accuracy: 70%
├ Ensemble Accuracy: 74%
└ Saved to models/btc_*.pkl
============================================================
```

## Models Directory

After training, models are saved to:
```
models/
├── btc_xgboost.pkl      # XGBoost model for BTC
├── btc_lightgbm.pkl     # LightGBM model for BTC
├── btc_metadata.pkl     # Metadata (metrics, features)
├── eth_xgboost.pkl      # XGBoost model for ETH
├── eth_lightgbm.pkl     # LightGBM model for ETH
└── eth_metadata.pkl     # Metadata
```

**Note**: Models are excluded from git (see `.gitignore`)

## Integration

### In AI Signals

ML validation is integrated into `src/signals/ai_signals.py`:

1. After calculating signal, extract features
2. Make ML prediction
3. Add ML confidence to signal data
4. Display in message

### Signal Display

Signals now show ML confidence:

```
📈 LONG BTC

💰 Вход: $87,200
🎯 TP1: $88,500
🛑 SL: $85,800

📊 Уверенность: 75%
🤖 ML Score: 78% ✅    ← NEW!

🔥 Сигналы:
├ RSI: 28
├ MACD: bullish
└ ML: Strong signal 🔥   ← NEW!
```

### Recommendation Logic

- **< 40%**: ⚠️ WAIT (cancel signal)
- **40-60%**: ⚠️ Low confidence
- **60-80%**: ✅ Normal signal
- **> 80%**: 🔥 Strong signal

## Features

The ML models use 50+ features:

### Technical Indicators
- RSI, MACD, Bollinger Bands
- Moving Averages (50, 200)
- Stochastic RSI, MFI, ROC
- Williams %R, ATR, ADX
- OBV, VWAP

### Market Data
- Volume (24h)
- Funding Rate
- Open Interest
- Price changes (1h, 4h, 24h)
- Fear & Greed Index

### Enhancer Scores
- Order Flow
- Volume Profile
- Multi-Exchange
- Liquidations
- Smart Money
- Wyckoff
- On-Chain
- Whale Tracker
- Funding Advanced
- Volatility

## Labels

Training labels are created based on next 4H candle:

- **LONG_WIN** (0): Price went up ≥ 1.5%
- **LONG_LOSS** (1): Price went down ≤ -1%
- **SHORT_WIN** (2): Price went down ≥ 1.5%
- **SHORT_LOSS** (3): Price went up ≥ -1%

## Testing

Run ML tests:
```bash
pytest tests/test_ml.py -v
```

Tests cover:
- Configuration validation
- Feature extraction
- Label creation
- Ensemble combination
- 13 tests, all passing ✅

## Retraining

Models should be retrained:
- **Weekly**: To capture new market patterns
- **On accuracy drop**: If accuracy < 60%
- **Every 100 signals**: To improve with new data

To retrain:
```bash
python scripts/train_model.py --all
```

## Performance

Expected accuracy on historical data:
- **XGBoost**: 70-75%
- **LightGBM**: 68-73%
- **Ensemble**: 72-76%

## GPU Support

Models support GPU training:
- **XGBoost**: Set `tree_method: "gpu_hist"` in config
- **LightGBM**: Set `device: "gpu"` in config

Auto-detected if CUDA is available.

## Troubleshooting

### Models not found
```
WARNING: No trained models found for BTC
```
**Solution**: Train models first with `python scripts/train_model.py --all`

### Import errors
```
ModuleNotFoundError: No module named 'xgboost'
```
**Solution**: Install dependencies with `pip install -r requirements.txt`

### Low accuracy
**Solution**: 
- Increase training data (use `--days 730` for 2 years)
- Adjust thresholds in `src/ml/config.py`
- Retrain with more recent data

## API

### Predict

```python
from ml.predictor import predict

# Features dict with required keys
features = {
    'rsi': 65.0,
    'macd': 0.5,
    'close': 50000,
    'volume': 1000000,
    # ... other features
}

result = predict('BTC', features)
# {
#     "ml_confidence": 0.75,
#     "xgboost_pred": 0.78,
#     "lightgbm_pred": 0.72,
#     "recommendation": "normal",
#     "should_cancel": False
# }
```

### Combine Scores

```python
from ml.ensemble import combine_scores

ml_prediction = {"ml_confidence": 0.8, ...}
result = combine_scores(70.0, ml_prediction)
# {
#     "final_confidence": 73.0,  # 70*0.7 + 80*0.3
#     "rules_contribution": 49.0,
#     "ml_contribution": 24.0,
#     "recommendation": "normal"
# }
```

## Future Improvements

- [ ] Add more features (orderbook depth, whale alerts)
- [ ] Implement auto-retraining on schedule
- [ ] Add model versioning
- [ ] Support more symbols (SOL, DOGE, etc.)
- [ ] Implement hyperparameter tuning
- [ ] Add LSTM for sequence prediction
- [ ] Track model drift metrics
