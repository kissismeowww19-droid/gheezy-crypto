# ML Infrastructure Quick Start Guide

## 🚀 Quick Start (5 minutes)

### Step 1: Install Dependencies

```bash
pip install xgboost lightgbm scikit-learn joblib pandas numpy aiohttp
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### Step 2: Train Models

Train models for BTC and ETH with 1 year of historical data:

```bash
python scripts/train_model.py --all
```

This will:
- Download 1 year of 4H candles from Binance
- Calculate technical indicators
- Create training labels
- Train XGBoost and LightGBM models
- Save models to `models/` directory

**Expected time**: 5-10 minutes (depending on internet speed)

### Step 3: Verify Installation

Check that models were created:

```bash
ls -lh models/
```

You should see:
```
btc_xgboost.pkl
btc_lightgbm.pkl
btc_metadata.pkl
eth_xgboost.pkl
eth_lightgbm.pkl
eth_metadata.pkl
```

### Step 4: Test Integration

Run the tests to verify everything works:

```bash
pytest tests/test_ml.py -v
```

Expected output:
```
13 passed in 0.97s ✅
```

### Step 5: Use in Production

The ML infrastructure is now integrated into AI signals. When you generate a signal for BTC or ETH:

```python
# In your bot or API
analyzer = AISignalAnalyzer()
message = await analyzer.analyze_coin("BTC")
```

The signal will automatically include ML confidence:

```
📈 LONG BTC

💰 Вход: $87,200
🎯 TP1: $88,500
🛑 SL: $85,800

📊 Уверенность: 75%
🤖 ML Score: 78% ✅    ← ML confidence!

🔥 Сигналы:
├ RSI: 28
├ MACD: bullish
└ ML: Strong signal 🔥   ← ML recommendation!
```

## 📊 Understanding Output

### During Training

```
============================================================
Training ML models for BTC
============================================================
Preparing training data for BTC...
Training data prepared: 2190 samples, 50 features

Training ensemble for BTC...
Training XGBoost...
XGBoost Validation Accuracy: 0.7247

Training LightGBM...
LightGBM Validation Accuracy: 0.7019

Saving models for BTC...
Saved XGBoost model to models/btc_xgboost.pkl
Saved LightGBM model to models/btc_lightgbm.pkl
Saved metadata to models/btc_metadata.pkl

============================================================
ML Model trained for BTC:
├ XGBoost Accuracy: 72%
├ LightGBM Accuracy: 70%
├ Ensemble Accuracy: 74%
└ Saved to models/btc_*.pkl
============================================================
```

### In Signals

When ML validates a signal, you'll see in logs:

```
INFO: Running ML validation for BTC...
INFO: ML prediction for BTC: confidence=78.0%, recommendation=strong
```

## 🔧 Configuration

### Change Training Period

Train with more historical data for better accuracy:

```bash
# 2 years of data
python scripts/train_model.py --symbol BTC --days 730

# 6 months of data (faster)
python scripts/train_model.py --symbol BTC --days 180
```

### Adjust Thresholds

Edit `src/ml/config.py`:

```python
"thresholds": {
    "cancel": 0.3,           # Lower = more aggressive cancellation
    "low_confidence": 0.5,   # Adjust confidence levels
    "normal": 0.7,
    "strong": 0.85           # Higher = stricter strong signal
}
```

### Change Ensemble Weights

Balance between rules and ML:

```python
"ensemble_weights": {
    "rules": 0.6,  # 60% rules
    "ml": 0.4      # 40% ML (more weight on ML)
}
```

## 🐛 Troubleshooting

### Problem: No module named 'xgboost'

**Solution**:
```bash
pip install xgboost lightgbm scikit-learn
```

### Problem: Models not found

**Solution**: Train models first
```bash
python scripts/train_model.py --all
```

### Problem: Low accuracy (< 60%)

**Solution**: Train with more data
```bash
python scripts/train_model.py --symbol BTC --days 730
```

### Problem: Download fails

**Solution**: Check Binance API is accessible
```bash
curl https://api.binance.com/api/v3/ping
```

## 📚 Next Steps

1. **Read Full Docs**: See `docs/ML_INFRASTRUCTURE.md`
2. **Monitor Performance**: Track ML confidence over time
3. **Retrain Regularly**: Weekly or when accuracy drops
4. **Tune Parameters**: Adjust thresholds for your strategy

## 💡 Tips

- **Start with BTC**: More data available, better accuracy
- **Use GPU**: Set `tree_method: "gpu_hist"` for faster training
- **Monitor Accuracy**: Retrain if drops below 60%
- **Test First**: Use on paper trading before live
- **Keep Models Updated**: Market patterns change over time

## 🎯 Expected Results

With 1 year of training data:

| Model | Accuracy | Notes |
|-------|----------|-------|
| XGBoost | 70-75% | Primary model |
| LightGBM | 68-73% | Secondary model |
| Ensemble | 72-76% | Best overall |

## 🔄 Maintenance

### Weekly Retraining

```bash
# Add to cron or scheduler
0 0 * * 0 python scripts/train_model.py --all
```

### Check Model Performance

```python
from ml.trainer import load_models

models_data = load_models('BTC')
metrics = models_data['metadata']['metrics']
print(f"Accuracy: {metrics['ensemble']['accuracy']:.2%}")
```

## ✅ Success Criteria

You've successfully set up the ML infrastructure if:

- [x] All dependencies installed
- [x] Models trained for BTC and ETH
- [x] Tests pass (13/13)
- [x] Signals show ML confidence
- [x] ML recommendations appear in signals

Ready to use! 🎉
