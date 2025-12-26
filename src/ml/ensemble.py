"""
Ensemble system - combines rules-based scores with ML predictions.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def combine_scores(rules_score: float, ml_prediction: Dict) -> Dict:
    """
    Combine rules-based score (70%) with ML prediction (30%).
    
    Args:
        rules_score: Rules-based confidence score (0-100)
        ml_prediction: Dict with ML prediction results
    
    Returns:
        Dict with final score and confidence:
        {
            "final_confidence": 72.5,
            "rules_contribution": 49.0,
            "ml_contribution": 23.5,
            "recommendation": "normal",
            "should_cancel": False
        }
    """
    from ml.config import ML_CONFIG
    
    # Get ensemble weights
    weights = ML_CONFIG['ensemble_weights']
    rules_weight = weights['rules']
    ml_weight = weights['ml']
    
    # Normalize rules score to 0-100 range if needed
    if rules_score < 0:
        rules_score_normalized = 0
    elif rules_score > 100:
        rules_score_normalized = 100
    else:
        rules_score_normalized = rules_score
    
    # Get ML confidence (0-1 range)
    ml_confidence = ml_prediction.get('ml_confidence', 0.5)
    ml_confidence_pct = ml_confidence * 100  # Convert to 0-100
    
    # Calculate weighted contributions
    rules_contribution = rules_score_normalized * rules_weight
    ml_contribution = ml_confidence_pct * ml_weight
    
    # Final combined score
    final_confidence = rules_contribution + ml_contribution
    
    # Determine final recommendation
    thresholds = ML_CONFIG['thresholds']
    ml_recommendation = ml_prediction.get('recommendation', 'normal')
    ml_should_cancel = ml_prediction.get('should_cancel', False)
    
    # If ML recommends cancellation, respect it
    if ml_should_cancel:
        recommendation = "wait"
        should_cancel = True
    else:
        # Use final confidence to determine recommendation
        final_conf_normalized = final_confidence / 100  # Back to 0-1 range
        
        if final_conf_normalized < thresholds['cancel']:
            recommendation = "wait"
            should_cancel = True
        elif final_conf_normalized < thresholds['low_confidence']:
            recommendation = "low_confidence"
            should_cancel = False
        elif final_conf_normalized < thresholds['normal']:
            recommendation = "normal"
            should_cancel = False
        else:
            recommendation = "strong"
            should_cancel = False
    
    result = {
        "final_confidence": float(final_confidence),
        "rules_contribution": float(rules_contribution),
        "ml_contribution": float(ml_contribution),
        "recommendation": recommendation,
        "should_cancel": should_cancel,
        "ml_confidence": float(ml_confidence_pct),
        "rules_confidence": float(rules_score_normalized)
    }
    
    logger.info(f"Combined score: {result}")
    
    return result
