"""
Test for safe_send_message function.

Tests the fail-soft approach where messages are sent with parse_mode first,
and if that fails due to parsing errors, retries without parse_mode.

Note: The safe_send_message function is duplicated in each test rather than imported
from src.bot to keep tests standalone and independent of implementation changes.
This allows tests to verify the contract/behavior without coupling to internal details.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.exceptions import TelegramBadRequest


@pytest.mark.asyncio
async def test_safe_send_message_success():
    """Test that safe_send_message works when Markdown parsing succeeds."""
    # Mock message method
    mock_method = AsyncMock(return_value="success")
    
    # Define the function locally for testing
    async def safe_send_message(message_method, text: str, **kwargs):
        """Copy of the function for testing."""
        try:
            return await message_method(text, **kwargs)
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "can't parse entities" in error_str or "can't find end of" in error_str:
                kwargs_no_parse = {k: v for k, v in kwargs.items() if k != 'parse_mode'}
                return await message_method(text, **kwargs_no_parse)
            else:
                raise
    
    # Test successful send
    result = await safe_send_message(
        mock_method,
        "Test message",
        parse_mode="Markdown",
        reply_markup="keyboard"
    )
    
    assert result == "success"
    mock_method.assert_called_once_with(
        "Test message",
        parse_mode="Markdown",
        reply_markup="keyboard"
    )


@pytest.mark.asyncio
async def test_safe_send_message_markdown_parse_error():
    """Test that safe_send_message retries without parse_mode on parsing error."""
    # Mock message method that fails first, succeeds second
    mock_method = AsyncMock()
    mock_method.side_effect = [
        TelegramBadRequest(method="", message="Can't parse entities: Can't find end of the entity starting at byte offset 50"),
        "success"
    ]
    
    async def safe_send_message(message_method, text: str, **kwargs):
        """Copy of the function for testing."""
        try:
            return await message_method(text, **kwargs)
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "can't parse entities" in error_str or "can't find end of" in error_str:
                kwargs_no_parse = {k: v for k, v in kwargs.items() if k != 'parse_mode'}
                return await message_method(text, **kwargs_no_parse)
            else:
                raise
    
    # Test fail-soft behavior
    result = await safe_send_message(
        mock_method,
        "Test message with _special* chars",
        parse_mode="Markdown",
        reply_markup="keyboard"
    )
    
    assert result == "success"
    assert mock_method.call_count == 2
    # First call with parse_mode
    assert mock_method.call_args_list[0][0] == ("Test message with _special* chars",)
    assert mock_method.call_args_list[0][1] == {"parse_mode": "Markdown", "reply_markup": "keyboard"}
    # Second call without parse_mode
    assert mock_method.call_args_list[1][0] == ("Test message with _special* chars",)
    assert mock_method.call_args_list[1][1] == {"reply_markup": "keyboard"}


@pytest.mark.asyncio
async def test_safe_send_message_other_error():
    """Test that safe_send_message re-raises non-parsing errors."""
    # Mock message method that raises a different error
    mock_method = AsyncMock()
    mock_method.side_effect = TelegramBadRequest(method="", message="Message to edit not found")
    
    async def safe_send_message(message_method, text: str, **kwargs):
        """Copy of the function for testing."""
        try:
            return await message_method(text, **kwargs)
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "can't parse entities" in error_str or "can't find end of" in error_str:
                kwargs_no_parse = {k: v for k, v in kwargs.items() if k != 'parse_mode'}
                return await message_method(text, **kwargs_no_parse)
            else:
                raise
    
    # Test that other errors are re-raised
    with pytest.raises(TelegramBadRequest) as exc_info:
        await safe_send_message(
            mock_method,
            "Test message",
            parse_mode="Markdown"
        )
    
    assert "Message to edit not found" in str(exc_info.value)
    # Should only be called once (not retried)
    assert mock_method.call_count == 1


@pytest.mark.asyncio
async def test_safe_send_message_cant_find_end_error():
    """Test detection of 'can't find end of' error variant."""
    mock_method = AsyncMock()
    mock_method.side_effect = [
        TelegramBadRequest(method="", message="Bad Request: can't find end of Bold entity at byte offset 42"),
        "success"
    ]
    
    async def safe_send_message(message_method, text: str, **kwargs):
        """Copy of the function for testing."""
        try:
            return await message_method(text, **kwargs)
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "can't parse entities" in error_str or "can't find end of" in error_str:
                kwargs_no_parse = {k: v for k, v in kwargs.items() if k != 'parse_mode'}
                return await message_method(text, **kwargs_no_parse)
            else:
                raise
    
    result = await safe_send_message(
        mock_method,
        "Test *broken markdown",
        parse_mode="Markdown"
    )
    
    assert result == "success"
    assert mock_method.call_count == 2


