#!/usr/bin/env python3
"""
Train ML models for signal validation.

Usage:
    python scripts/train_model.py --symbol BTC --days 365
    python scripts/train_model.py --symbol ETH --days 365
    python scripts/train_model.py --all
"""

import argparse
import asyncio
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ml.data_collector import prepare_training_data
from ml.trainer import train_ensemble, save_models
from ml.config import ML_CONFIG

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def train_for_symbol(symbol: str, days: int = 365):
    """
    Train models for a specific symbol.
    
    Args:
        symbol: Symbol (BTC, ETH)
        days: Number of days of historical data
    """
    logger.info(f"=" * 60)
    logger.info(f"Training ML models for {symbol}")
    logger.info(f"=" * 60)
    
    # Prepare training data
    logger.info(f"Preparing training data for {symbol}...")
    X, y = await prepare_training_data(symbol, days=days)
    
    if X.empty or len(y) == 0:
        logger.error(f"Failed to prepare training data for {symbol}")
        return False
    
    logger.info(f"Training data prepared: {len(X)} samples, {len(X.columns)} features")
    
    # Train ensemble
    logger.info(f"Training ensemble for {symbol}...")
    models_data = train_ensemble(symbol, X, y)
    
    if not models_data.get('models'):
        logger.error(f"No models trained for {symbol}")
        return False
    
    # Save models
    logger.info(f"Saving models for {symbol}...")
    save_models(models_data, symbol)
    
    # Print results
    logger.info(f"\n{'=' * 60}")
    logger.info(f"ML Model trained for {symbol}:")
    
    metrics = models_data.get('metrics', {})
    
    if 'xgboost' in metrics:
        xgb_acc = metrics['xgboost']['accuracy'] * 100
        logger.info(f"├ XGBoost Accuracy: {xgb_acc:.1f}%")
    
    if 'lightgbm' in metrics:
        lgb_acc = metrics['lightgbm']['accuracy'] * 100
        logger.info(f"├ LightGBM Accuracy: {lgb_acc:.1f}%")
    
    if 'ensemble' in metrics:
        ens_acc = metrics['ensemble']['accuracy'] * 100
        logger.info(f"├ Ensemble Accuracy: {ens_acc:.1f}%")
    
    logger.info(f"└ Saved to models/{symbol.lower()}_*.pkl")
    logger.info(f"{'=' * 60}\n")
    
    return True


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Train ML models for signal validation'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        help='Symbol to train (BTC, ETH)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=365,
        help='Number of days of historical data (default: 365)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Train models for all configured symbols'
    )
    
    args = parser.parse_args()
    
    if not args.all and not args.symbol:
        parser.print_help()
        sys.exit(1)
    
    # Determine which symbols to train
    if args.all:
        symbols = ML_CONFIG['coins']
    else:
        symbols = [args.symbol.upper()]
    
    # Validate symbols
    for symbol in symbols:
        if symbol not in ML_CONFIG['coins']:
            logger.error(f"Symbol {symbol} not configured for ML training")
            logger.info(f"Configured symbols: {ML_CONFIG['coins']}")
            sys.exit(1)
    
    # Train for each symbol
    results = []
    for symbol in symbols:
        success = await train_for_symbol(symbol, days=args.days)
        results.append((symbol, success))
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("Training Summary:")
    for symbol, success in results:
        status = "✅ Success" if success else "❌ Failed"
        logger.info(f"  {symbol}: {status}")
    logger.info("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
