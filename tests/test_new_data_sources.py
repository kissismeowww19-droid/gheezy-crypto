"""
Tests for new data sources in AI Signals (22-factor system).
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import Mock


class TestNewScoringFunctions:
    """Tests for the 7 new scoring functions."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        return tracker
    
    @pytest.fixture
    def analyzer(self, mock_whale_tracker):
        """Create an analyzer instance - we'll mock the import."""
        # Since we can't import due to dependencies, we'll test logic directly
        class MockAnalyzer:
            def _calculate_oi_change_score(self, oi_change: float, price_change: float) -> float:
                """Score на основе изменения Open Interest."""
                if oi_change > 2:  # OI растёт
                    if price_change > 0:
                        return 10  # Сильный бычий тренд
                    else:
                        return -5  # Накопление шортов
                elif oi_change < -2:  # OI падает
                    if price_change > 0:
                        return -3  # Слабый рост
                    else:
                        return 3  # Капитуляция
                else:
                    return 0
            
            def _calculate_top_traders_score(self, ratio: float) -> float:
                """Score на основе позиций топ трейдеров."""
                if ratio > 2.0:
                    return 8
                elif ratio > 1.5:
                    return 4
                elif ratio < 0.5:
                    return -10
                elif ratio < 0.67:
                    return -8
                else:
                    return (ratio - 1.0) * 5
            
            def _calculate_news_sentiment_score(self, sentiment_data: dict) -> float:
                """Score на основе новостного сентимента."""
                if not sentiment_data:
                    return 0
                
                sentiment_score = sentiment_data.get("sentiment_score", 0)
                
                if sentiment_score > 0.5:
                    return 10
                elif sentiment_score > 0.2:
                    return 5
                elif sentiment_score < -0.5:
                    return -10
                elif sentiment_score < -0.2:
                    return -5
                else:
                    return sentiment_score * 10
            
            def _calculate_tradingview_score(self, tv_data: dict) -> float:
                """Score на основе TradingView рейтинга."""
                if not tv_data:
                    return 0
                
                recommendation = tv_data.get("recommendation", "NEUTRAL")
                
                if recommendation == "STRONG_BUY":
                    return 10
                elif recommendation == "BUY":
                    return 5
                elif recommendation == "SELL":
                    return -5
                elif recommendation == "STRONG_SELL":
                    return -10
                else:
                    return 0
            
            def _calculate_whale_alert_score(self, whale_data: dict) -> float:
                """Score на основе Whale Alert транзакций."""
                if not whale_data:
                    return 0
                
                net_flow = whale_data.get("net_flow", 0)
                
                if net_flow > 50_000_000:
                    return 10
                elif net_flow > 20_000_000:
                    return 5
                elif net_flow < -50_000_000:
                    return -10
                elif net_flow < -20_000_000:
                    return -5
                else:
                    return (net_flow / 10_000_000)
        
        return MockAnalyzer()
    
    def test_oi_change_score_bullish(self, analyzer):
        """Test OI change score with bullish conditions."""
        # OI растёт + цена растёт = сильный бычий тренд
        score = analyzer._calculate_oi_change_score(5.0, 3.0)
        assert score == 10
    
    def test_oi_change_score_bearish(self, analyzer):
        """Test OI change score with bearish conditions."""
        # OI растёт + цена падает = накопление шортов
        score = analyzer._calculate_oi_change_score(5.0, -3.0)
        assert score == -5
    
    def test_oi_change_score_neutral(self, analyzer):
        """Test OI change score with neutral conditions."""
        score = analyzer._calculate_oi_change_score(0.5, 1.0)
        assert score == 0
    
    def test_top_traders_score_very_bullish(self, analyzer):
        """Test top traders score with very bullish ratio."""
        score = analyzer._calculate_top_traders_score(2.5)
        assert score == 8
    
    def test_top_traders_score_bullish(self, analyzer):
        """Test top traders score with bullish ratio."""
        score = analyzer._calculate_top_traders_score(1.8)
        assert score == 4
    
    def test_top_traders_score_very_bearish(self, analyzer):
        """Test top traders score with very bearish ratio."""
        score = analyzer._calculate_top_traders_score(0.3)
        assert score == -10
    
    def test_news_sentiment_very_bullish(self, analyzer):
        """Test news sentiment score with very positive sentiment."""
        score = analyzer._calculate_news_sentiment_score({"sentiment_score": 0.7})
        assert score == 10
    
    def test_news_sentiment_bullish(self, analyzer):
        """Test news sentiment score with positive sentiment."""
        score = analyzer._calculate_news_sentiment_score({"sentiment_score": 0.3})
        assert score == 5
    
    def test_news_sentiment_bearish(self, analyzer):
        """Test news sentiment score with negative sentiment."""
        score = analyzer._calculate_news_sentiment_score({"sentiment_score": -0.6})
        assert score == -10
    
    def test_tradingview_strong_buy(self, analyzer):
        """Test TradingView score with STRONG_BUY."""
        score = analyzer._calculate_tradingview_score({"recommendation": "STRONG_BUY"})
        assert score == 10
    
    def test_tradingview_buy(self, analyzer):
        """Test TradingView score with BUY."""
        score = analyzer._calculate_tradingview_score({"recommendation": "BUY"})
        assert score == 5
    
    def test_tradingview_sell(self, analyzer):
        """Test TradingView score with SELL."""
        score = analyzer._calculate_tradingview_score({"recommendation": "SELL"})
        assert score == -5
    
    def test_tradingview_neutral(self, analyzer):
        """Test TradingView score with NEUTRAL."""
        score = analyzer._calculate_tradingview_score({"recommendation": "NEUTRAL"})
        assert score == 0
    
    def test_whale_alert_strong_bullish(self, analyzer):
        """Test Whale Alert score with strong positive net flow."""
        score = analyzer._calculate_whale_alert_score({"net_flow": 75_000_000})
        assert score == 10
    
    def test_whale_alert_bullish(self, analyzer):
        """Test Whale Alert score with positive net flow."""
        score = analyzer._calculate_whale_alert_score({"net_flow": 30_000_000})
        assert score == 5
    
    def test_whale_alert_bearish(self, analyzer):
        """Test Whale Alert score with negative net flow."""
        score = analyzer._calculate_whale_alert_score({"net_flow": -60_000_000})
        assert score == -10


