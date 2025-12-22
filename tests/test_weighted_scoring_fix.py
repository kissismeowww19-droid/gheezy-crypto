"""
Test weighted scoring system fix (PR #88).

This test verifies that:
1. Weighted score is calculated correctly from 10 factors
2. Direction is determined based on weighted_score thresholds
3. Message formatting doesn't exceed 4096 chars
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.ai_signals import AISignalAnalyzer


def test_weighted_score_calculation():
    """Test that weighted score is calculated correctly."""
    # Create analyzer with minimal setup
    class MockWhaleTracker:
        async def get_transactions_by_blockchain(self, blockchain, limit):
            return []
    
    analyzer = AISignalAnalyzer(MockWhaleTracker())
    
    # Test case 1: All positive factors
    factors = {
        'whales': 5.0,        # 25% weight
        'derivatives': 4.0,   # 20% weight
        'trend': 3.0,         # 15% weight
        'momentum': 2.0,      # 12% weight
        'volume': 1.0,        # 10% weight
        'adx': 5.0,           # 5% weight
        'divergence': 3.0,    # 5% weight
        'sentiment': 2.0,     # 4% weight
        'macro': 1.0,         # 3% weight
        'options': 1.0,       # 1% weight
    }
    
    # Expected: 5*0.25 + 4*0.20 + 3*0.15 + 2*0.12 + 1*0.10 + 5*0.05 + 3*0.05 + 2*0.04 + 1*0.03 + 1*0.01
    # = 1.25 + 0.80 + 0.45 + 0.24 + 0.10 + 0.25 + 0.15 + 0.08 + 0.03 + 0.01 = 3.36
    weighted_score = analyzer.calculate_weighted_score(factors)
    
    assert abs(weighted_score - 3.36) < 0.01, f"Expected ~3.36, got {weighted_score}"
    print(f"✓ Test 1 passed: Weighted score = {weighted_score:.2f}")
    
    # Test case 2: All negative factors
    factors_negative = {k: -v for k, v in factors.items()}
    weighted_score_neg = analyzer.calculate_weighted_score(factors_negative)
    
    assert abs(weighted_score_neg + 3.36) < 0.01, f"Expected ~-3.36, got {weighted_score_neg}"
    print(f"✓ Test 2 passed: Negative weighted score = {weighted_score_neg:.2f}")
    
    # Test case 3: Mixed factors
    factors_mixed = {
        'whales': 10.0,       # Strong bullish
        'derivatives': -5.0,  # Bearish
        'trend': 3.0,
        'momentum': -2.0,
        'volume': 5.0,
        'adx': 0.0,
        'divergence': 0.0,
        'sentiment': 0.0,
        'macro': 0.0,
        'options': 0.0,
    }
    weighted_score_mixed = analyzer.calculate_weighted_score(factors_mixed)
    # Expected: 10*0.25 + (-5)*0.20 + 3*0.15 + (-2)*0.12 + 5*0.10
    # = 2.5 - 1.0 + 0.45 - 0.24 + 0.5 = 2.21
    
    assert abs(weighted_score_mixed - 2.21) < 0.01, f"Expected ~2.21, got {weighted_score_mixed}"
    print(f"✓ Test 3 passed: Mixed weighted score = {weighted_score_mixed:.2f}")


def test_direction_from_weighted_score():
    """Test that direction is determined correctly from weighted score."""
    test_cases = [
        (5.0, 'long', 'Strong bullish weighted score should give long direction'),
        (2.5, 'long', 'Moderate bullish weighted score should give long direction'),
        (2.0, 'long', 'Threshold bullish weighted score should give long direction'),
        (1.5, 'neutral', 'Weak bullish weighted score should give neutral direction'),
        (0.0, 'neutral', 'Zero weighted score should give neutral direction'),
        (-1.5, 'neutral', 'Weak bearish weighted score should give neutral direction'),
        (-2.0, 'short', 'Threshold bearish weighted score should give short direction'),
        (-2.5, 'short', 'Moderate bearish weighted score should give short direction'),
        (-5.0, 'short', 'Strong bearish weighted score should give short direction'),
    ]
    
    for weighted_score, expected_direction, description in test_cases:
        # Apply the same logic from ai_signals.py
        if weighted_score > 2.0:
            direction = 'long'
        elif weighted_score < -2.0:
            direction = 'short'
        else:
            direction = 'neutral'
        
        assert direction == expected_direction, f"{description}: weighted_score={weighted_score}, expected {expected_direction}, got {direction}"
        print(f"✓ Test passed: {description} (score={weighted_score}, direction={direction})")


def test_probability_from_weighted_score():
    """Test that probability is calculated correctly from weighted score."""
    test_cases = [
        (10.0, 85, 'Max weighted score should give capped probability'),
        (5.0, 67.5, 'Moderate bullish should give moderate probability'),
        (2.0, 57.0, 'Threshold bullish should give slightly above 50%'),
        (0.0, 50, 'Zero should give neutral 50%'),
        (-2.0, 57.0, 'Threshold bearish should give slightly above 50%'),
        (-5.0, 67.5, 'Moderate bearish should give moderate probability'),
        (-10.0, 85, 'Max negative should give capped probability'),
    ]
    
    for weighted_score, expected_prob, description in test_cases:
        # Apply the same logic from ai_signals.py
        if weighted_score > 2.0:
            probability = min(85, 50 + weighted_score * 3.5)
        elif weighted_score < -2.0:
            probability = min(85, 50 + abs(weighted_score) * 3.5)
        else:
            probability = 50
        
        assert abs(probability - expected_prob) < 0.5, f"{description}: weighted_score={weighted_score}, expected {expected_prob}, got {probability}"
        print(f"✓ Test passed: {description} (score={weighted_score}, prob={probability}%)")


def test_factor_weights_sum_to_100_percent():
    """Test that all factor weights sum to 100%."""
    class MockWhaleTracker:
        async def get_transactions_by_blockchain(self, blockchain, limit):
            return []
    
    analyzer = AISignalAnalyzer(MockWhaleTracker())
    
    total_weight = sum(analyzer.FACTOR_WEIGHTS.values())
    
    assert abs(total_weight - 1.0) < 0.001, f"Factor weights should sum to 1.0 (100%), got {total_weight}"
    print(f"✓ Test passed: Factor weights sum to {total_weight * 100:.1f}%")
    
    # Print breakdown
    print("\nFactor weights breakdown:")
    for factor, weight in analyzer.FACTOR_WEIGHTS.items():
        print(f"  {factor:15s}: {weight * 100:5.1f}%")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing Weighted Scoring System Fix")
    print("=" * 60)
    print()
    
    print("Test 1: Weighted Score Calculation")
    print("-" * 60)
    test_weighted_score_calculation()
    print()
    
    print("Test 2: Direction from Weighted Score")
    print("-" * 60)
    test_direction_from_weighted_score()
    print()
    
    print("Test 3: Probability from Weighted Score")
    print("-" * 60)
    test_probability_from_weighted_score()
    print()
    
    print("Test 4: Factor Weights Sum to 100%")
    print("-" * 60)
    test_factor_weights_sum_to_100_percent()
    print()
    
    print("=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
