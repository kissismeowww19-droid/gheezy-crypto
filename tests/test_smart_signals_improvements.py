"""
Tests for Smart Signals improvements.
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.smart_signals import SmartSignalAnalyzer


class TestSymbolFiltering:
    """Test symbol filtering functionality."""
    
    def setup_method(self):
        """Setup test instance."""
        self.analyzer = SmartSignalAnalyzer()
    
    def test_should_skip_stablecoins(self):
        """Test that stablecoins are filtered out."""
        stablecoins = ["USDT", "USDC", "BUSD", "DAI", "TUSD"]
        for coin in stablecoins:
            assert self.analyzer._should_skip_symbol(coin) is True, f"{coin} should be skipped"
    
    def test_should_skip_wrapped_tokens(self):
        """Test that wrapped tokens are filtered out."""
        wrapped = ["WETH", "WBTC", "WBNB", "WSTETH", "CBBTC"]
        for coin in wrapped:
            assert self.analyzer._should_skip_symbol(coin) is True, f"{coin} should be skipped"
    
    def test_should_skip_special_chars(self):
        """Test that symbols with special characters are filtered."""
        special = ["BSC-USD", "USDT_0", "TEST-123"]
        for coin in special:
            assert self.analyzer._should_skip_symbol(coin) is True, f"{coin} should be skipped"
    
    def test_should_skip_long_symbols(self):
        """Test that very long symbols are filtered."""
        long_symbol = "VERYLONGSYMBOL123"
        assert self.analyzer._should_skip_symbol(long_symbol) is True
    
    def test_should_not_skip_valid_symbols(self):
        """Test that valid trading symbols pass through."""
        valid = ["BTC", "ETH", "SOL", "DOGE", "XRP", "ADA"]
        for coin in valid:
            assert self.analyzer._should_skip_symbol(coin) is False, f"{coin} should not be skipped"
    
    def test_case_insensitive_filtering(self):
        """Test that filtering is case-insensitive."""
        assert self.analyzer._should_skip_symbol("usdt") is True
        assert self.analyzer._should_skip_symbol("Usdt") is True
        assert self.analyzer._should_skip_symbol("USDT") is True


class TestDirectionDetermination:
    """Test direction determination logic."""
    
    def setup_method(self):
        """Setup test instance."""
        self.analyzer = SmartSignalAnalyzer()
    
    def test_strong_bullish(self):
        """Test strong bullish signals."""
        direction, emoji = self.analyzer._determine_direction(
            change_1h=1.5,
            change_4h=3.0,
            trend_score=8.0,
            funding_rate=0.0001
        )
        assert direction == "ЛОНГ"
        assert emoji == "📈"
    
    def test_strong_bearish(self):
        """Test strong bearish signals."""
        direction, emoji = self.analyzer._determine_direction(
            change_1h=-1.5,
            change_4h=-3.0,
            trend_score=2.0,
            funding_rate=-0.0001
        )
        assert direction == "ШОРТ"
        assert emoji == "📉"
    
    def test_neutral_signals(self):
        """Test neutral signals."""
        direction, emoji = self.analyzer._determine_direction(
            change_1h=0.1,
            change_4h=-0.1,
            trend_score=5.0,
            funding_rate=0.0
        )
        assert direction == "НЕЙТРАЛЬНО"
        assert emoji == "➡️"
    
    def test_extreme_funding_contrarian(self):
        """Test that extreme funding acts as contrarian signal."""
        # High funding (too many longs) should reduce bullish signals
        direction, emoji = self.analyzer._determine_direction(
            change_1h=0.3,
            change_4h=0.8,
            trend_score=6.0,
            funding_rate=0.0006  # Extreme positive funding
        )
        # This might still be bullish but funding adds bearish signal
        assert direction in ["ЛОНГ", "НЕЙТРАЛЬНО"]


class TestLevelCalculation:
    """Test dynamic level calculations."""
    
    def setup_method(self):
        """Setup test instance."""
        self.analyzer = SmartSignalAnalyzer()
    
    def test_long_levels_structure(self):
        """Test that long levels are properly structured."""
        price = 100.0
        atr_pct = 2.0
        levels = self.analyzer._calculate_levels(price, atr_pct, "ЛОНГ")
        
        assert "entry_low" in levels
        assert "entry_high" in levels
        assert "stop" in levels
        assert "tp1" in levels
        assert "tp2" in levels
        
        # Entry should be around current price
        assert levels["entry_low"] < price < levels["entry_high"]
        
        # Stop should be below entry for longs
        assert levels["stop"] < price
        
        # TPs should be above entry for longs
        assert levels["tp1"] > price
        assert levels["tp2"] > levels["tp1"]
    
    def test_short_levels_structure(self):
        """Test that short levels are properly structured."""
        price = 100.0
        atr_pct = 2.0
        levels = self.analyzer._calculate_levels(price, atr_pct, "ШОРТ")
        
        # Stop should be above entry for shorts
        assert levels["stop"] > price
        
        # TPs should be below entry for shorts
        assert levels["tp1"] < price
        assert levels["tp2"] < levels["tp1"]
    
    def test_atr_impact_on_levels(self):
        """Test that higher ATR creates wider levels."""
        price = 100.0
        
        levels_low_atr = self.analyzer._calculate_levels(price, 1.0, "ЛОНГ")
        levels_high_atr = self.analyzer._calculate_levels(price, 4.0, "ЛОНГ")
        
        # Higher ATR should create wider stop loss
        stop_range_low = abs(price - levels_low_atr["stop"])
        stop_range_high = abs(price - levels_high_atr["stop"])
        assert stop_range_high > stop_range_low
        
        # Higher ATR should create wider take profit
        tp_range_low = abs(levels_low_atr["tp1"] - price)
        tp_range_high = abs(levels_high_atr["tp1"] - price)
        assert tp_range_high > tp_range_low


class TestTop3Changes:
    """Test TOP-3 change detection."""
    
    def setup_method(self):
        """Setup test instance."""
        self.analyzer = SmartSignalAnalyzer()
    
    def test_detect_additions(self):
        """Test detection of new coins in TOP-3."""
        self.analyzer.top3_history = [
            {"symbol": "BTC", "score": 9.0},
            {"symbol": "ETH", "score": 8.5},
            {"symbol": "SOL", "score": 8.0}
        ]
        
        new_top3 = [
            {"symbol": "BTC", "score": 9.0},
            {"symbol": "ETH", "score": 8.5},
            {"symbol": "DOGE", "score": 8.2}  # New coin
        ]
        
        changes = self.analyzer.get_top3_changes(new_top3)
        
        assert changes["has_changes"] is True
        assert len(changes["added"]) == 1
        assert changes["added"][0]["symbol"] == "DOGE"
        assert len(changes["removed"]) == 1
        assert changes["removed"][0]["symbol"] == "SOL"
    
    def test_no_changes(self):
        """Test when TOP-3 remains the same."""
        self.analyzer.top3_history = [
            {"symbol": "BTC", "score": 9.0},
            {"symbol": "ETH", "score": 8.5},
            {"symbol": "SOL", "score": 8.0}
        ]
        
        new_top3 = [
            {"symbol": "BTC", "score": 9.0},
            {"symbol": "ETH", "score": 8.5},
            {"symbol": "SOL", "score": 8.0}
        ]
        
        changes = self.analyzer.get_top3_changes(new_top3)
        
        assert changes["has_changes"] is False
        assert len(changes["added"]) == 0
        assert len(changes["removed"]) == 0
