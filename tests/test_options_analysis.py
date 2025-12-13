"""
Tests for Phase 3.2 Options Analysis module.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestOptionsAnalyzer:
    """Tests for OptionsAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an OptionsAnalyzer instance."""
        from signals.phase3.options_analysis import OptionsAnalyzer
        return OptionsAnalyzer()
    
    @pytest.mark.asyncio
    async def test_get_options_data_btc_success(self, analyzer):
        """Test successful options data fetch for BTC."""
        mock_response = {
            'result': [
                {'instrument_name': 'BTC-31DEC25-100000-C', 'open_interest': 1000},
                {'instrument_name': 'BTC-31DEC25-90000-C', 'open_interest': 1500},
                {'instrument_name': 'BTC-31DEC25-100000-P', 'open_interest': 2000},
                {'instrument_name': 'BTC-31DEC25-90000-P', 'open_interest': 2500},
            ]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_options_data('BTC')
            
            assert result is not None
            assert 'put_call_ratio' in result
            assert 'call_oi' in result
            assert 'put_oi' in result
            assert 'verdict' in result
            assert 'score' in result
            # call_oi = 2500 (1000+1500), put_oi = 4500 (2000+2500)
            # PCR = 4500 / 2500 = 1.8 -> bullish
            assert result['put_call_ratio'] > 1.0
    
    @pytest.mark.asyncio
    async def test_get_options_data_eth_success(self, analyzer):
        """Test successful options data fetch for ETH."""
        mock_response = {
            'result': [
                {'instrument_name': 'ETH-31DEC25-5000-C', 'open_interest': 3000},
                {'instrument_name': 'ETH-31DEC25-4500-C', 'open_interest': 2000},
                {'instrument_name': 'ETH-31DEC25-5000-P', 'open_interest': 1000},
                {'instrument_name': 'ETH-31DEC25-4500-P', 'open_interest': 500},
            ]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_options_data('ETH')
            
            assert result is not None
            assert 'put_call_ratio' in result
            # call_oi = 5000 (3000+2000), put_oi = 1500 (1000+500)
            # PCR = 1500 / 5000 = 0.3 -> bearish (low PCR means many calls)
            assert result['put_call_ratio'] < 1.0
    
    @pytest.mark.asyncio
    async def test_get_options_data_unsupported_symbol(self, analyzer):
        """Test options data fetch for unsupported symbol (e.g., TON)."""
        result = await analyzer.get_options_data('TON')
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_options_data_failure(self, analyzer):
        """Test options data fetch failure handling."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 404
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            result = await analyzer.get_options_data('BTC')
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_analyze_options_high_pcr_bullish(self, analyzer):
        """Test _analyze_options with high PCR (contrarian bullish)."""
        options = [
            {'instrument_name': 'BTC-31DEC25-100000-C', 'open_interest': 1000},
            {'instrument_name': 'BTC-31DEC25-100000-P', 'open_interest': 1500},
        ]
        
        result = analyzer._analyze_options(options, 'BTC')
        
        assert result is not None
        assert result['put_call_ratio'] == 1.5  # 1500 / 1000
        assert result['verdict'] == 'slightly_bullish'
        assert result['score'] == 5
    
    @pytest.mark.asyncio
    async def test_analyze_options_very_high_pcr(self, analyzer):
        """Test _analyze_options with very high PCR (strong contrarian bullish)."""
        options = [
            {'instrument_name': 'BTC-31DEC25-100000-C', 'open_interest': 1000},
            {'instrument_name': 'BTC-31DEC25-100000-P', 'open_interest': 1400},
        ]
        
        result = analyzer._analyze_options(options, 'BTC')
        
        assert result is not None
        assert result['put_call_ratio'] == 1.4  # 1400 / 1000
        assert result['verdict'] == 'bullish'
        assert result['score'] == 10
    
    @pytest.mark.asyncio
    async def test_analyze_options_low_pcr_bearish(self, analyzer):
        """Test _analyze_options with low PCR (contrarian bearish)."""
        options = [
            {'instrument_name': 'BTC-31DEC25-100000-C', 'open_interest': 1000},
            {'instrument_name': 'BTC-31DEC25-100000-P', 'open_interest': 600},
        ]
        
        result = analyzer._analyze_options(options, 'BTC')
        
        assert result is not None
        assert result['put_call_ratio'] == 0.6  # 600 / 1000
        assert result['verdict'] == 'bearish'
        assert result['score'] == -10
    
    @pytest.mark.asyncio
    async def test_analyze_options_neutral_pcr(self, analyzer):
        """Test _analyze_options with neutral PCR."""
        options = [
            {'instrument_name': 'BTC-31DEC25-100000-C', 'open_interest': 1000},
            {'instrument_name': 'BTC-31DEC25-100000-P', 'open_interest': 1000},
        ]
        
        result = analyzer._analyze_options(options, 'BTC')
        
        assert result is not None
        assert result['put_call_ratio'] == 1.0  # 1000 / 1000
        assert result['verdict'] == 'neutral'
        assert result['score'] == 0
    
    @pytest.mark.asyncio
    async def test_analyze_btc_success(self, analyzer):
        """Test analyze method for BTC with successful data fetch."""
        mock_data = {
            'put_call_ratio': 1.25,
            'call_oi': 10000,
            'put_oi': 12500,
            'total_options': 50,
            'verdict': 'slightly_bullish',
            'interpretation': 'Умеренно высокий PCR',
            'score': 5
        }
        
        with patch.object(analyzer, 'get_options_data', return_value=mock_data):
            result = await analyzer.analyze('BTC')
            
            assert result is not None
            assert result['score'] == 5
            assert result['verdict'] == 'slightly_bullish'
            assert result['put_call_ratio'] == 1.25
    
    @pytest.mark.asyncio
    async def test_analyze_no_data(self, analyzer):
        """Test analyze method when data fetch fails."""
        with patch.object(analyzer, 'get_options_data', return_value=None):
            result = await analyzer.analyze('BTC')
            
            assert result is not None
            assert result['score'] == 0
            assert result['verdict'] == 'neutral'
            assert result['interpretation'] == 'Данные недоступны'
            assert result['put_call_ratio'] is None


