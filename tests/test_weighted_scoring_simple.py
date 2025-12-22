"""
Simple test for weighted scoring logic without importing full modules.
Tests the core calculation logic that was implemented.
"""


def calculate_weighted_score(factors):
    """
    Calculate weighted score from factor scores (copied from ai_signals.py).
    """
    FACTOR_WEIGHTS = {
        'whales': 0.25,
        'derivatives': 0.20,
        'trend': 0.15,
        'momentum': 0.12,
        'volume': 0.10,
        'adx': 0.05,
        'divergence': 0.05,
        'sentiment': 0.04,
        'macro': 0.03,
        'options': 0.01,
    }
    
    total = 0.0
    for factor, score in factors.items():
        weight = FACTOR_WEIGHTS.get(factor, 0)
        clamped_score = max(-10, min(10, score))
        total += clamped_score * weight
    
    return total


def test_weighted_score_calculation():
    """Test that weighted score is calculated correctly."""
    
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
    weighted_score = calculate_weighted_score(factors)
    
    assert abs(weighted_score - 3.36) < 0.01, f"Expected ~3.36, got {weighted_score}"
    print(f"✓ Test 1 passed: Weighted score = {weighted_score:.2f}")
    
    # Test case 2: All negative factors
    factors_negative = {k: -v for k, v in factors.items()}
    weighted_score_neg = calculate_weighted_score(factors_negative)
    
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
    weighted_score_mixed = calculate_weighted_score(factors_mixed)
    # Expected: 10*0.25 + (-5)*0.20 + 3*0.15 + (-2)*0.12 + 5*0.10
    # = 2.5 - 1.0 + 0.45 - 0.24 + 0.5 = 2.21
    
    assert abs(weighted_score_mixed - 2.21) < 0.01, f"Expected ~2.21, got {weighted_score_mixed}"
    print(f"✓ Test 3 passed: Mixed weighted score = {weighted_score_mixed:.2f}")
    
    # Test case 4: Extreme values (clamping test)
    factors_extreme = {
        'whales': 50.0,       # Should be clamped to 10
        'derivatives': -50.0, # Should be clamped to -10
        'trend': 0.0,
        'momentum': 0.0,
        'volume': 0.0,
        'adx': 0.0,
        'divergence': 0.0,
        'sentiment': 0.0,
        'macro': 0.0,
        'options': 0.0,
    }
    weighted_score_extreme = calculate_weighted_score(factors_extreme)
    # Expected: 10*0.25 + (-10)*0.20 = 2.5 - 2.0 = 0.5
    
    assert abs(weighted_score_extreme - 0.5) < 0.01, f"Expected ~0.5 (after clamping), got {weighted_score_extreme}"
    print(f"✓ Test 4 passed: Extreme values clamped correctly = {weighted_score_extreme:.2f}")


def test_direction_from_weighted_score():
    """Test that direction is determined correctly from weighted score."""
    test_cases = [
        (5.0, 'long', 'Strong bullish weighted score should give long direction'),
        (2.5, 'long', 'Moderate bullish weighted score should give long direction'),
        (2.1, 'long', 'Just above threshold should give long direction'),
        (2.0, 'neutral', 'Threshold value 2.0 should give neutral (boundary case)'),
        (1.5, 'neutral', 'Weak bullish weighted score should give neutral direction'),
        (0.0, 'neutral', 'Zero weighted score should give neutral direction'),
        (-1.5, 'neutral', 'Weak bearish weighted score should give neutral direction'),
        (-2.0, 'neutral', 'Threshold value -2.0 should give neutral (boundary case)'),
        (-2.1, 'short', 'Just below threshold should give short direction'),
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
        (2.5, 58.75, 'Mild bullish should give ~59%'),
        (2.1, 57.35, 'Just above threshold should give ~57%'),
        (2.0, 50, 'Threshold 2.0 should give neutral 50%'),
        (0.0, 50, 'Zero should give neutral 50%'),
        (-2.0, 50, 'Threshold -2.0 should give neutral 50%'),
        (-2.1, 57.35, 'Just below threshold should give ~57%'),
        (-2.5, 58.75, 'Mild bearish should give ~59%'),
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
    FACTOR_WEIGHTS = {
        'whales': 0.25,
        'derivatives': 0.20,
        'trend': 0.15,
        'momentum': 0.12,
        'volume': 0.10,
        'adx': 0.05,
        'divergence': 0.05,
        'sentiment': 0.04,
        'macro': 0.03,
        'options': 0.01,
    }
    
    total_weight = sum(FACTOR_WEIGHTS.values())
    
    assert abs(total_weight - 1.0) < 0.001, f"Factor weights should sum to 1.0 (100%), got {total_weight}"
    print(f"✓ Test passed: Factor weights sum to {total_weight * 100:.1f}%")
    
    # Print breakdown
    print("\nFactor weights breakdown:")
    for factor, weight in FACTOR_WEIGHTS.items():
        print(f"  {factor:15s}: {weight * 100:5.1f}%")


def test_message_length_estimation():
    """Test that message splitting logic works for long messages."""
    # Simulate a realistic long signal message (similar to actual format)
    # A typical full signal is around 5000-6000 chars
    long_message = """🤖 AI СИГНАЛ: BTC (4ч прогноз)
━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 ЦЕНА СЕЙЧАС: $95,000

🔮 ПРОГНОЗ НА 4 ЧАСА:
• Направление: UP
• Цель: $96,500 (+1.6%)
• Диапазон: $94,000 — $96,000
• Уверенность: 65%

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ВЗВЕШЕННЫЙ АНАЛИЗ (1/2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━

🐋 КИТЫ (25% веса)
• Score: 5/10
• Details: Net outflow from exchanges
• Вердикт: Bullish

📊 ДЕРИВАТИВЫ (20% веса)
• Score: 4/10
• Details: Positive funding rate
• Вердикт: Bullish

📈 ТРЕНД (15% веса)
• Score: 3/10
• Details: EMA crossover
• Вердикт: Bullish

⚡ ИМПУЛЬС (12% веса)
• Score: 2/10
• Details: RSI 55
• Вердикт: Neutral

📊 ОБЪЁМ (10% веса)
• Score: 1/10
• Details: Above average
• Вердикт: Neutral

━━━━━━━━━━━━━━━━━━━━━━━━━━━
""" * 3  # Repeat 3 times to simulate long content
    
    print(f"Long message length: {len(long_message)} chars")
    
    # If message is short enough, no splitting needed
    if len(long_message) <= 4000:
        print(f"✓ Message is short enough ({len(long_message)} chars), no splitting needed")
        return
    
    # Simulate splitting logic
    parts = []
    sections = long_message.split("━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    current_part = ""
    for i, section in enumerate(sections):
        if i > 0:
            test_part = current_part + "━━━━━━━━━━━━━━━━━━━━━━━━━━━" + section
        else:
            test_part = current_part + section
        
        if len(test_part) > 3900:
            if current_part:
                parts.append(current_part)
            current_part = section
        else:
            current_part = test_part
    
    if current_part:
        parts.append(current_part)
    
    print(f"Split into {len(parts)} parts")
    for i, part in enumerate(parts):
        print(f"  Part {i+1}: {len(part)} chars")
        assert len(part) <= 4096, f"Part {i+1} exceeds Telegram limit!"
    
    print(f"✓ Test passed: Message split correctly into {len(parts)} parts, all under 4096 chars")


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
    
    print("Test 5: Message Length and Splitting")
    print("-" * 60)
    test_message_length_estimation()
    print()
    
    print("=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
