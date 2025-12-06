"""
Tests for API key loading from settings.

Verifies that API keys are properly loaded from Pydantic settings
instead of directly from os.getenv(), ensuring .env file is properly read.
"""

import sys
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import Mock, patch
from importlib.util import spec_from_file_location, module_from_spec


def load_api_keys_module():
    """Load api_keys module directly without triggering package imports."""
    api_keys_path = src_path / "whale" / "api_keys.py"
    spec = spec_from_file_location("whale.api_keys", api_keys_path)
    module = module_from_spec(spec)
    
    # Create a mock config module
    mock_config = type(sys)('config')
    mock_config.settings = Mock()
    mock_config.settings.etherscan_api_key = ""
    mock_config.settings.etherscan_api_key_2 = ""
    mock_config.settings.etherscan_api_key_3 = ""
    
    sys.modules['config'] = mock_config
    
    spec.loader.exec_module(module)
    return module


def test_api_keys_uses_settings():
    """Test that api_keys module imports settings from config."""
    api_keys_module = load_api_keys_module()
    api_keys_module.reset_api_keys()
    
    # Mock the settings object
    mock_settings = Mock()
    mock_settings.etherscan_api_key = "test_key_1"
    mock_settings.etherscan_api_key_2 = "test_key_2"
    mock_settings.etherscan_api_key_3 = "test_key_3"
    
    # Patch the settings in the api_keys module
    with patch.object(api_keys_module, 'settings', mock_settings):
        api_keys_module.reset_api_keys()
        api_keys_module.init_api_keys()
        
        # Verify keys were loaded from settings
        assert api_keys_module.get_api_key_count() == 3
        
        # Verify key rotation works
        key1 = api_keys_module.get_next_api_key()
        key2 = api_keys_module.get_next_api_key()
        key3 = api_keys_module.get_next_api_key()
        key4 = api_keys_module.get_next_api_key()  # Should cycle back to first
        
        assert key1 == "test_key_1"
        assert key2 == "test_key_2"
        assert key3 == "test_key_3"
        assert key4 == "test_key_1"  # Cycled back


def test_api_keys_filters_empty_strings():
    """Test that empty strings are filtered out from API keys."""
    api_keys_module = load_api_keys_module()
    api_keys_module.reset_api_keys()
    
    # Mock the settings object with some empty keys
    mock_settings = Mock()
    mock_settings.etherscan_api_key = "test_key_1"
    mock_settings.etherscan_api_key_2 = ""  # Empty string
    mock_settings.etherscan_api_key_3 = "test_key_3"
    
    with patch.object(api_keys_module, 'settings', mock_settings):
        api_keys_module.reset_api_keys()
        api_keys_module.init_api_keys()
        
        # Should only have 2 keys (empty string filtered out)
        assert api_keys_module.get_api_key_count() == 2


def test_api_keys_handles_no_keys():
    """Test behavior when no API keys are configured."""
    api_keys_module = load_api_keys_module()
    api_keys_module.reset_api_keys()
    
    # Mock the settings object with no keys
    mock_settings = Mock()
    mock_settings.etherscan_api_key = ""
    mock_settings.etherscan_api_key_2 = ""
    mock_settings.etherscan_api_key_3 = ""
    
    with patch.object(api_keys_module, 'settings', mock_settings):
        api_keys_module.reset_api_keys()
        api_keys_module.init_api_keys()
        
        # Should have 0 keys
        assert api_keys_module.get_api_key_count() == 0
        # Should return None when no keys configured
        assert api_keys_module.get_next_api_key() is None


def test_api_keys_single_key():
    """Test behavior with a single API key."""
    api_keys_module = load_api_keys_module()
    api_keys_module.reset_api_keys()
    
    # Mock the settings object with single key
    mock_settings = Mock()
    mock_settings.etherscan_api_key = "single_key"
    mock_settings.etherscan_api_key_2 = ""
    mock_settings.etherscan_api_key_3 = ""
    
    with patch.object(api_keys_module, 'settings', mock_settings):
        api_keys_module.reset_api_keys()
        api_keys_module.init_api_keys()
        
        # Should have 1 key
        assert api_keys_module.get_api_key_count() == 1
        
        # Should always return the same key
        key1 = api_keys_module.get_next_api_key()
        key2 = api_keys_module.get_next_api_key()
        key3 = api_keys_module.get_next_api_key()
        
        assert key1 == "single_key"
        assert key2 == "single_key"
        assert key3 == "single_key"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
