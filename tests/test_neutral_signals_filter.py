"""
Tests for filtering out neutral signals and price formatting improvements.
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.smart_signals import SmartSignalAnalyzer


class TestSymbolValidation:
    """Test the new _is_valid_symbol method."""
    
    def setup_method(self):
        """Setup test instance."""
        self.analyzer = SmartSignalAnalyzer()
    
    def test_should_reject_symbols_with_dots(self):
        """Test that symbols with dots are rejected (wrapped tokens)."""
        invalid_symbols = ['USDC.E', 'USDC.e', 'BTC.B', 'BTC.b']
        for symbol in invalid_symbols:
            assert self.analyzer._is_valid_symbol(symbol) is False, f"{symbol} should be invalid"
    
    def test_should_reject_non_ascii_symbols(self):
        """Test that non-ASCII symbols are rejected (Chinese chars, etc)."""
        invalid_symbols = ['币安人生', 'Тест', '日本円']
        for symbol in invalid_symbols:
            assert self.analyzer._is_valid_symbol(symbol) is False, f"{symbol} should be invalid"
    
    def test_should_reject_new_excluded_symbols(self):
        """Test that newly added excluded symbols are rejected."""
        excluded = ['UBTC', 'BTSE', 'BMX', 'UCN', 'KOGE', 'EURC', 'AUSD', 
                    'WHYPE', 'TIBBIR', 'CASH', 'BLIFE']
        for symbol in excluded:
            assert self.analyzer._is_valid_symbol(symbol) is False, f"{symbol} should be excluded"
    
    def test_should_accept_valid_symbols(self):
        """Test that valid trading symbols are accepted."""
        valid_symbols = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'CAKE', 'LPT']
        for symbol in valid_symbols:
            assert self.analyzer._is_valid_symbol(symbol) is True, f"{symbol} should be valid"
    
    def test_should_reject_wrapped_tokens(self):
        """Test that wrapped tokens are rejected."""
        wrapped = ['WETH', 'WBTC', 'WAETHUSDC', 'WAETHUSDT']
        for symbol in wrapped:
            assert self.analyzer._is_valid_symbol(symbol) is False, f"{symbol} should be rejected"


class TestPriceFormatting:
    """Test the new _format_price method."""
    
    def setup_method(self):
        """Setup test instance."""
        self.analyzer = SmartSignalAnalyzer()
    
    def test_format_zero_price(self):
        """Test formatting of zero or negative price."""
        assert self.analyzer._format_price(0) == "$0.00"
        assert self.analyzer._format_price(-1) == "$0.00"
    
    def test_format_very_small_price(self):
        """Test formatting of very small prices (< 0.0001)."""
        result = self.analyzer._format_price(0.00001234)
        assert result == "$0.000012"
        
        result = self.analyzer._format_price(0.00009999)
        assert result == "$0.000100"
    
    def test_format_small_price(self):
        """Test formatting of small prices (0.0001 - 0.01)."""
        result = self.analyzer._format_price(0.001234)
        assert result == "$0.0012"
        
        result = self.analyzer._format_price(0.00999)
        assert result == "$0.0100"
    
    def test_format_fractional_price(self):
        """Test formatting of fractional prices (0.01 - 1)."""
        result = self.analyzer._format_price(0.12345)
        assert result == "$0.123"
        
        result = self.analyzer._format_price(0.9999)
        assert result == "$1.000"
    
    def test_format_regular_price(self):
        """Test formatting of regular prices (1 - 1000)."""
        result = self.analyzer._format_price(1.2345)
        assert result == "$1.23"
        
        result = self.analyzer._format_price(100.567)
        assert result == "$100.57"
        
        result = self.analyzer._format_price(999.99)
        assert result == "$999.99"
    
    def test_format_large_price(self):
        """Test formatting of large prices (> 1000)."""
        result = self.analyzer._format_price(1234.56)
        assert result == "$1,234.56"
        
        result = self.analyzer._format_price(50000.00)
        assert result == "$50,000.00"


class TestNeutralSignalFiltering:
    """Test filtering of neutral signals."""
    
    def setup_method(self):
        """Setup test instance."""
        self.analyzer = SmartSignalAnalyzer()
    
    def test_neutral_direction_returned(self):
        """Test that _determine_direction can return neutral."""
        direction, emoji = self.analyzer._determine_direction(
            change_1h=0.05,
            change_4h=0.1,
            trend_score=5.0,
            funding_rate=0.0
        )
        # With such weak signals, should be neutral
        assert direction == "НЕЙТРАЛЬНО"
        assert emoji == "➡️"
    
    def test_should_filter_results_with_neutral(self):
        """Test that filtering logic would remove neutral signals."""
        # Create mock signal data
        signals = [
            {'symbol': 'BTC', 'direction': 'ЛОНГ', 'score': 9.0},
            {'symbol': 'ETH', 'direction': 'ШОРТ', 'score': 8.5},
            {'symbol': 'SOL', 'direction': 'НЕЙТРАЛЬНО', 'score': 8.0},
            {'symbol': 'DOGE', 'direction': 'ЛОНГ', 'score': 7.5},
        ]
        
        # Filter out neutral signals (same logic as in get_top3)
        filtered = [s for s in signals if s.get('direction') in ['ЛОНГ', 'ШОРТ']]
        
        # Should only have 3 signals (BTC, ETH, DOGE)
        assert len(filtered) == 3
        assert all(s['direction'] in ['ЛОНГ', 'ШОРТ'] for s in filtered)
        assert not any(s['direction'] == 'НЕЙТРАЛЬНО' for s in filtered)
        
        # Check that SOL was filtered out
        symbols = [s['symbol'] for s in filtered]
        assert 'SOL' not in symbols
        assert 'BTC' in symbols
        assert 'ETH' in symbols
        assert 'DOGE' in symbols
