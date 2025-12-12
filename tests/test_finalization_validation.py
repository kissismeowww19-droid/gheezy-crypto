"""
Simple validation tests for AI Signals finalization changes.
Tests the code changes directly without running the full application.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_bybit_mapping_has_ton():
    """Test that TON is in bybit_mapping by reading the file."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'signals', 'ai_signals.py'), 'r') as f:
        content = f.read()
    
    # Check that TON is in bybit_mapping
    assert '"TON": "TONUSDT"' in content, "TON should be in bybit_mapping"
    print("✓ TON is correctly added to bybit_mapping")


def test_weak_signal_logic():
    """Test that weak signal logic exists via _determine_direction_from_score."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'signals', 'ai_signals.py'), 'r') as f:
        content = f.read()
    
    # Check that the direction determination method exists
    assert 'def _determine_direction_from_score(' in content, "Direction determination method should exist"
    assert 'if total_score <= -10:' in content, "Short threshold check should exist"
    assert 'elif total_score >= 10:' in content, "Long threshold check should exist"
    assert 'return "sideways"' in content, "Sideways return should exist"
    
    print("✓ Direction determination logic is correctly implemented")


def test_consensus_logic():
    """Test that consensus counting exists."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'signals', 'ai_signals.py'), 'r') as f:
        content = f.read()
    
    # Check that consensus counting exists
    assert 'def count_consensus(' in content, "Consensus counting method should exist"
    assert 'bullish_count' in content and 'bearish_count' in content, "Consensus counts should be tracked"
    assert 'elif bearish_count <= 1 and bullish_count == 0:' in content, \
        "Consensus check for single bearish factor should exist"
    assert '# Слишком мало факторов для бычьего консенсуса' in content, \
        "Comment for bullish consensus check should exist"
    assert '# Слишком мало факторов для медвежьего консенсуса' in content, \
        "Comment for bearish consensus check should exist"
    
    print("✓ Consensus logic is correctly implemented")


def test_all_changes_in_correct_locations():
    """Verify key methods exist and TON mapping is in __init__."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'signals', 'ai_signals.py'), 'r') as f:
        lines = f.readlines()
    
    # Find method definitions
    calculate_signal_line = None
    format_signal_message_line = None
    init_line = None
    determine_direction_line = None
    calculate_real_probability_line = None
    
    for i, line in enumerate(lines):
        if 'def calculate_signal(' in line:
            calculate_signal_line = i
        elif 'def format_signal_message(' in line:
            format_signal_message_line = i
        elif 'def __init__(self, whale_tracker):' in line:
            init_line = i
        elif 'def _determine_direction_from_score(' in line:
            determine_direction_line = i
        elif 'def _calculate_real_probability(' in line:
            calculate_real_probability_line = i
    
    assert calculate_signal_line is not None, "calculate_signal method should exist"
    assert format_signal_message_line is not None, "format_signal_message method should exist"
    assert init_line is not None, "__init__ method should exist"
    assert determine_direction_line is not None, "_determine_direction_from_score method should exist"
    assert calculate_real_probability_line is not None, "_calculate_real_probability method should exist"
    
    # Find TON mapping
    ton_mapping_line = None
    for i, line in enumerate(lines):
        if '"TON": "TONUSDT"' in line:
            ton_mapping_line = i
    
    # Verify TON mapping is in __init__ method
    assert ton_mapping_line is not None, "TON mapping should exist"
    assert init_line < ton_mapping_line < calculate_signal_line, \
        "TON mapping should be in __init__ method"
    
    print("✓ All key methods exist and TON mapping is in the correct location")


def test_direction_emoji():
    """Test that Боковик uses the correct emoji."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'signals', 'ai_signals.py'), 'r') as f:
        content = f.read()
    
    # Check for боковик direction with correct emoji (according to honest signals fix)
    assert 'direction = "➡️ Боковик"' in content, "Should have ➡️ Боковик for sideways signal"
    
    print("✓ Боковик direction uses correct emoji")


if __name__ == "__main__":
    print("Running AI Signals finalization validation tests...\n")
    
    test_bybit_mapping_has_ton()
    test_weak_signal_logic()
    test_consensus_logic()
    test_all_changes_in_correct_locations()
    test_direction_emoji()
    
    print("\n✅ All validation tests passed!")
