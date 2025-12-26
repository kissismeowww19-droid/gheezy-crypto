"""
Data collector for ML models - downloads historical data from Binance API.
"""

import aiohttp
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Optional
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

logger = logging.getLogger(__name__)

BINANCE_API_URL = "https://api.binance.com/api/v3/klines"


async def download_historical_data(symbol: str, days: int = 365, interval: str = "4h") -> pd.DataFrame:
    """
    Download historical OHLCV data from Binance API.
    
    Args:
        symbol: Symbol (BTC, ETH)
        days: Number of days of historical data
        interval: Timeframe (4h, 1h, etc.)
    
    Returns:
        pd.DataFrame with OHLCV data
    """
    binance_symbol = f"{symbol}USDT"
    
    # Calculate start time
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)
    
    logger.info(f"Downloading {days} days of {interval} data for {symbol}")
    
    all_candles = []
    
    async with aiohttp.ClientSession() as session:
        current_start = start_ts
        
        while current_start < end_ts:
            params = {
                'symbol': binance_symbol,
                'interval': interval,
                'startTime': current_start,
                'endTime': end_ts,
                'limit': 1000  # Max limit per request
            }
            
            try:
                async with session.get(BINANCE_API_URL, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if not data:
                            break
                        
                        all_candles.extend(data)
                        
                        # Update start time for next batch
                        current_start = data[-1][0] + 1
                        
                        logger.debug(f"Downloaded {len(data)} candles, total: {len(all_candles)}")
                        
                        # Rate limiting
                        await asyncio.sleep(0.2)
                    else:
                        logger.error(f"Error fetching data: {response.status}")
                        break
                        
            except Exception as e:
                logger.error(f"Error downloading data: {e}")
                break
    
    if not all_candles:
        logger.error(f"No data downloaded for {symbol}")
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(all_candles, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    # Convert types
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    
    logger.info(f"Downloaded {len(df)} candles for {symbol}")
    
    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]


def calculate_indicators_for_training(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate technical indicators for training data.
    
    Args:
        df: DataFrame with OHLCV data
    
    Returns:
        DataFrame with added indicator columns
    """
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_diff'] = df['macd'] - df['macd_signal']
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # Moving averages
    df['ma_50'] = df['close'].rolling(window=50).mean()
    df['ma_200'] = df['close'].rolling(window=200).mean()
    
    # Additional indicators
    df['atr'] = ((df['high'] - df['low']) + 
                 abs(df['high'] - df['close'].shift(1)) + 
                 abs(df['low'] - df['close'].shift(1))) / 3
    df['atr'] = df['atr'].rolling(window=14).mean()
    
    # Volume SMA
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    
    # Fill NaN values
    df = df.fillna(method='bfill').fillna(0)
    
    return df


def create_labels(df: pd.DataFrame, profit_threshold: float = 0.015, loss_threshold: float = -0.01) -> pd.Series:
    """
    Create labels for training based on future price movement.
    
    Labels:
    - 0: LONG_WIN (price went up >= profit_threshold)
    - 1: LONG_LOSS (price went down <= loss_threshold)
    - 2: SHORT_WIN (price went down >= profit_threshold)
    - 3: SHORT_LOSS (price went up >= loss_threshold)
    
    Args:
        df: DataFrame with OHLCV data
        profit_threshold: Profit threshold (e.g., 0.015 = 1.5%)
        loss_threshold: Loss threshold (e.g., -0.01 = -1%)
    
    Returns:
        pd.Series with labels
    """
    labels = []
    
    for i in range(len(df)):
        if i >= len(df) - 1:
            # No future data, skip
            labels.append(-1)
            continue
        
        current_price = df.iloc[i]['close']
        next_price = df.iloc[i + 1]['close']
        
        price_change = (next_price - current_price) / current_price
        
        # Determine label based on price movement
        if price_change >= profit_threshold:
            # Price went up significantly → LONG_WIN
            labels.append(0)
        elif price_change <= loss_threshold:
            # Price went down significantly → LONG_LOSS (or SHORT_WIN)
            labels.append(2)  # SHORT_WIN
        elif price_change >= -loss_threshold:
            # Price went up a bit → SHORT_LOSS
            labels.append(3)
        else:
            # Price went down a bit → LONG_LOSS
            labels.append(1)
    
    return pd.Series(labels)


async def prepare_training_data(symbol: str, days: int = 365) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Prepare training data for ML models.
    
    Args:
        symbol: Symbol (BTC, ETH)
        days: Number of days of historical data
    
    Returns:
        Tuple of (features_df, labels_series)
    """
    # Download historical data
    df = await download_historical_data(symbol, days=days, interval="4h")
    
    if df.empty:
        logger.error(f"No data downloaded for {symbol}")
        return pd.DataFrame(), pd.Series()
    
    # Calculate indicators
    df = calculate_indicators_for_training(df)
    
    # Create labels
    from ml.config import LABELING_CONFIG
    labels = create_labels(
        df,
        profit_threshold=LABELING_CONFIG['profit_threshold'],
        loss_threshold=LABELING_CONFIG['loss_threshold']
    )
    
    # Extract features
    indicators = {
        'rsi': df['rsi'].values,
        'macd': df['macd'].values,
        'macd_signal': df['macd_signal'].values,
        'macd_diff': df['macd_diff'].values,
        'bb_upper': df['bb_upper'].values,
        'bb_middle': df['bb_middle'].values,
        'bb_lower': df['bb_lower'].values,
        'ma_50': df['ma_50'].values,
        'ma_200': df['ma_200'].values,
        'atr': df['atr'].values,
    }
    
    candles = df[['open', 'high', 'low', 'close', 'volume']].to_dict('records')
    
    # Use features module to extract features
    from ml.features import extract_features
    features_df = extract_features(candles, indicators=indicators)
    
    # Remove samples with invalid labels
    valid_mask = labels != -1
    features_df = features_df[valid_mask].reset_index(drop=True)
    labels = labels[valid_mask].reset_index(drop=True)
    
    logger.info(f"Prepared {len(features_df)} training samples for {symbol}")
    logger.info(f"Label distribution: {labels.value_counts().to_dict()}")
    
    return features_df, labels
