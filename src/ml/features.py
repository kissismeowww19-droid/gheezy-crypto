"""
Feature extraction for ML models.

Extracts features from candles, indicators, and enhancer scores.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def extract_features(
    candles: List[dict],
    indicators: Optional[Dict] = None,
    enhancer_scores: Optional[Dict] = None,
    market_data: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Extract features from candles and indicators for ML models.

    Args:
        candles: List of OHLCV candles
        indicators: Dict with technical indicators (RSI, MACD, BB, etc.)
        enhancer_scores: Dict with enhancer scores
        market_data: Dict with market data (funding_rate, open_interest, etc.)

    Returns:
        pd.DataFrame with extracted features
    """
    if not candles or len(candles) == 0:
        logger.warning("No candles provided for feature extraction")
        return pd.DataFrame()

    # Convert candles to DataFrame
    df = pd.DataFrame(candles)

    # Ensure we have required columns
    required_cols = ["open", "high", "low", "close", "volume"]
    if not all(col in df.columns for col in required_cols):
        logger.error(f"Missing required columns. Available: {df.columns.tolist()}")
        return pd.DataFrame()

    features = pd.DataFrame()

    # Basic price features
    features["open"] = df["open"]
    features["high"] = df["high"]
    features["low"] = df["low"]
    features["close"] = df["close"]
    features["volume"] = df["volume"]

    # Price changes
    features["price_change_1"] = df["close"].pct_change(1).fillna(0)
    features["price_change_4"] = df["close"].pct_change(4).fillna(0)
    features["price_change_24"] = df["close"].pct_change(24).fillna(0)

    # Volume changes
    features["volume_change_1"] = df["volume"].pct_change(1).fillna(0)
    features["volume_change_4"] = df["volume"].pct_change(4).fillna(0)

    # Price range features
    features["high_low_range"] = (df["high"] - df["low"]) / df["close"]
    features["close_open_range"] = (df["close"] - df["open"]) / df["open"]

    # Technical indicators
    if indicators:
        # RSI
        if "rsi" in indicators:
            features["rsi"] = indicators["rsi"]
        else:
            features["rsi"] = 50.0  # neutral

        # MACD
        if "macd" in indicators:
            features["macd"] = indicators["macd"]
            features["macd_signal"] = indicators.get("macd_signal", 0)
            features["macd_diff"] = indicators.get("macd_diff", 0)
        else:
            features["macd"] = 0
            features["macd_signal"] = 0
            features["macd_diff"] = 0

        # Bollinger Bands
        if "bb_upper" in indicators:
            features["bb_upper"] = indicators["bb_upper"]
            features["bb_middle"] = indicators["bb_middle"]
            features["bb_lower"] = indicators["bb_lower"]
            # BB position (where price is within bands)
            bb_range = indicators["bb_upper"] - indicators["bb_lower"]
            # Handle array - avoid division by zero
            bb_range_safe = np.where(bb_range == 0, 1, bb_range)
            features["bb_position"] = (
                df["close"] - indicators["bb_lower"]
            ) / bb_range_safe
            # Set position to 0.5 where range was 0
            features["bb_position"] = np.where(
                bb_range == 0, 0.5, features["bb_position"]
            )
        else:
            features["bb_upper"] = df["close"] * 1.02
            features["bb_middle"] = df["close"]
            features["bb_lower"] = df["close"] * 0.98
            features["bb_position"] = 0.5

        # Moving averages
        if "ma_50" in indicators:
            features["ma_50"] = indicators["ma_50"]
        else:
            features["ma_50"] = df["close"].rolling(50, min_periods=1).mean()

        if "ma_200" in indicators:
            features["ma_200"] = indicators["ma_200"]
        else:
            features["ma_200"] = df["close"].rolling(200, min_periods=1).mean()

        # MA crossover
        features["ma_crossover"] = (features["ma_50"] - features["ma_200"]) / features[
            "ma_200"
        ]

        # Additional indicators
        features["stoch_rsi"] = indicators.get("stoch_rsi", 50.0)
        features["mfi"] = indicators.get("mfi", 50.0)
        features["roc"] = indicators.get("roc", 0.0)
        features["williams_r"] = indicators.get("williams_r", -50.0)
        features["atr"] = indicators.get("atr", 0.0)
        features["adx"] = indicators.get("adx", 0.0)
        features["obv"] = indicators.get("obv", 0.0)
        features["vwap"] = indicators.get("vwap", df["close"])
    else:
        # Set default values for indicators
        features["rsi"] = 50.0
        features["macd"] = 0.0
        features["macd_signal"] = 0.0
        features["macd_diff"] = 0.0
        features["bb_upper"] = df["close"] * 1.02
        features["bb_middle"] = df["close"]
        features["bb_lower"] = df["close"] * 0.98
        features["bb_position"] = 0.5
        features["ma_50"] = df["close"]
        features["ma_200"] = df["close"]
        features["ma_crossover"] = 0.0
        features["stoch_rsi"] = 50.0
        features["mfi"] = 50.0
        features["roc"] = 0.0
        features["williams_r"] = -50.0
        features["atr"] = 0.0
        features["adx"] = 0.0
        features["obv"] = 0.0
        features["vwap"] = df["close"]

    # Market data features
    if market_data:
        features["funding_rate"] = market_data.get("funding_rate", 0.0)
        features["open_interest"] = market_data.get("open_interest", 0.0)
        features["fear_greed_index"] = market_data.get("fear_greed_index", 50.0)
    else:
        features["funding_rate"] = 0.0
        features["open_interest"] = 0.0
        features["fear_greed_index"] = 50.0

    # Enhancer scores
    if enhancer_scores:
        features["order_flow"] = enhancer_scores.get("order_flow", 0.0)
        features["volume_profile"] = enhancer_scores.get("volume_profile", 0.0)
        features["multi_exchange"] = enhancer_scores.get("multi_exchange", 0.0)
        features["liquidations"] = enhancer_scores.get("liquidations", 0.0)
        features["smart_money"] = enhancer_scores.get("smart_money", 0.0)
        features["wyckoff"] = enhancer_scores.get("wyckoff", 0.0)
        features["on_chain"] = enhancer_scores.get("on_chain", 0.0)
        features["whale_tracker"] = enhancer_scores.get("whale_tracker", 0.0)
        features["funding_advanced"] = enhancer_scores.get("funding_advanced", 0.0)
        features["volatility_score"] = enhancer_scores.get("volatility", 0.0)
    else:
        # Set default enhancer scores
        features["order_flow"] = 0.0
        features["volume_profile"] = 0.0
        features["multi_exchange"] = 0.0
        features["liquidations"] = 0.0
        features["smart_money"] = 0.0
        features["wyckoff"] = 0.0
        features["on_chain"] = 0.0
        features["whale_tracker"] = 0.0
        features["funding_advanced"] = 0.0
        features["volatility_score"] = 0.0

    # Fill any remaining NaN values
    features = features.fillna(0)

    # Replace inf values with large finite values
    features = features.replace([np.inf, -np.inf], [1e10, -1e10])

    logger.info(
        f"Extracted {len(features.columns)} features from {len(features)} samples"
    )

    return features


