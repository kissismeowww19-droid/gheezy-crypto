"""
Tests for Phase 3.3 Social Sentiment Analysis module.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestSocialSentimentAnalyzer:
    """Tests for SocialSentimentAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a SocialSentimentAnalyzer instance."""
        from signals.phase3.social_sentiment import SocialSentimentAnalyzer
        return SocialSentimentAnalyzer()
    
    @pytest.mark.asyncio
    async def test_get_reddit_sentiment_btc_success(self, analyzer):
        """Test successful Reddit sentiment fetch for BTC."""
        mock_response = {
            'data': {
                'children': [
                    {
                        'data': {
                            'title': 'Bitcoin to the moon! 🚀',
                            'selftext': 'Great breakout happening now',
                            'score': 100,
                            'num_comments': 50
                        }
                    },
                    {
                        'data': {
                            'title': 'BTC crash incoming',
                            'selftext': 'Bearish signs everywhere',
                            'score': 50,
                            'num_comments': 20
                        }
                    },
                    {
                        'data': {
                            'title': 'Neutral analysis',
                            'selftext': 'Market is sideways',
                            'score': 30,
                            'num_comments': 10
                        }
                    }
                ]
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_reddit_sentiment('BTC')
            
            assert result is not None
            assert 'bullish_ratio' in result
            assert 'bearish_ratio' in result
            assert 'posts_analyzed' in result
            assert 'verdict' in result
            assert 'score' in result
            assert result['posts_analyzed'] > 0
    
    @pytest.mark.asyncio
    async def test_get_reddit_sentiment_rate_limited(self, analyzer):
        """Test Reddit rate limit handling."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 429
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_reddit_sentiment('BTC')
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_reddit_sentiment_failure(self, analyzer):
        """Test Reddit fetch failure handling."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 404
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_reddit_sentiment('BTC')
            
            assert result is None
    
    def test_analyze_posts_bullish(self, analyzer):
        """Test _analyze_posts with bullish sentiment."""
        posts = [
            {
                'data': {
                    'title': 'Bitcoin bullish breakout! 🚀📈',
                    'selftext': 'Great news, price going to moon',
                    'score': 200,
                    'num_comments': 100
                }
            },
            {
                'data': {
                    'title': 'Buy the dip!',
                    'selftext': 'Time to accumulate',
                    'score': 150,
                    'num_comments': 75
                }
            },
        ]
        
        result = analyzer._analyze_posts(posts)
        
        assert result is not None
        assert result['bullish_score'] > 0
        assert result['posts_count'] == 2
        assert result['engagement'] > 0
    
    def test_analyze_posts_bearish(self, analyzer):
        """Test _analyze_posts with bearish sentiment."""
        posts = [
            {
                'data': {
                    'title': 'Market crash coming 📉',
                    'selftext': 'Sell everything, bearish trend',
                    'score': 180,
                    'num_comments': 90
                }
            },
            {
                'data': {
                    'title': 'Fear and panic in the market',
                    'selftext': 'Everything is dumping',
                    'score': 120,
                    'num_comments': 60
                }
            },
        ]
        
        result = analyzer._analyze_posts(posts)
        
        assert result is not None
        assert result['bearish_score'] > 0
        assert result['posts_count'] == 2
    
    def test_analyze_posts_mixed(self, analyzer):
        """Test _analyze_posts with mixed sentiment."""
        posts = [
            {
                'data': {
                    'title': 'Bullish on Bitcoin 🚀',
                    'selftext': 'Great breakout',
                    'score': 100,
                    'num_comments': 50
                }
            },
            {
                'data': {
                    'title': 'Bearish market crash',
                    'selftext': 'Sell now',
                    'score': 80,
                    'num_comments': 40
                }
            },
            {
                'data': {
                    'title': 'Neutral market analysis',
                    'selftext': 'Nothing happening',
                    'score': 50,
                    'num_comments': 25
                }
            }
        ]
        
        result = analyzer._analyze_posts(posts)
        
        assert result is not None
        assert result['bullish_score'] > 0
        assert result['bearish_score'] > 0
        assert result['posts_count'] == 3
    
    @pytest.mark.asyncio
    async def test_analyze_success(self, analyzer):
        """Test analyze method with successful sentiment fetch."""
        mock_sentiment = {
            'bullish_ratio': 0.65,
            'bearish_ratio': 0.35,
            'total_engagement': 5000,
            'posts_analyzed': 25,
            'verdict': 'bullish',
            'score': 8
        }
        
        with patch.object(analyzer, 'get_reddit_sentiment', return_value=mock_sentiment):
            result = await analyzer.analyze('BTC')
            
            assert result is not None
            assert result['score'] == 8
            assert result['verdict'] == 'bullish'
            assert result['bullish_ratio'] == 0.65
    
    @pytest.mark.asyncio
    async def test_analyze_no_data(self, analyzer):
        """Test analyze method when data fetch fails."""
        with patch.object(analyzer, 'get_reddit_sentiment', return_value=None):
            result = await analyzer.analyze('BTC')
            
            assert result is not None
            assert result['score'] == 0
            assert result['verdict'] == 'neutral'
            assert result['bullish_ratio'] is None
            assert result['posts_analyzed'] == 0
    
    @pytest.mark.asyncio
    async def test_verdict_bullish(self, analyzer):
        """Test verdict calculation for bullish scenario."""
        posts = []
        for i in range(25):
            # Create heavily bullish posts
            posts.append({
                'data': {
                    'title': f'Bitcoin moon rocket {i} 🚀',
                    'selftext': 'bull bull bull',
                    'score': 100,
                    'num_comments': 50
                }
            })
        
        mock_response = {'data': {'children': posts}}
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_reddit_sentiment('BTC')
            
            assert result is not None
            assert result['verdict'] in ['bullish', 'slightly_bullish']
            assert result['score'] > 0
    
    @pytest.mark.asyncio
    async def test_verdict_bearish(self, analyzer):
        """Test verdict calculation for bearish scenario."""
        posts = []
        for i in range(25):
            # Create heavily bearish posts
            posts.append({
                'data': {
                    'title': f'Bitcoin crash {i} 📉',
                    'selftext': 'bear bear bear dump',
                    'score': 100,
                    'num_comments': 50
                }
            })
        
        mock_response = {'data': {'children': posts}}
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_reddit_sentiment('BTC')
            
            assert result is not None
            assert result['verdict'] in ['bearish', 'slightly_bearish']
            assert result['score'] < 0


class TestAISignalsSentimentIntegration:
    """Tests for social sentiment integration in AISignalAnalyzer."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        return tracker
    
    @pytest.mark.asyncio
    async def test_get_sentiment_data_success(self, mock_whale_tracker):
        """Test get_sentiment_data method in AISignalAnalyzer."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        # Mock the sentiment analyzer
        mock_sentiment_result = {
            'score': 8,
            'verdict': 'bullish',
            'bullish_ratio': 0.70,
            'bearish_ratio': 0.30,
            'total_engagement': 10000,
            'posts_analyzed': 25
        }
        
        if analyzer.sentiment_analyzer:
            with patch.object(analyzer.sentiment_analyzer, 'analyze', return_value=mock_sentiment_result):
                result = await analyzer.get_sentiment_data('BTC')
                
                assert result is not None
                assert result['score'] == 8
                assert result['verdict'] == 'bullish'
                assert result['bullish_ratio'] == 0.70
    
    @pytest.mark.asyncio
    async def test_get_sentiment_data_no_analyzer(self, mock_whale_tracker):
        """Test get_sentiment_data when sentiment analyzer is not available."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        # Force sentiment_analyzer to None
        analyzer.sentiment_analyzer = None
        
        result = await analyzer.get_sentiment_data('BTC')
        
        assert result is not None
        assert result['score'] == 0
        assert result['verdict'] == 'neutral'
    
    @pytest.mark.asyncio
    async def test_get_sentiment_data_exception(self, mock_whale_tracker):
        """Test get_sentiment_data exception handling."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        if analyzer.sentiment_analyzer:
            with patch.object(analyzer.sentiment_analyzer, 'analyze', side_effect=Exception("Test error")):
                result = await analyzer.get_sentiment_data('BTC')
                
                assert result is not None
                assert result['score'] == 0
                assert result['verdict'] == 'neutral'
