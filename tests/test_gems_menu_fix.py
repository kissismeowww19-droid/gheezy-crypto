"""
Tests for gems menu fixes:
1. HTML parsing error fix (using Markdown instead of HTML)
2. Gems button moved to signals menu

This test verifies the changes by examining the bot.py source code directly.
"""

import os
import re


def get_bot_source():
    """Read the bot.py source code."""
    bot_path = os.path.join(os.path.dirname(__file__), "..", "src", "bot.py")
    with open(bot_path, "r", encoding="utf-8") as f:
        return f.read()


def test_main_keyboard_no_gems_button():
    """Test that the main keyboard does not have the gems button."""
    source = get_bot_source()
    
    # Find get_main_keyboard function
    main_keyboard_match = re.search(
        r'def get_main_keyboard\(\).*?return InlineKeyboardMarkup\((.*?)\n    \)',
        source,
        re.DOTALL
    )
    
    assert main_keyboard_match, "Could not find get_main_keyboard function"
    main_keyboard_code = main_keyboard_match.group(1)
    
    # Check that "gems" callback_data is not in main keyboard
    assert 'callback_data="gems"' not in main_keyboard_code, \
        "Gems button should not be in main menu"
    
    # Verify that "📊 Рынок" button exists
    assert "📊 Рынок" in main_keyboard_code, "Market button should exist in main menu"


def test_signals_menu_has_gems_button():
    """Test that the signals menu has the gems button."""
    source = get_bot_source()
    
    # Find get_signals_menu_keyboard function
    signals_menu_match = re.search(
        r'def get_signals_menu_keyboard\(\).*?return InlineKeyboardMarkup\((.*?)\n    \)',
        source,
        re.DOTALL
    )
    
    assert signals_menu_match, "Could not find get_signals_menu_keyboard function"
    signals_menu_code = signals_menu_match.group(1)
    
    # Check that gems button exists
    assert 'callback_data="gems"' in signals_menu_code, \
        "Gems button should be in signals menu"
    assert "💎 Новые гемы" in signals_menu_code, \
        "Gems button text should be correct"


def test_gems_network_keyboard_back_button():
    """Test that the gems network keyboard back button goes to signals menu."""
    source = get_bot_source()
    
    # Find get_gems_network_keyboard function
    gems_network_match = re.search(
        r'def get_gems_network_keyboard\(\).*?return InlineKeyboardMarkup\((.*?)\n    \)',
        source,
        re.DOTALL
    )
    
    assert gems_network_match, "Could not find get_gems_network_keyboard function"
    gems_network_code = gems_network_match.group(1)
    
    # Check that back button goes to menu_signals
    assert 'callback_data="menu_signals"' in gems_network_code, \
        "Back button should go to signals menu"


def test_welcome_text_mentions_gems_in_signals():
    """Test that the welcome text mentions gems as part of signals."""
    source = get_bot_source()
    
    # Find get_welcome_text function
    welcome_text_match = re.search(
        r'def get_welcome_text\(name: str\) -> str:(.*?)return text',
        source,
        re.DOTALL
    )
    
    assert welcome_text_match, "Could not find get_welcome_text function"
    welcome_text_code = welcome_text_match.group(1)
    
    # Check that gems are mentioned as part of signals
    assert "Сигналы — торговые сигналы + новые гемы" in welcome_text_code, \
        "Welcome text should mention gems as part of signals"
    
    # Check that there is no separate gems line
    assert "• 💎 Новые гемы — поиск свежих токенов на DEX" not in welcome_text_code, \
        "Welcome text should not have a separate gems line"


def test_gems_menu_uses_markdown():
    """Test that gems_menu uses Markdown parse mode."""
    source = get_bot_source()
    
    # Find gems_menu function
    gems_menu_match = re.search(
        r'async def gems_menu\(callback: CallbackQuery\):(.*?)await callback\.answer\(\)',
        source,
        re.DOTALL
    )
    
    assert gems_menu_match, "Could not find gems_menu function"
    gems_menu_code = gems_menu_match.group(1)
    
    # Check that it uses Markdown parse mode
    assert "ParseMode.MARKDOWN" in gems_menu_code or 'parse_mode="Markdown"' in gems_menu_code, \
        "gems_menu should use Markdown parse mode"
    
    # Check that it doesn't use HTML parse mode
    assert 'parse_mode="HTML"' not in gems_menu_code, \
        "gems_menu should not use HTML parse mode"
    
    # Check that it uses Markdown bold (*) not HTML bold (<b>)
    assert "*Новые гемы*" in gems_menu_code, \
        "gems_menu should use Markdown bold syntax"
    assert "<b>Новые гемы</b>" not in gems_menu_code, \
        "gems_menu should not use HTML bold syntax"
    
    # Check that it uses "до" instead of "<"
    assert "Возраст до 7 дней" in gems_menu_code, \
        "gems_menu should use 'до' instead of '<'"
    assert "капа до $2M" in gems_menu_code, \
        "gems_menu should use 'до' instead of '<'"


if __name__ == "__main__":
    print("Running tests...")
    
    test_main_keyboard_no_gems_button()
    print("✓ test_main_keyboard_no_gems_button passed")
    
    test_signals_menu_has_gems_button()
    print("✓ test_signals_menu_has_gems_button passed")
    
    test_gems_network_keyboard_back_button()
    print("✓ test_gems_network_keyboard_back_button passed")
    
    test_welcome_text_mentions_gems_in_signals()
    print("✓ test_welcome_text_mentions_gems_in_signals passed")
    
    test_gems_menu_uses_markdown()
    print("✓ test_gems_menu_uses_markdown passed")
    
    print("\n✅ All tests passed!")