def extract_features_from_signal_data(
    signal_data: Dict, technical_data: Dict, market_data: Dict
) -> Dict:
    """
    Extract features from signal data for real-time prediction.

    Args:
        signal_data: Signal data with scores and indicators
        technical_data: Technical indicators
        market_data: Market data (price, volume, etc.)

    Returns:
        Dict with features ready for prediction
    """
    features = {}

    # Basic price data
    current_price = market_data.get("price_usd", 0)
    features["close"] = current_price
    features["volume"] = market_data.get("volume_24h", 0)

    # Price changes (from signal_data if available) - handle None values
    price_change_1h = signal_data.get("price_change_1h", 0)
    features["price_change_1"] = (price_change_1h / 100) if price_change_1h is not None else 0.0
    
    price_change_4h = signal_data.get("price_change_4h", 0)
    features["price_change_4"] = (price_change_4h / 100) if price_change_4h is not None else 0.0
    
    price_change_24h = signal_data.get("price_change_24h", 0)
    features["price_change_24"] = (price_change_24h / 100) if price_change_24h is not None else 0.0

    # Technical indicators - handle nested dictionaries from calculate_technical_indicators
    if technical_data:
        # RSI - can be nested dict with 'value' key or direct value
        rsi_data = technical_data.get("rsi", 50.0)
        if isinstance(rsi_data, dict):
            features["rsi"] = rsi_data.get("value", 50.0)
        else:
            features["rsi"] = rsi_data
        
        # MACD - can be nested dict or direct values
        macd_data = technical_data.get("macd", 0.0)
        if isinstance(macd_data, dict):
            features["macd"] = macd_data.get("macd_line", 0.0)
            features["macd_signal"] = macd_data.get("signal_line", 0.0)
            features["macd_diff"] = macd_data.get("histogram", 0.0)
        else:
            features["macd"] = macd_data
            features["macd_signal"] = technical_data.get("macd_signal", 0.0)
            features["macd_diff"] = technical_data.get("macd_diff", 0.0)

        bb_data = technical_data.get("bollinger_bands", {})
        features["bb_upper"] = bb_data.get("upper", current_price * 1.02)
        features["bb_middle"] = bb_data.get("middle", current_price)
        features["bb_lower"] = bb_data.get("lower", current_price * 0.98)

        bb_range = features["bb_upper"] - features["bb_lower"]
        # Safe division - handle zero range
        if isinstance(bb_range, (np.ndarray, pd.Series)):
            # Handle array case
            bb_range_safe = np.where(bb_range == 0, 1, bb_range)
            features["bb_position"] = (
                current_price - features["bb_lower"]
            ) / bb_range_safe
            features["bb_position"] = np.where(
                bb_range == 0, 0.5, features["bb_position"]
            )
        else:
            # Handle scalar case
            features["bb_position"] = (
                (current_price - features["bb_lower"]) / bb_range
                if bb_range != 0
                else 0.5
            )

        # Moving averages
        ma_cross_data = technical_data.get("ma_crossover", {})
        if isinstance(ma_cross_data, dict):
            features["ma_50"] = ma_cross_data.get("ma_short", current_price)
            features["ma_200"] = ma_cross_data.get("ma_long", current_price)
        else:
            features["ma_50"] = technical_data.get("ma_50", current_price)
            features["ma_200"] = technical_data.get("ma_200", current_price)
        
        features["ma_crossover"] = (features["ma_50"] - features["ma_200"]) / features[
            "ma_200"
        ] if features["ma_200"] != 0 else 0.0

        # Additional indicators - handle nested dicts
        stoch_rsi_data = technical_data.get("stoch_rsi", 50.0)
        features["stoch_rsi"] = stoch_rsi_data.get("k", 50.0) if isinstance(stoch_rsi_data, dict) else stoch_rsi_data
        
        mfi_data = technical_data.get("mfi", 50.0)
        features["mfi"] = mfi_data.get("value", 50.0) if isinstance(mfi_data, dict) else mfi_data
        
        roc_data = technical_data.get("roc", 0.0)
        features["roc"] = roc_data.get("value", 0.0) if isinstance(roc_data, dict) else roc_data
        
        williams_data = technical_data.get("williams_r", -50.0)
        features["williams_r"] = williams_data.get("value", -50.0) if isinstance(williams_data, dict) else williams_data
        
        atr_data = technical_data.get("atr", 0.0)
        features["atr"] = atr_data.get("value", 0.0) if isinstance(atr_data, dict) else atr_data
        
        adx_data = technical_data.get("adx", 0.0)
        features["adx"] = adx_data.get("value", 0.0) if isinstance(adx_data, dict) else adx_data
        
        obv_data = technical_data.get("obv", 0.0)
        features["obv"] = obv_data.get("value", 0.0) if isinstance(obv_data, dict) else obv_data
        
        vwap_data = technical_data.get("vwap", current_price)
        features["vwap"] = vwap_data.get("value", current_price) if isinstance(vwap_data, dict) else vwap_data

    # Market data
    features["funding_rate"] = signal_data.get("funding_rate", 0.0)
    features["open_interest"] = market_data.get("open_interest", 0.0)
    features["fear_greed_index"] = signal_data.get("fear_greed", 50.0)

    # Enhancer scores (from signal_data)
    enhancer_data = signal_data.get("enhancer_data", {})
    features["order_flow"] = enhancer_data.get("order_flow", 0.0)
    features["volume_profile"] = enhancer_data.get("volume_profile", 0.0)
    features["multi_exchange"] = enhancer_data.get("multi_exchange", 0.0)
    features["liquidations"] = enhancer_data.get("liquidations", 0.0)
    features["smart_money"] = enhancer_data.get("smart_money", 0.0)
    features["wyckoff"] = enhancer_data.get("wyckoff", 0.0)
    features["on_chain"] = enhancer_data.get("on_chain", 0.0)
    features["whale_tracker"] = enhancer_data.get("whale_tracker", 0.0)
    features["funding_advanced"] = enhancer_data.get("funding_advanced", 0.0)
    features["volatility_score"] = enhancer_data.get("volatility", 0.0)

    # Convert all values to float to avoid dtype errors in ML models
    for key, value in features.items():
        try:
            if isinstance(value, (list, np.ndarray)):
                # Take last value if array
                features[key] = float(value[-1]) if len(value) > 0 else 0.0
            elif isinstance(value, str):
                # Try to parse string as float, handle special cases
                value_lower = value.lower()
                if value_lower == 'bullish':
                    features[key] = 1.0
                elif value_lower == 'bearish':
                    features[key] = -1.0
                else:
                    # Try to parse as number
                    features[key] = float(value) if value else 0.0
            elif value is None:
                features[key] = 0.0
            else:
                features[key] = float(value)
        except (ValueError, TypeError, IndexError):
            features[key] = 0.0

    return features