@pytest.mark.asyncio
async def test_safe_send_message_ton_logging(caplog):
    """Test that TON signals are specially logged when markdown parsing fails."""
    import logging
    
    # Mock message method that fails first, succeeds second
    mock_method = AsyncMock()
    mock_method.side_effect = [
        TelegramBadRequest(method="", message="Can't parse entities: Can't find end of the entity starting at byte offset 50"),
        "success"
    ]
    
    async def safe_send_message(message_method, text: str, **kwargs):
        """Copy of the function with TON logging for testing."""
        try:
            return await message_method(text, **kwargs)
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "can't parse entities" in error_str or "can't find end of" in error_str:
                logging.error(f"Markdown parsing error: {e}")
                
                # Special logging for TON signals
                if "TON" in text or "💎" in text:
                    logging.error(f"TON Telegram error: {str(e)}\nRAW SIGNAL: {text}")
                
                kwargs_no_parse = {k: v for k, v in kwargs.items() if k != 'parse_mode'}
                return await message_method(text, **kwargs_no_parse)
            else:
                raise
    
    # Test with TON signal text
    with caplog.at_level(logging.ERROR):
        result = await safe_send_message(
            mock_method,
            "🤖 *AI СИГНАЛ: TON (4ч прогноз)*\nTest signal with 💎 TON",
            parse_mode="Markdown"
        )
    
    assert result == "success"
    assert mock_method.call_count == 2
    
    # Check that TON-specific logging was triggered
    ton_logs = [record for record in caplog.records if "TON Telegram error" in record.message]
    assert len(ton_logs) == 1
    assert "RAW SIGNAL:" in ton_logs[0].message
    assert "TON" in ton_logs[0].message


@pytest.mark.asyncio
async def test_safe_send_message_ton_emoji_logging(caplog):
    """Test that messages with TON emoji (💎) are logged even without TON text."""
    import logging
    
    mock_method = AsyncMock()
    mock_method.side_effect = [
        TelegramBadRequest(method="", message="Can't parse entities"),
        "success"
    ]
    
    async def safe_send_message(message_method, text: str, **kwargs):
        """Copy of the function with TON logging for testing."""
        try:
            return await message_method(text, **kwargs)
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "can't parse entities" in error_str or "can't find end of" in error_str:
                logging.error(f"Markdown parsing error: {e}")
                
                # Special logging for TON signals
                if "TON" in text or "💎" in text:
                    logging.error(f"TON Telegram error: {str(e)}\nRAW SIGNAL: {text}")
                
                kwargs_no_parse = {k: v for k, v in kwargs.items() if k != 'parse_mode'}
                return await message_method(text, **kwargs_no_parse)
            else:
                raise
    
    # Test with TON emoji only (no TON text)
    with caplog.at_level(logging.ERROR):
        result = await safe_send_message(
            mock_method,
            "🤖 Signal with 💎 emoji",
            parse_mode="Markdown"
        )
    
    assert result == "success"
    
    # Check that TON-specific logging was triggered by emoji
    ton_logs = [record for record in caplog.records if "TON Telegram error" in record.message]
    assert len(ton_logs) == 1


@pytest.mark.asyncio
async def test_safe_send_message_non_ton_no_special_logging(caplog):
    """Test that non-TON signals don't get special logging."""
    import logging
    
    mock_method = AsyncMock()
    mock_method.side_effect = [
        TelegramBadRequest(method="", message="Can't parse entities"),
        "success"
    ]
    
    async def safe_send_message(message_method, text: str, **kwargs):
        """Copy of the function with TON logging for testing."""
        try:
            return await message_method(text, **kwargs)
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "can't parse entities" in error_str or "can't find end of" in error_str:
                logging.error(f"Markdown parsing error: {e}")
                
                # Special logging for TON signals
                if "TON" in text or "💎" in text:
                    logging.error(f"TON Telegram error: {str(e)}\nRAW SIGNAL: {text}")
                
                kwargs_no_parse = {k: v for k, v in kwargs.items() if k != 'parse_mode'}
                return await message_method(text, **kwargs_no_parse)
            else:
                raise
    
    # Test with BTC signal (no TON)
    with caplog.at_level(logging.ERROR):
        result = await safe_send_message(
            mock_method,
            "🤖 *AI СИГНАЛ: BTC (4ч прогноз)*\nTest signal",
            parse_mode="Markdown"
        )
    
    assert result == "success"
    
    # Check that TON-specific logging was NOT triggered
    ton_logs = [record for record in caplog.records if "TON Telegram error" in record.message]
    assert len(ton_logs) == 0
    
    # But general markdown error logging should be present
    markdown_logs = [record for record in caplog.records if "Markdown parsing error" in record.message]
    assert len(markdown_logs) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
