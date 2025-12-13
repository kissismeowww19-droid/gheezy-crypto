"""
Price Forecast Module for 4-Hour Predictions.

Calculates ATR-based targets, pivot points, and generates scenarios.
"""

import logging
from typing import Optional, Dict, List
from signals.indicators import calculate_atr, calculate_pivot_points

logger = logging.getLogger(__name__)


class PriceForecastAnalyzer:
    """Analyzer for 4-hour price forecasts."""
    
    # ATR multipliers for targets
    ATR_TARGET_MULTIPLIER = 1.5
    ATR_STOP_MULTIPLIER = 1.0
    
    def __init__(self):
        """Initialize price forecast analyzer."""
        pass
    
    def calculate_atr_targets(
        self,
        high: List[float],
        low: List[float],
        close: List[float],
        current_price: float,
        direction: str
    ) -> Optional[Dict]:
        """
        Calculate ATR-based targets and stop loss for 4-hour forecast.
        
        Args:
            high: List of high prices
            low: List of low prices
            close: List of close prices
            current_price: Current market price
            direction: Trading direction ("long", "short", "sideways")
            
        Returns:
            Dict with target1, target2, stop, and risk_reward ratio
        """
        if len(high) < 14 or len(low) < 14 or len(close) < 14:
            logger.warning("Insufficient data for ATR calculation")
            return None
        
        try:
            # Calculate ATR (14-period)
            atr = calculate_atr(high, low, close, period=14)
            
            if not atr or atr.value <= 0:
                logger.warning("Invalid ATR value")
                return None
            
            atr_value = atr.value
            
            # Calculate targets based on direction
            if direction == "long":
                target1 = current_price + (atr_value * self.ATR_TARGET_MULTIPLIER)
                target2 = current_price + (atr_value * self.ATR_TARGET_MULTIPLIER * 1.5)
                stop = current_price - (atr_value * self.ATR_STOP_MULTIPLIER)
                
                target1_percent = ((target1 - current_price) / current_price) * 100
                target2_percent = ((target2 - current_price) / current_price) * 100
                stop_percent = ((stop - current_price) / current_price) * 100
                
            elif direction == "short":
                target1 = current_price - (atr_value * self.ATR_TARGET_MULTIPLIER)
                target2 = current_price - (atr_value * self.ATR_TARGET_MULTIPLIER * 1.5)
                stop = current_price + (atr_value * self.ATR_STOP_MULTIPLIER)
                
                target1_percent = ((target1 - current_price) / current_price) * 100
                target2_percent = ((target2 - current_price) / current_price) * 100
                stop_percent = ((stop - current_price) / current_price) * 100
                
            else:  # sideways
                # For sideways, use ATR for range estimation
                target1 = current_price + (atr_value * 0.5)
                target2 = current_price - (atr_value * 0.5)
                stop = None
                
                target1_percent = ((target1 - current_price) / current_price) * 100
                target2_percent = ((target2 - current_price) / current_price) * 100
                stop_percent = 0
            
            # Calculate risk-reward ratio
            if direction != "sideways" and stop:
                risk = abs(current_price - stop)
                reward = abs(target1 - current_price)
                risk_reward = reward / risk if risk > 0 else 0
            else:
                risk_reward = 0
            
            return {
                "current_price": current_price,
                "target1": target1,
                "target2": target2,
                "stop": stop,
                "target1_percent": target1_percent,
                "target2_percent": target2_percent,
                "stop_percent": stop_percent,
                "risk_reward": risk_reward,
                "atr": atr_value
            }
        
        except Exception as e:
            logger.error(f"Error calculating ATR targets: {e}")
            return None
    
    def calculate_pivot_levels(
        self,
        high: float,
        low: float,
        close: float
    ) -> Optional[Dict]:
        """
        Calculate Pivot Points and support/resistance levels.
        
        Args:
            high: Last period high
            low: Last period low
            close: Last period close
            
        Returns:
            Dict with pivot, R1, R2, S1, S2 levels
        """
        try:
            pivot = (high + low + close) / 3
            r1 = (2 * pivot) - low
            r2 = pivot + (high - low)
            s1 = (2 * pivot) - high
            s2 = pivot - (high - low)
            
            return {
                "pivot": pivot,
                "r1": r1,
                "r2": r2,
                "s1": s1,
                "s2": s2
            }
        
        except Exception as e:
            logger.error(f"Error calculating pivot levels: {e}")
            return None
    
    def generate_scenarios(
        self,
        current_price: float,
        direction: str,
        signal_strength: float,
        targets: Dict,
        pivot_levels: Dict,
        multi_timeframe_data: Optional[Dict] = None
    ) -> Dict:
        """
        Generate bullish, bearish, and sideways scenarios with probabilities.
        
        Args:
            current_price: Current market price
            direction: Primary signal direction
            signal_strength: Signal strength (0-100)
            targets: ATR-based targets
            pivot_levels: Pivot point levels
            multi_timeframe_data: Multi-timeframe analysis data
            
        Returns:
            Dict with three scenarios
        """
        try:
            # Base probabilities depend on signal direction and strength
            if direction == "long":
                base_bull = 50 + (signal_strength * 0.3)  # 50-80%
                base_bear = 20 - (signal_strength * 0.1)  # 10-20%
                base_side = 100 - base_bull - base_bear
            elif direction == "short":
                base_bear = 50 + (signal_strength * 0.3)  # 50-80%
                base_bull = 20 - (signal_strength * 0.1)  # 10-20%
                base_side = 100 - base_bull - base_bear
            else:  # sideways
                base_side = 60
                base_bull = 20
                base_bear = 20
            
            # Adjust based on multi-timeframe consensus
            if multi_timeframe_data:
                consensus = multi_timeframe_data.get("consensus", {})
                consensus_direction = consensus.get("direction", "neutral")
                consensus_strength = consensus.get("strength", 0.5)
                
                if consensus_direction == "bullish":
                    adjustment = consensus_strength * 10
                    base_bull += adjustment
                    base_bear -= adjustment / 2
                    base_side -= adjustment / 2
                elif consensus_direction == "bearish":
                    adjustment = consensus_strength * 10
                    base_bear += adjustment
                    base_bull -= adjustment / 2
                    base_side -= adjustment / 2
            
            # Ensure probabilities sum to 100 and are within bounds
            total = base_bull + base_bear + base_side
            bull_prob = max(5, min(85, (base_bull / total) * 100))
            bear_prob = max(5, min(85, (base_bear / total) * 100))
            side_prob = max(10, min(90, 100 - bull_prob - bear_prob))
            
            # Generate scenario targets
            scenarios = {
                "bullish": {
                    "probability": int(bull_prob),
                    "target": targets.get("target1", current_price * 1.02),
                    "trigger": f"Прорыв выше ${pivot_levels.get('r1', current_price * 1.01):.2f}"
                },
                "bearish": {
                    "probability": int(bear_prob),
                    "target": targets.get("target2" if direction == "short" else "stop", current_price * 0.98),
                    "trigger": f"Пробой ниже ${pivot_levels.get('s1', current_price * 0.99):.2f}"
                },
                "sideways": {
                    "probability": int(side_prob),
                    "range_high": pivot_levels.get("r1", current_price * 1.01),
                    "range_low": pivot_levels.get("s1", current_price * 0.99),
                    "range_text": f"${pivot_levels.get('s1', current_price * 0.99):.2f} - ${pivot_levels.get('r1', current_price * 1.01):.2f}"
                }
            }
            
            return scenarios
        
        except Exception as e:
            logger.error(f"Error generating scenarios: {e}")
            # Return default scenarios
            return {
                "bullish": {
                    "probability": 33,
                    "target": current_price * 1.02,
                    "trigger": "Прорыв сопротивления"
                },
                "bearish": {
                    "probability": 33,
                    "target": current_price * 0.98,
                    "trigger": "Пробой поддержки"
                },
                "sideways": {
                    "probability": 34,
                    "range_high": current_price * 1.01,
                    "range_low": current_price * 0.99,
                    "range_text": f"${current_price * 0.99:.2f} - ${current_price * 1.01:.2f}"
                }
            }
    
    def analyze_4h_forecast(
        self,
        candles_4h: List[Dict],
        current_price: float,
        direction: str,
        signal_strength: float,
        multi_timeframe_data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Complete 4-hour forecast analysis.
        
        Args:
            candles_4h: 4-hour candles
            current_price: Current market price
            direction: Signal direction
            signal_strength: Signal strength (0-100)
            multi_timeframe_data: Multi-timeframe analysis data
            
        Returns:
            Complete forecast analysis
        """
        if not candles_4h or len(candles_4h) < 14:
            logger.warning("Insufficient 4h candle data for forecast")
            return None
        
        try:
            # Extract price arrays
            highs = [c["high"] for c in candles_4h]
            lows = [c["low"] for c in candles_4h]
            closes = [c["close"] for c in candles_4h]
            
            # Calculate ATR targets
            targets = self.calculate_atr_targets(
                highs, lows, closes, current_price, direction
            )
            
            if not targets:
                return None
            
            # Calculate pivot levels (use last complete candle)
            pivot_levels = self.calculate_pivot_levels(
                highs[-1], lows[-1], closes[-1]
            )
            
            if not pivot_levels:
                return None
            
            # Generate scenarios
            scenarios = self.generate_scenarios(
                current_price,
                direction,
                signal_strength,
                targets,
                pivot_levels,
                multi_timeframe_data
            )
            
            return {
                "targets": targets,
                "pivot_levels": pivot_levels,
                "scenarios": scenarios,
                "forecast_period": "4 часа"
            }
        
        except Exception as e:
            logger.error(f"Error in 4h forecast analysis: {e}")
            return None
