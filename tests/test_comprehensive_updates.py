"""
Tests for comprehensive updates: Solana API integration, Ethereum improvements, and AI signals.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestSolanaAPIIntegration:
    """Tests for Solana API integration with multiple sources."""
    
    def test_api_urls_configured(self):
        """Test that all new API URLs are properly configured."""
        # Import inside test to avoid loading issues
        from whale.solana import HELIUS_API_URL, JUPITER_API_URL, SOLANA_TRACKER_API_URL
        
        assert HELIUS_API_URL == "https://api.helius.xyz/v0"
        assert JUPITER_API_URL == "https://api.jup.ag"
        assert SOLANA_TRACKER_API_URL == "https://data.solanatracker.io"
    
    def test_solana_tracker_has_new_methods(self):
        """Test that SolanaTracker has new API methods."""
        from whale.solana import SolanaTracker
        
        tracker = SolanaTracker()
        
        # Check new methods exist
        assert hasattr(tracker, '_get_from_helius')
        assert callable(getattr(tracker, '_get_from_helius'))
        
        assert hasattr(tracker, '_get_from_jupiter')
        assert callable(getattr(tracker, '_get_from_jupiter'))
        
        assert hasattr(tracker, '_get_from_solana_tracker')
        assert callable(getattr(tracker, '_get_from_solana_tracker'))
    
    @pytest.mark.asyncio
    async def test_fallback_priority_order(self):
        """Test that get_large_transactions uses correct fallback priority."""
        from whale.solana import SolanaTracker
        
        tracker = SolanaTracker()
        
        with patch.object(tracker, '_get_from_helius', new_callable=AsyncMock) as mock_helius, \
             patch.object(tracker, '_get_from_jupiter', new_callable=AsyncMock) as mock_jupiter, \
             patch.object(tracker, '_get_from_solana_tracker', new_callable=AsyncMock) as mock_solana_tracker, \
             patch.object(tracker, '_get_from_solscan', new_callable=AsyncMock) as mock_solscan, \
             patch.object(tracker, '_get_from_rpc', new_callable=AsyncMock) as mock_rpc, \
             patch.object(tracker, '_update_sol_price', new_callable=AsyncMock):
            
            # All sources return empty - should call all in order
            mock_helius.return_value = []
            mock_jupiter.return_value = []
            mock_solana_tracker.return_value = []
            mock_solscan.return_value = []
            mock_rpc.return_value = []
            
            result = await tracker.get_large_transactions(limit=10)
            
            # Verify all were called in correct order
            mock_helius.assert_called_once()
            mock_jupiter.assert_called_once()
            mock_solana_tracker.assert_called_once()
            mock_solscan.assert_called_once()
            mock_rpc.assert_called_once()
            assert result == []
    
    @pytest.mark.asyncio
    async def test_helius_success_skips_other_sources(self):
        """Test that if Helius succeeds, other sources are not called."""
        from whale.solana import SolanaTracker
        
        tracker = SolanaTracker()
        
        with patch.object(tracker, '_get_from_helius', new_callable=AsyncMock) as mock_helius, \
             patch.object(tracker, '_get_from_jupiter', new_callable=AsyncMock) as mock_jupiter, \
             patch.object(tracker, '_get_from_solana_tracker', new_callable=AsyncMock) as mock_solana_tracker, \
             patch.object(tracker, '_update_sol_price', new_callable=AsyncMock):
            
            # Helius returns data
            mock_tx = Mock()
            mock_tx.tx_hash = "test_hash"
            mock_helius.return_value = [mock_tx]
            
            result = await tracker.get_large_transactions(limit=10)
            
            # Verify only Helius was called
            mock_helius.assert_called_once()
            mock_jupiter.assert_not_called()
            mock_solana_tracker.assert_not_called()
            assert len(result) == 1


class TestEthereumImprovements:
    """Tests for Ethereum tracker improvements."""
    
    def test_transaction_type_enum_exists(self):
        """Test that TransactionType enum is properly defined."""
        from whale.ethereum import TransactionType
        
        assert hasattr(TransactionType, 'DEPOSIT')
        assert hasattr(TransactionType, 'WITHDRAWAL')
        assert hasattr(TransactionType, 'EXCHANGE_TRANSFER')
        assert hasattr(TransactionType, 'WHALE_TRANSFER')
        assert hasattr(TransactionType, 'DEX_SWAP')
        assert hasattr(TransactionType, 'CONTRACT_INTERACTION')
        assert hasattr(TransactionType, 'NFT_TRANSFER')
        assert hasattr(TransactionType, 'UNKNOWN')
    
    def test_extended_exchange_addresses(self):
        """Test that new exchange addresses are added to TRACKED_EXCHANGE_ADDRESSES."""
        from whale.ethereum import TRACKED_EXCHANGE_ADDRESSES
        
        # Check for new HTX addresses
        assert "0x1062a747393198f70f71ec65a582423dba7e5ab3" in TRACKED_EXCHANGE_ADDRESSES
        assert "0xe93381fb4c4f14bda253907b18fad305d799241a" in TRACKED_EXCHANGE_ADDRESSES
        
        # Check for Crypto.com addresses
        assert "0x6262998ced04146fa42253a5c0af90ca02dfd2a3" in TRACKED_EXCHANGE_ADDRESSES
        assert "0x46340b20830761efd32832a74d7169b29feb9758" in TRACKED_EXCHANGE_ADDRESSES
        
        # Check for MEXC address
        assert "0x75e89d5979e4f6fba9f97c104c2f0afb3f1dcb88" in TRACKED_EXCHANGE_ADDRESSES
        
        # Check for Gate.io addresses
        assert "0x0d0707963952f2fba59dd06f2b425ace40b492fe" in TRACKED_EXCHANGE_ADDRESSES
        assert "0x1c4b70a3968436b9a0a9cf5205c787eb81bb558c" in TRACKED_EXCHANGE_ADDRESSES
        
        # Check for Bitget addresses
        assert "0x97b9d2102a9a65a26e1ee82d59e42d1b73b68689" in TRACKED_EXCHANGE_ADDRESSES
        assert "0x5bdf85216ec1e38d6458c870992a69e38e03f7ef" in TRACKED_EXCHANGE_ADDRESSES
        
        # Verify total count increased
        assert len(TRACKED_EXCHANGE_ADDRESSES) >= 40
    
    def test_ethereum_tracker_has_new_methods(self):
        """Test that EthereumTracker has new methods."""
        from whale.ethereum import EthereumTracker
        
        tracker = EthereumTracker()
        
        # Check new methods exist
        assert hasattr(tracker, 'get_internal_transactions')
        assert callable(getattr(tracker, 'get_internal_transactions'))
        
        assert hasattr(tracker, 'get_gas_prices')
        assert callable(getattr(tracker, 'get_gas_prices'))
    
    @pytest.mark.asyncio
    async def test_get_internal_transactions_requires_api_key(self):
        """Test that internal transactions requires API key."""
        from whale.ethereum import EthereumTracker
        
        tracker = EthereumTracker()
        tracker.api_key = None
        
        result = await tracker.get_internal_transactions("0x1234567890123456789012345678901234567890")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_gas_prices_requires_api_key(self):
        """Test that gas prices requires API key."""
        from whale.ethereum import EthereumTracker
        
        tracker = EthereumTracker()
        tracker.api_key = None
        
        result = await tracker.get_gas_prices()
        assert result is None


class TestAISignalMessageFormat:
    """Tests for extended AI signal message format."""
    
    def test_format_signal_message_method_signature(self):
        """Test that format_signal_message has correct signature."""
        # Mock dependencies to avoid loading entire app
        with patch('signals.ai_signals.DataSourceManager'):
            from signals.ai_signals import AISignalAnalyzer
            
            # Create mock whale tracker
            mock_whale_tracker = Mock()
            mock_whale_tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
            
            analyzer = AISignalAnalyzer(mock_whale_tracker)
            
            # Verify method exists
            assert hasattr(analyzer, 'format_signal_message')
            assert callable(getattr(analyzer, 'format_signal_message'))
    
    def test_format_signal_message_extended_sections(self):
        """Test that format_signal_message includes all extended sections."""
        with patch('signals.ai_signals.DataSourceManager'):
            from signals.ai_signals import AISignalAnalyzer
            
            mock_whale_tracker = Mock()
            analyzer = AISignalAnalyzer(mock_whale_tracker)
            
            signal_data = {
                'probability': 72,
                'probability_direction': 'up',
                'raw_direction': 'long',  # Add raw_direction for proper display
                'factors': {
                    'whale': {'score': 5}
                }
            }
            
            whale_data = {
                'transaction_count': 15,
                'total_volume_usd': 50_000_000,
                'deposits': 45_000_000,
                'withdrawals': 120_000_000,
            }
            
            market_data = {
                'price_usd': 97500,
                'price_change_1h': 0.8,
                'price_change_24h': 2.3,
                'price_change_7d': -1.2,
                'market_cap': 1_920_000_000_000,
                'volume_24h': 45_200_000_000,
            }
            
            technical_data = {
                'rsi': {'value': 58, 'signal': 0},
                'macd': {'signal': 1},
                'bollinger': {'signal': 0, 'position': 'lower'},
                'ma_crossover': {'signal': 1},
            }
            
            message = analyzer.format_signal_message(
                symbol="BTC",
                signal_data=signal_data,
                whale_data=whale_data,
                market_data=market_data,
                technical_data=technical_data,
            )
            
            # Check for key sections in the message
            assert "AI СИГНАЛ: BTC" in message
            assert "НАПРАВЛЕНИЕ" in message
            assert "ЦЕНА И УРОВНИ" in message
            assert "ТРЕНД ЦЕНЫ" in message
            assert "РЫНОЧНЫЕ ДАННЫЕ" in message
            assert "АКТИВНОСТЬ КИТОВ" in message
            assert "ТЕХНИЧЕСКИЙ АНАЛИЗ" in message
            assert "УРОВНИ ПОДДЕРЖКИ/СОПРОТИВЛЕНИЯ" in message
            assert "ПРИЧИНЫ СИГНАЛА (TOP 5)" in message
            assert "ФАКТОРЫ АНАЛИЗА" in message
            
            # Check for specific data
            assert "72%" in message  # Probability
            assert "ЛОНГ" in message  # Direction
            assert "TP1:" in message and "TP2:" in message  # Two TP levels
            assert "Market Cap:" in message
            assert "Volume 24h:" in message
            assert "Vol/MCap:" in message
            assert "Score:" in message  # Whale score
            assert "RSI(14):" in message
            assert "MACD:" in message
            assert "EMA 9/21:" in message
            assert "R2:" in message and "S2:" in message  # Resistance/Support
            assert "Консенсус:" in message
            assert "Источников данных:" in message
    
    def test_format_signal_message_two_tp_levels(self):
        """Test that the message includes two TP levels."""
        with patch('signals.ai_signals.DataSourceManager'):
            from signals.ai_signals import AISignalAnalyzer
            
            mock_whale_tracker = Mock()
            analyzer = AISignalAnalyzer(mock_whale_tracker)
            
            signal_data = {
                'probability': 75,
                'probability_direction': 'up',
                'raw_direction': 'long',  # Add raw_direction for proper display
                'factors': {'whale': {'score': 3}}
            }
            
            whale_data = {'transaction_count': 0, 'total_volume_usd': 0, 'deposits': 0, 'withdrawals': 0}
            market_data = {
                'price_usd': 100,
                'price_change_1h': 0,
                'price_change_24h': 0,
                'price_change_7d': 0,
                'market_cap': 1_000_000_000,
                'volume_24h': 10_000_000,
            }
            
            message = analyzer.format_signal_message(
                symbol="TEST",
                signal_data=signal_data,
                whale_data=whale_data,
                market_data=market_data,
            )
            
            # Check for TP1 and TP2
            assert "TP1:" in message
            assert "TP2:" in message
            assert "(+1.5%)" in message  # TP1 percentage
            assert "(+2.0%)" in message  # TP2 percentage


class TestWhaleTrackerMenu:
    """Tests to verify whale tracker menu simplification."""
    
    def test_whale_keyboard_has_three_networks(self):
        """Test that whale keyboard has only BTC, ETH, SOL buttons."""
        # Mock required dependencies
        with patch('bot.settings'), \
             patch('bot.get_coin_price'), \
             patch('bot.get_api_stats'), \
             patch('bot.RealWhaleTracker'), \
             patch('bot.AISignalAnalyzer'):
            
            from bot import get_whale_keyboard
            
            keyboard = get_whale_keyboard()
            
            # Get all buttons
            all_buttons = []
            for row in keyboard.inline_keyboard:
                for button in row:
                    all_buttons.append(button.callback_data)
            
            # Check main network buttons
            assert "whale_btc" in all_buttons
            assert "whale_eth" in all_buttons
            assert "whale_sol" in all_buttons
            
            # Make sure no other network buttons exist
            assert "whale_ton" not in all_buttons
            assert "whale_bsc" not in all_buttons
            assert "whale_polygon" not in all_buttons
            assert "whale_arbitrum" not in all_buttons
            assert "whale_avalanche" not in all_buttons
            assert "whale_base" not in all_buttons


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