class TestAISignalsOptionsIntegration:
    """Tests for options analysis integration in AISignalAnalyzer."""
    
    @pytest.fixture
    def mock_whale_tracker(self):
        """Create a mock whale tracker."""
        tracker = Mock()
        tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        return tracker
    
    @pytest.mark.asyncio
    async def test_get_options_data_success(self, mock_whale_tracker):
        """Test get_options_data method in AISignalAnalyzer for BTC."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        # Mock the options analyzer
        mock_options_result = {
            'score': 10,
            'verdict': 'bullish',
            'put_call_ratio': 1.35,
            'interpretation': 'Высокий PCR — толпа в путах (contrarian bullish)',
            'call_oi': 10000,
            'put_oi': 13500,
            'total_options': 100
        }
        
        if analyzer.options_analyzer:
            with patch.object(analyzer.options_analyzer, 'analyze', return_value=mock_options_result):
                result = await analyzer.get_options_data('BTC')
                
                assert result is not None
                assert result['score'] == 10
                assert result['verdict'] == 'bullish'
                assert result['put_call_ratio'] == 1.35
    
    @pytest.mark.asyncio
    async def test_get_options_data_unsupported_symbol(self, mock_whale_tracker):
        """Test get_options_data for unsupported symbol (e.g., TON)."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        result = await analyzer.get_options_data('TON')
        
        assert result is not None
        assert result['score'] == 0
        assert result['verdict'] == 'neutral'
    
    @pytest.mark.asyncio
    async def test_get_options_data_no_analyzer(self, mock_whale_tracker):
        """Test get_options_data when options analyzer is not available."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        # Force options_analyzer to None
        analyzer.options_analyzer = None
        
        result = await analyzer.get_options_data('BTC')
        
        assert result is not None
        assert result['score'] == 0
        assert result['verdict'] == 'neutral'
    
    @pytest.mark.asyncio
    async def test_get_options_data_exception(self, mock_whale_tracker):
        """Test get_options_data exception handling."""
        from signals.ai_signals import AISignalAnalyzer
        
        analyzer = AISignalAnalyzer(mock_whale_tracker)
        
        if analyzer.options_analyzer:
            with patch.object(analyzer.options_analyzer, 'analyze', side_effect=Exception("Test error")):
                result = await analyzer.get_options_data('BTC')
                
                assert result is not None
                assert result['score'] == 0
                assert result['verdict'] == 'neutral'
