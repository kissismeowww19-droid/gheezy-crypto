"""
Tests for Compact Message Formatter.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from signals.message_formatter import CompactMessageFormatter


class TestCompactMessageFormatter:
    """Tests for CompactMessageFormatter class."""
    
    @pytest.fixture
    def formatter(self):
        """Create a formatter instance."""
        return CompactMessageFormatter()
    
    def test_format_long_signal(self, formatter):
        """Test formatting a LONG signal."""
        message = formatter.format_signal(
            coin="BTC",
            direction="long",
            entry_price=88021.0,
            targets={
                "tp1": 89500.0,
                "tp1_label": "VAH",
                "tp2": 91200.0,
                "tp2_label": "Short Liq",
                "sl": 85800.0,
                "sl_label": "Order Block",
                "rr": 2.3
            },
            confidence=75.0,
            timeframe="4H",
            levels={
                "poc": 88176.0,
                "resistance": 88659.0,
                "support": 86850.0
            },
            reasons=[
                {"icon": "🌊", "name": "Wyckoff", "value": "Accumulation (65%)"},
                {"icon": "🐋", "name": "Киты", "value": "накапливают"},
                {"icon": "💧", "name": "Магнит", "value": "$90.7K (short liq)"},
                {"icon": "🔄", "name": "Funding", "value": "норма (0.01%)"}
            ]
        )
        
        # Check that message contains key elements
        assert "🚀" in message
        assert "LONG BTC" in message
        assert "$88,021" in message
        assert "$89,500" in message
        assert "VAH" in message
        assert "1:2.3" in message
        assert "4H" in message
        assert "75%" in message
        assert "POC" in message
        assert "Wyckoff" in message
        assert "Киты" in message
    
    def test_format_short_signal(self, formatter):
        """Test formatting a SHORT signal."""
        message = formatter.format_signal(
            coin="ETH",
            direction="short",
            entry_price=3200.0,
            targets={
                "tp1": 3100.0,
                "tp2": 3050.0,
                "sl": 3250.0,
                "rr": 2.0
            },
            confidence=68.0,
            timeframe="4H"
        )
        
        assert "📉" in message
        assert "SHORT ETH" in message
        assert "$3,200" in message
        assert "$3,100" in message
        assert "1:2.0" in message
        assert "68%" in message
    
    def test_format_sideways_signal(self, formatter):
        """Test formatting a SIDEWAYS signal."""
        message = formatter.format_signal(
            coin="TON",
            direction="sideways",
            entry_price=5.0,
            targets={
                "tp1": 5.05,
                "tp2": 5.10,
                "sl": 4.95,
                "rr": None  # No R:R for sideways
            },
            confidence=52.0,
            timeframe="4H"
        )
        
        assert "➡️" in message
        assert "SIDEWAYS TON" in message
        assert "$5.00" in message
        assert "Диапазон" in message
        # Should not have R:R for sideways
        assert "R:R" not in message
    
    def test_format_price_large(self, formatter):
        """Test price formatting for large numbers."""
        assert formatter._format_price(88021.5) == "$88,021"
        assert formatter._format_price(1234567.8) == "$1,234,568"
    
    def test_format_price_medium(self, formatter):
        """Test price formatting for medium numbers."""
        assert formatter._format_price(123.45) == "$123.45"
        assert formatter._format_price(5.67) == "$5.67"
    
    def test_format_price_small(self, formatter):
        """Test price formatting for small numbers."""
        assert formatter._format_price(0.1234) == "$0.1234"
        assert formatter._format_price(0.5678) == "$0.5678"
    
    def test_format_price_very_small(self, formatter):
        """Test price formatting for very small numbers."""
        assert formatter._format_price(0.001234) == "$0.001234"
        assert formatter._format_price(0.000056) == "$0.000056"
    
    def test_format_rr(self, formatter):
        """Test R:R calculation."""
        # Long: Entry 100, TP 105, SL 98 -> Risk 2, Reward 5 -> R:R = 2.5
        rr = formatter._format_rr(entry=100, tp=105, sl=98)
        assert abs(rr - 2.5) < 0.01
        
        # Short: Entry 100, TP 95, SL 102 -> Risk 2, Reward 5 -> R:R = 2.5
        rr = formatter._format_rr(entry=100, tp=95, sl=102)
        assert abs(rr - 2.5) < 0.01
    
    def test_format_rr_zero_handling(self, formatter):
        """Test R:R calculation with zero values."""
        # Zero entry
        rr = formatter._format_rr(entry=0, tp=100, sl=90)
        assert rr == 0.0
        
        # Zero SL
        rr = formatter._format_rr(entry=100, tp=110, sl=0)
        assert rr == 0.0
        
        # Same entry and SL
        rr = formatter._format_rr(entry=100, tp=110, sl=100)
        assert rr == 0.0
    
    def test_get_top_reasons_wyckoff(self, formatter):
        """Test extracting Wyckoff reason."""
        enhancer_data = {
            "wyckoff": {
                "phase": "accumulation",
                "confidence": 0.65
            }
        }
        
        reasons = formatter._get_top_reasons(enhancer_data)
        
        assert len(reasons) > 0
        assert reasons[0]["icon"] == "🌊"
        assert reasons[0]["name"] == "Wyckoff"
        assert "Накопление" in reasons[0]["value"]
        assert "65%" in reasons[0]["value"]
    
    def test_get_top_reasons_whale(self, formatter):
        """Test extracting whale activity reason."""
        enhancer_data = {
            "whale_activity": {
                "signal": "bullish"
            }
        }
        
        reasons = formatter._get_top_reasons(enhancer_data)
        
        assert len(reasons) > 0
        whale_reason = next((r for r in reasons if r["name"] == "Киты"), None)
        assert whale_reason is not None
        assert whale_reason["icon"] == "🐋"
        assert "накапливают" in whale_reason["value"]
    
    def test_get_top_reasons_liquidation(self, formatter):
        """Test extracting liquidation magnet reason."""
        enhancer_data = {
            "liquidation_zones": {
                "nearest_short": {
                    "price": 90700.0
                }
            },
            "current_price": 88000.0
        }
        
        reasons = formatter._get_top_reasons(enhancer_data)
        
        liq_reason = next((r for r in reasons if r["name"] == "Магнит"), None)
        assert liq_reason is not None
        assert liq_reason["icon"] == "💧"
        assert "90.7K" in liq_reason["value"]
        assert "short liq" in liq_reason["value"]
    
    def test_get_top_reasons_funding(self, formatter):
        """Test extracting funding rate reason."""
        enhancer_data = {
            "funding": {
                "current_funding": 0.0001
            }
        }
        
        reasons = formatter._get_top_reasons(enhancer_data)
        
        funding_reason = next((r for r in reasons if r["name"] == "Funding"), None)
        assert funding_reason is not None
        assert funding_reason["icon"] == "🔄"
        assert "норма" in funding_reason["value"]
    
    def test_get_top_reasons_smc(self, formatter):
        """Test extracting SMC order block reason."""
        enhancer_data = {
            "smc_levels": {
                "order_blocks": [
                    {
                        "type": "bullish",
                        "low": 85800.0
                    }
                ]
            }
        }
        
        reasons = formatter._get_top_reasons(enhancer_data)
        
        smc_reason = next((r for r in reasons if r["name"] == "SMC"), None)
        assert smc_reason is not None
        assert smc_reason["icon"] == "🧠"
        assert "Bullish" in smc_reason["value"]
        assert "$85,800" in smc_reason["value"]
    
    def test_get_top_reasons_limit(self, formatter):
        """Test that only top 4 reasons are returned."""
        enhancer_data = {
            "wyckoff": {"phase": "accumulation", "confidence": 0.65},
            "whale_activity": {"signal": "bullish"},
            "liquidation_zones": {"nearest_short": {"price": 90700.0}},
            "funding": {"current_funding": 0.0001},
            "smc_levels": {"order_blocks": [{"type": "bullish", "low": 85800.0}]},
            "current_price": 88000.0
        }
        
        reasons = formatter._get_top_reasons(enhancer_data, limit=4)
        
        # Should return maximum 4 reasons
        assert len(reasons) <= 4
    
    def test_format_with_enhancer_data(self, formatter):
        """Test formatting with enhancer_data instead of reasons."""
        enhancer_data = {
            "wyckoff": {"phase": "accumulation", "confidence": 0.65},
            "whale_activity": {"signal": "bullish"},
            "current_price": 88000.0
        }
        
        message = formatter.format_signal(
            coin="BTC",
            direction="long",
            entry_price=88021.0,
            targets={"tp1": 89500.0, "tp2": 91200.0, "sl": 85800.0, "rr": 2.3},
            confidence=75.0,
            enhancer_data=enhancer_data
        )
        
        assert "Wyckoff" in message
        assert "Киты" in message
    
    def test_format_compact_line_count(self, formatter):
        """Test that formatted message is compact (15-20 lines)."""
        message = formatter.format_signal(
            coin="BTC",
            direction="long",
            entry_price=88021.0,
            targets={
                "tp1": 89500.0,
                "tp2": 91200.0,
                "sl": 85800.0,
                "rr": 2.3
            },
            confidence=75.0,
            levels={
                "poc": 88176.0,
                "resistance": 88659.0,
                "support": 86850.0
            },
            reasons=[
                {"icon": "🌊", "name": "Wyckoff", "value": "Accumulation (65%)"},
                {"icon": "🐋", "name": "Киты", "value": "накапливают"}
            ]
        )
        
        lines = message.split("\n")
        # Should be compact - around 15-20 lines
        assert len(lines) >= 10  # At least 10 lines
        assert len(lines) <= 25  # No more than 25 lines
    
    def test_case_insensitive_direction(self, formatter):
        """Test that direction is case-insensitive."""
        message_upper = formatter.format_signal(
            coin="BTC",
            direction="LONG",
            entry_price=88021.0,
            targets={"tp1": 89500.0, "tp2": 91200.0, "sl": 85800.0, "rr": 2.3},
            confidence=75.0
        )
        
        message_lower = formatter.format_signal(
            coin="BTC",
            direction="long",
            entry_price=88021.0,
            targets={"tp1": 89500.0, "tp2": 91200.0, "sl": 85800.0, "rr": 2.3},
            confidence=75.0
        )
        
        # Both should produce similar output
        assert "LONG BTC" in message_upper
        assert "LONG BTC" in message_lower
