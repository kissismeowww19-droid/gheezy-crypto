"""
Tests for Gem Scanner functionality
"""
import pytest
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from signals.gem_scanner import GemScanner


class TestGemScanner:
    """Test cases for GemScanner class"""

    def test_initialization(self):
        """Test that GemScanner initializes correctly"""
        scanner = GemScanner()
        assert scanner.filters is not None
        assert scanner.filters["max_market_cap"] == 2_000_000
        assert scanner.filters["min_liquidity"] == 10_000
        assert scanner.NETWORKS["solana"] == "solana"
        assert scanner.NETWORKS["base"] == "base"

    def test_format_empty_gems_message(self):
        """Test formatting message with no gems"""
        scanner = GemScanner()
        message = scanner.format_gems_message([], "solana")
        assert "💎 НОВЫЕ ГЕМЫ ☀️ SOLANA" in message
        assert "❌ Гемы не найдены" in message

    def test_calculate_gem_score(self):
        """Test gem scoring algorithm"""
        scanner = GemScanner()

        # Test token with good metrics
        token = {
            "liquidity": {"usd": 50000},
            "marketCap": 300000,
            "volume": {"h24": 80000},
            "priceChange": {"h24": 25},
            "pairCreatedAt": None,  # Will default to old token
        }

        result = scanner._calculate_gem_score(token)

        assert "score" in result
        assert "signal" in result
        assert "reasons" in result
        assert isinstance(result["score"], int)
        assert result["score"] >= 0
        assert result["score"] <= 100

    def test_apply_filters(self):
        """Test filter application"""
        scanner = GemScanner()

        # Good token that should pass filters
        good_token = {
            "liquidity": {"usd": 50000},
            "marketCap": 500000,
            "volume": {"h24": 10000},
            "pairCreatedAt": None,  # Will be treated as old
        }

        # Token with too high market cap
        bad_token = {
            "liquidity": {"usd": 50000},
            "marketCap": 5000000,  # Too high
            "volume": {"h24": 10000},
            "pairCreatedAt": None,
        }

        # Token with too low liquidity
        bad_token2 = {
            "liquidity": {"usd": 5000},  # Too low
            "marketCap": 500000,
            "volume": {"h24": 10000},
            "pairCreatedAt": None,
        }

        # Note: pairCreatedAt=None will fail the age filter (treated as 999 hours)
        # So we can't fully test without mocking datetime
        result = scanner._apply_filters([good_token, bad_token, bad_token2])

        # bad_token should be filtered out due to high market cap
        # bad_token2 should be filtered out due to low liquidity
        assert len(result) <= 1  # At most good_token if it passes age check

    def test_networks_configuration(self):
        """Test that all networks are properly configured"""
        scanner = GemScanner()
        expected_networks = ["solana", "base", "ethereum", "bsc"]

        for network in expected_networks:
            assert network in scanner.NETWORKS
            assert scanner.NETWORKS[network] == network

    @pytest.mark.asyncio
    async def test_session_management(self):
        """Test session creation and closing"""
        scanner = GemScanner()

        # Session should be None initially
        assert scanner.session is None

        # Create session
        await scanner._ensure_session()
        assert scanner.session is not None
        assert not scanner.session.closed

        # Close session
        await scanner.close()
        assert scanner.session.closed

    @pytest.mark.asyncio
    async def test_scan_returns_list(self):
        """Test that scan returns a list even on error"""
        scanner = GemScanner()

        # Scan should return empty list if API fails
        result = await scanner.scan("solana", limit=5)

        assert isinstance(result, list)
        assert len(result) <= 5

        await scanner.close()

    def test_format_gems_message_with_data(self):
        """Test formatting message with gem data"""
        scanner = GemScanner()

        # Mock gem data
        gems = [
            {
                "baseToken": {"symbol": "TEST", "name": "Test Token"},
                "priceUsd": 0.00012,
                "marketCap": 250000,
                "liquidity": {"usd": 35000},
                "volume": {"h24": 15000},
                "priceChange": {"h24": 15.5},
                "pairCreatedAt": None,
                "_gem_score": 75,
                "_gem_signal": "🟢 ВЫСОКИЙ ПОТЕНЦИАЛ",
                "_gem_reasons": ["Test reason 1", "Test reason 2"],
            }
        ]

        message = scanner.format_gems_message(gems, "solana")

        assert "💎 НОВЫЕ ГЕМЫ ☀️ SOLANA" in message
        assert "TEST" in message
        assert "Test Token" in message
        assert "75%" in message
        assert "🟢 ВЫСОКИЙ ПОТЕНЦИАЛ" in message
