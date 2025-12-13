"""
Tests for Phase 3.1 Macro Analysis module.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestMacroAnalyzer:
    """Tests for MacroAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a MacroAnalyzer instance."""
        # Import here to avoid triggering full module tree
        from signals.phase3.macro_analysis import MacroAnalyzer
        return MacroAnalyzer()
    
    @pytest.mark.asyncio
    async def test_get_dxy_data_success(self, analyzer):
        """Test successful DXY data fetch."""
        mock_response = {
            'chart': {
                'result': [{
                    'indicators': {
                        'quote': [{
                            'close': [105.0, 105.5, 106.0, 106.5]
                        }]
                    }
                }]
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_dxy_data()
            
            assert result is not None
            assert 'value' in result
            assert 'change_24h' in result
            assert 'trend' in result
    
    @pytest.mark.asyncio
    async def test_get_dxy_data_failure(self, analyzer):
        """Test DXY data fetch failure handling."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 404
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_dxy_data()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_sp500_data_success(self, analyzer):
        """Test successful S&P500 data fetch."""
        mock_response = {
            'chart': {
                'result': [{
                    'indicators': {
                        'quote': [{
                            'close': [6000.0, 6010.0, 6020.0, 6050.0]
                        }]
                    }
                }]
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_sp500_data()
            
            assert result is not None
            assert 'value' in result
            assert 'change_24h' in result
            assert 'trend' in result
    
    @pytest.mark.asyncio
    async def test_get_gold_data_success(self, analyzer):
        """Test successful Gold data fetch."""
        mock_response = {
            'chart': {
                'result': [{
                    'indicators': {
                        'quote': [{
                            'close': [2640.0, 2645.0, 2650.0]
                        }]
                    }
                }]
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_gold_data()
            
            assert result is not None
            assert 'value' in result
            assert 'change_24h' in result
            assert 'trend' in result
    
    @pytest.mark.asyncio
    async def test_analyze_bullish_scenario(self, analyzer):
        """Test analyze method with bullish macro scenario."""
        # Mock DXY falling (bearish for DXY = bullish for crypto)
        mock_dxy = {'value': 105.0, 'change_24h': -0.5, 'trend': 'bearish'}
        # Mock S&P500 rising (bullish for crypto)
        mock_sp500 = {'value': 6050.0, 'change_24h': 0.8, 'trend': 'bullish'}
        # Mock Gold rising (slightly bullish)
        mock_gold = {'value': 2650.0, 'change_24h': 0.4, 'trend': 'bullish'}
        
        with patch.object(analyzer, 'get_dxy_data', return_value=mock_dxy), \
             patch.object(analyzer, 'get_sp500_data', return_value=mock_sp500), \
             patch.object(analyzer, 'get_gold_data', return_value=mock_gold):
            
            result = await analyzer.analyze()
            
            assert result is not None
            assert 'score' in result
            assert 'verdict' in result
            assert 'factors' in result
            # Score should be positive: +8 (DXY bearish) + 6 (S&P bullish) + 3 (Gold bullish) = 17, capped at 15
            assert result['score'] == 15
            assert result['verdict'] == 'bullish'
            assert len(result['factors']) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_bearish_scenario(self, analyzer):
        """Test analyze method with bearish macro scenario."""
        # Mock DXY rising (bullish for DXY = bearish for crypto)
        mock_dxy = {'value': 107.0, 'change_24h': 0.6, 'trend': 'bullish'}
        # Mock S&P500 falling (bearish for crypto)
        mock_sp500 = {'value': 6000.0, 'change_24h': -0.7, 'trend': 'bearish'}
        # Mock Gold falling
        mock_gold = {'value': 2600.0, 'change_24h': -0.5, 'trend': 'bearish'}
        
        with patch.object(analyzer, 'get_dxy_data', return_value=mock_dxy), \
             patch.object(analyzer, 'get_sp500_data', return_value=mock_sp500), \
             patch.object(analyzer, 'get_gold_data', return_value=mock_gold):
            
            result = await analyzer.analyze()
            
            assert result is not None
            assert result['score'] < 0
            # Score: -8 (DXY bullish) - 6 (S&P bearish) - 3 (Gold bearish) = -17, capped at -15
            assert result['score'] == -15
            assert result['verdict'] == 'bearish'
    
    @pytest.mark.asyncio
    async def test_analyze_neutral_scenario(self, analyzer):
        """Test analyze method with neutral macro scenario."""
        # Mock all neutral trends
        mock_dxy = {'value': 106.0, 'change_24h': 0.1, 'trend': 'neutral'}
        mock_sp500 = {'value': 6020.0, 'change_24h': 0.2, 'trend': 'neutral'}
        mock_gold = {'value': 2640.0, 'change_24h': 0.0, 'trend': 'neutral'}
        
        with patch.object(analyzer, 'get_dxy_data', return_value=mock_dxy), \
             patch.object(analyzer, 'get_sp500_data', return_value=mock_sp500), \
             patch.object(analyzer, 'get_gold_data', return_value=mock_gold):
            
            result = await analyzer.analyze()
            
            assert result is not None
            assert result['score'] == 0
            assert result['verdict'] == 'neutral'
    
    @pytest.mark.asyncio
    async def test_analyze_partial_data(self, analyzer):
        """Test analyze method with partial data (some sources unavailable)."""
        # Only DXY available
        mock_dxy = {'value': 105.0, 'change_24h': -0.5, 'trend': 'bearish'}
        
        with patch.object(analyzer, 'get_dxy_data', return_value=mock_dxy), \
             patch.object(analyzer, 'get_sp500_data', return_value=None), \
             patch.object(analyzer, 'get_gold_data', return_value=None):
            
            result = await analyzer.analyze()
            
            assert result is not None
            assert result['score'] == 8  # Only DXY contribution
            assert result['verdict'] == 'bullish'
            assert result['dxy'] is not None
            assert result['sp500'] is None
            assert result['gold'] is None
    
    @pytest.mark.asyncio
    async def test_analyze_no_data(self, analyzer):
        """Test analyze method when all data sources fail."""
        with patch.object(analyzer, 'get_dxy_data', return_value=None), \
             patch.object(analyzer, 'get_sp500_data', return_value=None), \
             patch.object(analyzer, 'get_gold_data', return_value=None):
            
            result = await analyzer.analyze()
            
            assert result is not None
            assert result['score'] == 0
            assert result['verdict'] == 'neutral'
            assert len(result['factors']) == 0


class TestAISignalsMacroIntegration:
    """Tests for macro analysis integration in AISignalAnalyzer."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        return tracker
    
    @pytest.mark.asyncio
    async def test_get_macro_data_success(self, mock_whale_tracker):
        """Test get_macro_data method in AISignalAnalyzer."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        # Mock the macro analyzer
        mock_macro_result = {
            'score': 10,
            'verdict': 'bullish',
            'factors': ['DXY ↓-0.35% (бычье)', 'S&P500 ↑+0.82% (бычье)'],
            'dxy': {'value': 106.5, 'change_24h': -0.35, 'trend': 'bearish'},
            'sp500': {'value': 6051.0, 'change_24h': 0.82, 'trend': 'bullish'},
            'gold': {'value': 2650.0, 'change_24h': 0.15, 'trend': 'neutral'}
        }
        
        if analyzer.macro_analyzer:
            with patch.object(analyzer.macro_analyzer, 'analyze', return_value=mock_macro_result):
                result = await analyzer.get_macro_data()
                
                assert result is not None
                assert result['score'] == 10
                assert result['verdict'] == 'bullish'
    
    @pytest.mark.asyncio
    async def test_get_macro_data_no_analyzer(self, mock_whale_tracker):
        """Test get_macro_data when macro analyzer is not available."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        # Force macro_analyzer to None
        analyzer.macro_analyzer = None
        
        result = await analyzer.get_macro_data()
        
        assert result is not None
        assert result['score'] == 0
        assert result['verdict'] == 'neutral'
    
    @pytest.mark.asyncio
    async def test_get_macro_data_exception(self, mock_whale_tracker):
        """Test get_macro_data exception handling."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        if analyzer.macro_analyzer:
            with patch.object(analyzer.macro_analyzer, 'analyze', side_effect=Exception("Test error")):
                result = await analyzer.get_macro_data()
                
                assert result is not None
                assert result['score'] == 0
                assert result['verdict'] == 'neutral'