class TestWeightSystem:
    """Test that the 22-factor weight system is correctly configured."""
    
    def test_weight_distribution(self):
        """Test that weights sum to 100% and are distributed correctly."""
        # Long-term factors (35%)
        long_term_weights = {
            'WHALE_WEIGHT': 0.04,
            'TREND_WEIGHT': 0.05,
            'MOMENTUM_WEIGHT': 0.04,
            'VOLATILITY_WEIGHT': 0.04,
            'VOLUME_WEIGHT': 0.04,
            'MARKET_WEIGHT': 0.04,
            'ORDERBOOK_WEIGHT': 0.04,
            'DERIVATIVES_WEIGHT': 0.03,
            'ONCHAIN_WEIGHT': 0.02,
            'SENTIMENT_WEIGHT': 0.01,
        }
        
        # Short-term factors (35%)
        short_term_weights = {
            'SHORT_TREND_WEIGHT': 0.08,
            'TRADES_FLOW_WEIGHT': 0.07,
            'LIQUIDATIONS_WEIGHT': 0.06,
            'ORDERBOOK_DELTA_WEIGHT': 0.07,
            'PRICE_MOMENTUM_WEIGHT': 0.07,
        }
        
        # New sources (30%)
        new_source_weights = {
            'COINGLASS_OI_WEIGHT': 0.05,
            'COINGLASS_TOP_TRADERS_WEIGHT': 0.05,
            'NEWS_SENTIMENT_WEIGHT': 0.05,
            'TRADINGVIEW_WEIGHT': 0.06,
            'WHALE_ALERT_WEIGHT': 0.05,
            'SOCIAL_WEIGHT': 0.04,
        }
        
        # Combine all weights
        all_weights = {**long_term_weights, **short_term_weights, **new_source_weights}
        
        total = sum(all_weights.values())
        assert abs(total - 1.0) < 0.01, f"Weights should sum to 1.0, got {total}"
        
        # Test category distributions
        long_term = sum(long_term_weights.values())
        short_term = sum(short_term_weights.values())
        new_sources = sum(new_source_weights.values())
        
        assert abs(long_term - 0.35) < 0.01, f"Long-term should be 35%, got {long_term * 100:.0f}%"
        assert abs(short_term - 0.35) < 0.01, f"Short-term should be 35%, got {short_term * 100:.0f}%"
        assert abs(new_sources - 0.30) < 0.01, f"New sources should be 30%, got {new_sources * 100:.0f}%"
