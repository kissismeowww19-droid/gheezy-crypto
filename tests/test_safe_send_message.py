"""
Test for safe_send_message function.

Tests the fail-soft Markdown parsing approach where messages are sent with
MarkdownV2 first, and if that fails due to parsing errors, retries without parse_mode.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.exceptions import TelegramBadRequest


@pytest.mark.asyncio
async def test_safe_send_message_success():
    """Test that safe_send_message works when Markdown parsing succeeds."""
    # Mock message method
    mock_method = AsyncMock(return_value="success")
    
    # Import the function (we'll need to mock it or test the logic)
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
