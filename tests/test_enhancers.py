"""
Tests for Enhancers module.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from enhancers.order_flow import OrderFlowEnhancer
from enhancers.volume_profile import VolumeProfileEnhancer
from enhancers.multi_exchange import MultiExchangeEnhancer
from enhancers.enhancer_manager import EnhancerManager


class TestOrderFlowEnhancer:
    """Tests for OrderFlowEnhancer class."""
    
    @pytest.fixture
    def order_flow(self):
        """Create an OrderFlowEnhancer instance."""
        return OrderFlowEnhancer()
    
    @pytest.mark.asyncio
    async def test_get_score_no_data(self, order_flow):
        """Test get_score when no trades data available."""
        with patch.object(order_flow, '_get_recent_trades', return_value=None):
            score = await order_flow.get_score("BTC")
            assert score == 0.0
    
    @pytest.mark.asyncio
    async def test_get_score_with_bullish_cvd(self, order_flow):
        """Test get_score with bullish CVD (more buys than sells)."""
        # Mock trades with more buys than sells
        mock_trades = [
            {'q': '1.0', 'p': '50000', 'm': False},  # Buy
            {'q': '0.5', 'p': '50000', 'm': False},  # Buy
            {'q': '0.3', 'p': '50000', 'm': True},   # Sell
        ]
        
        with patch.object(order_flow, '_get_recent_trades', return_value=mock_trades):
            score = await order_flow.get_score("BTC")
            assert score > 0  # Should be bullish
    
    @pytest.mark.asyncio
    async def test_get_score_with_bearish_cvd(self, order_flow):
        """Test get_score with bearish CVD (more sells than buys)."""
        # Mock trades with more sells than buys
        mock_trades = [
            {'q': '1.0', 'p': '50000', 'm': True},   # Sell
            {'q': '0.8', 'p': '50000', 'm': True},   # Sell
            {'q': '0.2', 'p': '50000', 'm': False},  # Buy
        ]
        
        with patch.object(order_flow, '_get_recent_trades', return_value=mock_trades):
            score = await order_flow.get_score("BTC")
            assert score < 0  # Should be bearish
    
    @pytest.mark.asyncio
    async def test_get_score_with_large_orders(self, order_flow):
        """Test get_score with large orders (> $100K)."""
        # Mock trades with large orders
        mock_trades = [
            {'q': '3.0', 'p': '50000', 'm': False},  # Large buy ($150K)
            {'q': '0.5', 'p': '50000', 'm': True},   # Small sell
        ]
        
        with patch.object(order_flow, '_get_recent_trades', return_value=mock_trades):
            score = await order_flow.get_score("BTC")
            assert score > 0  # Should be bullish due to large buy order
    
    @pytest.mark.asyncio
    async def test_get_cvd(self, order_flow):
        """Test get_cvd method."""
        mock_trades = [
            {'q': '1.0', 'p': '50000', 'm': False},  # Buy: $50K
            {'q': '0.5', 'p': '50000', 'm': True},   # Sell: $25K
        ]
        
        with patch.object(order_flow, '_get_recent_trades', return_value=mock_trades):
            cvd = await order_flow.get_cvd("BTC")
            assert cvd == 25000.0  # $50K - $25K = $25K
    
    def test_calculate_cvd(self, order_flow):
        """Test _calculate_cvd method."""
        trades = [
            {'q': '1.0', 'p': '50000', 'm': False},  # Buy
            {'q': '0.5', 'p': '50000', 'm': True},   # Sell
        ]
        
        cvd = order_flow._calculate_cvd(trades)
        assert cvd == 25000.0
    
    def test_detect_large_orders(self, order_flow):
        """Test _detect_large_orders method."""
        trades = [
            {'q': '3.0', 'p': '50000', 'm': False},  # Large buy ($150K)
            {'q': '2.5', 'p': '50000', 'm': True},   # Large sell ($125K)
            {'q': '0.5', 'p': '50000', 'm': False},  # Small buy ($25K)
        ]
        
        result = order_flow._detect_large_orders(trades)
        
        assert result['buy_count'] == 1
        assert result['sell_count'] == 1
        assert result['buy_volume'] == 150000.0
        assert result['sell_volume'] == 125000.0
    
    def test_calculate_imbalance(self, order_flow):
        """Test _calculate_imbalance method."""
        trades = [
            {'q': '1.0', 'p': '50000', 'm': False},  # Buy: $50K
            {'q': '0.5', 'p': '50000', 'm': True},   # Sell: $25K
        ]
        
        imbalance = order_flow._calculate_imbalance(trades)
        
        # imbalance = (50000 - 25000) / 75000 = 0.333...
        assert 0.3 < imbalance < 0.4


class TestVolumeProfileEnhancer:
    """Tests for VolumeProfileEnhancer class."""
    
    @pytest.fixture
    def volume_profile(self):
        """Create a VolumeProfileEnhancer instance."""
        return VolumeProfileEnhancer()
    
    @pytest.mark.asyncio
    async def test_get_score_no_price(self, volume_profile):
        """Test get_score when current_price not provided."""
        score = await volume_profile.get_score("BTC")
        assert score == 0.0
    
    @pytest.mark.asyncio
    async def test_get_score_no_levels(self, volume_profile):
        """Test get_score when no levels available."""
        with patch.object(volume_profile, 'get_levels', return_value={}):
            score = await volume_profile.get_score("BTC", current_price=50000.0)
            assert score == 0.0
    
    @pytest.mark.asyncio
    async def test_get_score_price_below_poc(self, volume_profile):
        """Test get_score when price is below POC."""
        mock_levels = {
            'poc': 51000.0,
            'vah': 52000.0,
            'val': 49000.0
        }
        
        with patch.object(volume_profile, 'get_levels', return_value=mock_levels):
            score = await volume_profile.get_score("BTC", current_price=50000.0)
            # Price below POC should give positive score (expected to return to POC)
            assert score > 0
    
    @pytest.mark.asyncio
    async def test_get_score_price_above_poc(self, volume_profile):
        """Test get_score when price is above POC."""
        mock_levels = {
            'poc': 49000.0,
            'vah': 52000.0,
            'val': 47000.0
        }
        
        with patch.object(volume_profile, 'get_levels', return_value=mock_levels):
            score = await volume_profile.get_score("BTC", current_price=50000.0)
            # Price above POC should give negative score (expected to move down)
            assert score < 0
    
    @pytest.mark.asyncio
    async def test_get_levels(self, volume_profile):
        """Test get_levels method."""
        # Mock OHLCV data
        mock_ohlcv = [
            {'timestamp': 1, 'open': 49000, 'high': 50000, 'low': 48000, 'close': 49500, 'volume': 100},
            {'timestamp': 2, 'open': 49500, 'high': 51000, 'low': 49000, 'close': 50500, 'volume': 150},
            {'timestamp': 3, 'open': 50500, 'high': 52000, 'low': 50000, 'close': 51000, 'volume': 120},
        ]
        
        with patch.object(volume_profile, '_get_ohlcv', return_value=mock_ohlcv):
            levels = await volume_profile.get_levels("BTC")
            
            assert 'poc' in levels
            assert 'vah' in levels
            assert 'val' in levels
            assert 'lvn' in levels
    
    def test_calculate_volume_profile(self, volume_profile):
        """Test _calculate_volume_profile method."""
        ohlcv_data = [
            {'timestamp': 1, 'open': 49000, 'high': 50000, 'low': 48000, 'close': 49500, 'volume': 100},
            {'timestamp': 2, 'open': 49500, 'high': 51000, 'low': 49000, 'close': 50500, 'volume': 150},
        ]
        
        profile = volume_profile._calculate_volume_profile(ohlcv_data)
        
        assert isinstance(profile, dict)
        assert len(profile) > 0
        # All values should be non-negative
        assert all(v >= 0 for v in profile.values())
    
    def test_calculate_poc(self, volume_profile):
        """Test _calculate_poc method."""
        profile = {
            48000: 100.0,
            49000: 250.0,  # POC
            50000: 150.0,
            51000: 80.0,
        }
        
        poc = volume_profile._calculate_poc(profile)
        assert poc == 49000  # Should be the level with highest volume
    
    def test_calculate_value_area(self, volume_profile):
        """Test _calculate_value_area method."""
        profile = {
            48000: 100.0,
            49000: 250.0,  # POC
            50000: 150.0,
            51000: 80.0,
        }
        
        vah, val = volume_profile._calculate_value_area(profile, poc=49000)
        
        assert vah is not None
        assert val is not None
        assert vah > val  # VAH should be higher than VAL


class TestMultiExchangeEnhancer:
    """Tests for MultiExchangeEnhancer class."""
    
    @pytest.fixture
    def multi_exchange(self):
        """Create a MultiExchangeEnhancer instance."""
        return MultiExchangeEnhancer()
    
    @pytest.mark.asyncio
    async def test_get_score_no_data(self, multi_exchange):
        """Test get_score when no exchange data available."""
        with patch.object(multi_exchange, '_get_multi_exchange_data', return_value={}):
            score = await multi_exchange.get_score("BTC")
            assert score == 0.0
    
    @pytest.mark.asyncio
    async def test_get_score_binance_leads_up(self, multi_exchange):
        """Test get_score when Binance price is higher."""
        mock_data = {
            'Binance': {'price': 50100.0, 'volume': 1000.0},
            'Bybit': {'price': 50000.0, 'volume': 800.0},
            'OKX': {'price': 49950.0, 'volume': 700.0},
        }
        
        with patch.object(multi_exchange, '_get_multi_exchange_data', return_value=mock_data):
            score = await multi_exchange.get_score("BTC")
            assert score > 0  # Binance leading up should be positive
    
    @pytest.mark.asyncio
    async def test_get_score_binance_leads_down(self, multi_exchange):
        """Test get_score when Binance price is lower."""
        mock_data = {
            'Binance': {'price': 49900.0, 'volume': 1000.0},
            'Bybit': {'price': 50000.0, 'volume': 800.0},
            'OKX': {'price': 50050.0, 'volume': 700.0},
        }
        
        with patch.object(multi_exchange, '_get_multi_exchange_data', return_value=mock_data):
            score = await multi_exchange.get_score("BTC")
            assert score < 0  # Binance leading down should be negative
    
    @pytest.mark.asyncio
    async def test_get_leader(self, multi_exchange):
        """Test get_leader method."""
        mock_data = {
            'Binance': {'price': 50100.0, 'volume': 1000.0},
            'Bybit': {'price': 50000.0, 'volume': 800.0},
            'OKX': {'price': 49950.0, 'volume': 700.0},
        }
        
        with patch.object(multi_exchange, '_get_multi_exchange_data', return_value=mock_data):
            leader = await multi_exchange.get_leader("BTC")
            assert leader == "Binance"  # Binance has highest price
    
    def test_calculate_price_delta_score(self, multi_exchange):
        """Test _calculate_price_delta_score method."""
        exchange_data = {
            'Binance': {'price': 50100.0, 'volume': 1000.0},
            'Bybit': {'price': 50000.0, 'volume': 800.0},
            'OKX': {'price': 49900.0, 'volume': 700.0},
        }
        
        score = multi_exchange._calculate_price_delta_score(exchange_data)
        assert score > 0  # Binance price higher should give positive score
    
    def test_calculate_volume_score(self, multi_exchange):
        """Test _calculate_volume_score method."""
        exchange_data = {
            'Binance': {'price': 50000.0, 'volume': 2000.0},  # 60% of total
            'Bybit': {'price': 50000.0, 'volume': 800.0},
            'OKX': {'price': 50000.0, 'volume': 500.0},
        }
        
        score = multi_exchange._calculate_volume_score(exchange_data)
        assert score > 0  # Binance has > 50% volume share


class TestEnhancerManager:
    """Tests for EnhancerManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create an EnhancerManager instance."""
        return EnhancerManager()
    
    @pytest.mark.asyncio
    async def test_get_total_score(self, manager):
        """Test get_total_score method."""
        # Mock all enhancers
        with patch.object(manager.order_flow, 'get_score', return_value=5.0), \
             patch.object(manager.volume_profile, 'get_score', return_value=3.0), \
             patch.object(manager.multi_exchange, 'get_score', return_value=2.0):
            
            total = await manager.get_total_score("BTC", 50000.0)
            assert total == 10.0  # 5 + 3 + 2
    
    @pytest.mark.asyncio
    async def test_get_total_score_with_failures(self, manager):
        """Test get_total_score when some enhancers fail."""
        # Mock order flow to fail, others succeed
        with patch.object(manager.order_flow, 'get_score', side_effect=Exception("API Error")), \
             patch.object(manager.volume_profile, 'get_score', return_value=3.0), \
             patch.object(manager.multi_exchange, 'get_score', return_value=2.0):
            
            total = await manager.get_total_score("BTC", 50000.0)
            assert total == 5.0  # 0 (failed) + 3 + 2
    
    @pytest.mark.asyncio
    async def test_get_total_score_all_fail(self, manager):
        """Test get_total_score when all enhancers fail."""
        # Mock all enhancers to fail
        with patch.object(manager.order_flow, 'get_score', side_effect=Exception("Error")), \
             patch.object(manager.volume_profile, 'get_score', side_effect=Exception("Error")), \
             patch.object(manager.multi_exchange, 'get_score', side_effect=Exception("Error")):
            
            total = await manager.get_total_score("BTC", 50000.0)
            assert total == 0.0  # All failed, should return 0
    
    @pytest.mark.asyncio
    async def test_get_extra_data(self, manager):
        """Test get_extra_data method."""
        mock_levels = {'poc': 50000.0, 'vah': 51000.0, 'val': 49000.0}
        
        with patch.object(manager.volume_profile, 'get_levels', return_value=mock_levels), \
             patch.object(manager.multi_exchange, 'get_leader', return_value="Binance"), \
             patch.object(manager.order_flow, 'get_cvd', return_value=1000000.0):
            
            extra_data = await manager.get_extra_data("BTC")
            
            assert 'volume_profile_levels' in extra_data
            assert 'exchange_leader' in extra_data
            assert 'order_flow_cvd' in extra_data
            assert extra_data['exchange_leader'] == "Binance"
            assert extra_data['order_flow_cvd'] == 1000000.0
    
    @pytest.mark.asyncio
    async def test_get_extra_data_with_failures(self, manager):
        """Test get_extra_data when some methods fail."""
        with patch.object(manager.volume_profile, 'get_levels', side_effect=Exception("Error")), \
             patch.object(manager.multi_exchange, 'get_leader', return_value="Binance"), \
             patch.object(manager.order_flow, 'get_cvd', return_value=1000000.0):
            
            extra_data = await manager.get_extra_data("BTC")
            
            # volume_profile_levels should be empty dict due to failure
            assert extra_data['volume_profile_levels'] == {}
            # Others should still work
            assert extra_data['exchange_leader'] == "Binance"
            assert extra_data['order_flow_cvd'] == 1000000.0


class TestEnhancersIntegration:
    """Integration tests for enhancers with AI signals."""
    
    @pytest.mark.asyncio
    async def test_enhancers_integration_with_ai_signals(self):
        """Test that enhancers integrate correctly with AI signals."""
        # This is a placeholder for integration tests with actual AI signal analyzer
        # In a real scenario, you would test the full integration
        pass
