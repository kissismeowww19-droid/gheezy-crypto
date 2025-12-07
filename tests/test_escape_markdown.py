"""
Test for escape_markdown function.
Simple test without heavy dependencies.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы Markdown для безопасного отображения в Telegram.
    
    Args:
        text: Текст для экранирования
        
    Returns:
        Экранированный текст
    """
    if not text or not isinstance(text, str):
        return text
    
    # Список специальных символов Markdown, которые нужно экранировать
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


def test_escape_markdown_basic():
    """Test that escape_markdown properly escapes special characters."""
    # Test basic special characters
    assert escape_markdown("Hello_World") == "Hello\\_World"
    assert escape_markdown("Test*Bold*") == "Test\\*Bold\\*"
    assert escape_markdown("Link[text]") == "Link\\[text\\]"
    assert escape_markdown("Code`block`") == "Code\\`block\\`"
    print("✓ Basic escape tests passed")


def test_escape_markdown_multiple():
    """Test multiple special characters."""
    input_text = "Breaking news: BTC up 5%! [Details]"
    expected = "Breaking news: BTC up 5%\\! \\[Details\\]"
    assert escape_markdown(input_text) == expected
    print("✓ Multiple character escape tests passed")


def test_escape_markdown_news():
    """Test news-like content with various special characters."""
    news_title = "Bitcoin's price surged by 10% - analysts predict more gains!"
    escaped = escape_markdown(news_title)
    # Should escape: - (dash), ! (exclamation)
    assert "\\-" in escaped
    assert "\\!" in escaped
    print("✓ News-like content escape tests passed")


def test_escape_markdown_empty():
    """Test with None or empty."""
    assert escape_markdown("") == ""
    assert escape_markdown(None) is None
    print("✓ Empty/None tests passed")


def test_escape_markdown_all_special():
    """Test all special characters."""
    all_special = "_*[]()~`>#+-=|{}.!"
    escaped_all = escape_markdown(all_special)
    # Each character should be escaped with backslash
    for char in all_special:
        assert f"\\{char}" in escaped_all
    print("✓ All special characters escape tests passed")


def test_escape_markdown_real_news_examples():
    """Test with real-world news title examples."""
    examples = [
        ("Breaking: Bitcoin hits $50,000!", "Breaking: Bitcoin hits $50,000\\!"),
        ("ETH 2.0 - The upgrade everyone's waiting for", "ETH 2\\.0 \\- The upgrade everyone's waiting for"),
        ("Market Analysis [2024]: Top 5 Trends", "Market Analysis \\[2024\\]: Top 5 Trends"),
        ("Price Alert! BTC > $45K", "Price Alert\\! BTC \\> $45K"),
    ]
    
    for original, expected in examples:
        result = escape_markdown(original)
        assert result == expected, f"Failed for: {original}\nExpected: {expected}\nGot: {result}"
    
    print("✓ Real-world news examples tests passed")


if __name__ == "__main__":
    test_escape_markdown_basic()
    test_escape_markdown_multiple()
    test_escape_markdown_news()
    test_escape_markdown_empty()
    test_escape_markdown_all_special()
    test_escape_markdown_real_news_examples()
    print("\n✅ All escape_markdown tests passed!")
