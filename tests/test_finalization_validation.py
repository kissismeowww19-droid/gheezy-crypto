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
    """Test that weak signal logic exists in calculate_signal."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'signals', 'ai_signals.py'), 'r') as f:
        content = f.read()
    
    # Check that the weak signal check exists
    assert 'if abs(total_score) < 5:' in content, "Weak signal check should exist"
    assert '# Очень слабый сетап, почти нет сигнала' in content, "Weak signal comment should exist"
    
    # Check that it comes before other direction checks
    weak_signal_pos = content.find('if abs(total_score) < 5:')
    strong_up_pos = content.find('elif total_score > 20:')
    assert weak_signal_pos < strong_up_pos, "Weak signal check should come before strong signal checks"
    
    print("✓ Weak signal logic is correctly implemented")


def test_consensus_logic():
    """Test that consensus logic handles single factors correctly."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'signals', 'ai_signals.py'), 'r') as f:
        content = f.read()
    
    # Check that the consensus logic exists
    assert 'if bullish_count <= 1 and bearish_count == 0:' in content, \
        "Consensus check for single bullish factor should exist"
    assert 'elif bearish_count <= 1 and bullish_count == 0:' in content, \
        "Consensus check for single bearish factor should exist"
    assert '# Слишком мало факторов для бычьего консенсуса' in content, \
        "Comment for bullish consensus check should exist"
    assert '# Слишком мало факторов для медвежьего консенсуса' in content, \
        "Comment for bearish consensus check should exist"
    
    print("✓ Consensus logic is correctly implemented")


def test_all_changes_in_correct_locations():
    """Verify all changes are in the correct methods."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'signals', 'ai_signals.py'), 'r') as f:
        lines = f.readlines()
    
    # Find method definitions
    calculate_signal_line = None
    format_signal_message_line = None
    init_line = None
    
    for i, line in enumerate(lines):
        if 'def calculate_signal(' in line:
            calculate_signal_line = i
        elif 'def format_signal_message(' in line:
            format_signal_message_line = i
        elif 'def __init__(self, whale_tracker):' in line:
            init_line = i
    
    assert calculate_signal_line is not None, "calculate_signal method should exist"
    assert format_signal_message_line is not None, "format_signal_message method should exist"
    assert init_line is not None, "__init__ method should exist"
    
    # Find where changes are
    weak_signal_line = None
    consensus_line = None
    ton_mapping_line = None
    
    for i, line in enumerate(lines):
        if 'if abs(total_score) < 5:' in line:
            weak_signal_line = i
        elif 'if bullish_count <= 1 and bearish_count == 0:' in line:
            consensus_line = i
        elif '"TON": "TONUSDT"' in line:
            ton_mapping_line = i
    
    # Verify changes are in correct methods
    assert calculate_signal_line < weak_signal_line < format_signal_message_line, \
        "Weak signal logic should be in calculate_signal method"
    assert format_signal_message_line < consensus_line, \
        "Consensus logic should be in format_signal_message method"
    assert init_line < ton_mapping_line < calculate_signal_line, \
        "TON mapping should be in __init__ method"
    
    print("✓ All changes are in the correct method locations")


def test_direction_emoji():
    """Test that Боковик uses the correct emoji."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'signals', 'ai_signals.py'), 'r') as f:
        content = f.read()
    
    # Check for both боковик directions with correct emojis
    assert 'direction = "📊 Боковик"' in content, "Should have 📊 Боковик for very weak signal"
    assert 'direction = "➡️ Боковик"' in content, "Should have ➡️ Боковик for moderate weak signal"
    
    print("✓ Боковик directions use correct emojis")


if __name__ == "__main__":
    print("Running AI Signals finalization validation tests...\n")
    
    test_bybit_mapping_has_ton()
    test_weak_signal_logic()
    test_consensus_logic()
    test_all_changes_in_correct_locations()
    test_direction_emoji()
    
    print("\n✅ All validation tests passed!")
