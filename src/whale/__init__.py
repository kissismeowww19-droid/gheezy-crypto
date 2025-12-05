"""
Gheezy Crypto - Модуль отслеживания китов

Мониторинг крупных транзакций на Ethereum, BSC и Bitcoin.
Использует API которые работают в России без VPN:
- Etherscan API для Ethereum
- BscScan API для BSC
- Blockchair API для Bitcoin
"""

from whale.tracker import WhaleTracker, WhaleTransaction
from whale.ethereum import EthereumTracker, EthereumTransaction
from whale.bsc import BSCTracker, BSCTransaction
from whale.bitcoin import BitcoinTracker, BitcoinTransaction
from whale.alerts import (
    WhaleAlert,
    format_whale_alert_message,
    format_whale_summary,
    format_stats_message,
)
from whale.known_wallets import (
    get_wallet_label,
    get_ethereum_wallet_label,
    get_bsc_wallet_label,
    get_bitcoin_wallet_label,
    is_exchange_address,
    get_short_address,
)

__all__ = [
    # Main tracker
    "WhaleTracker",
    "WhaleTransaction",
    # Blockchain-specific trackers
    "EthereumTracker",
    "EthereumTransaction",
    "BSCTracker",
    "BSCTransaction",
    "BitcoinTracker",
    "BitcoinTransaction",
    # Alerts
    "WhaleAlert",
    "format_whale_alert_message",
    "format_whale_summary",
    "format_stats_message",
    # Wallet utilities
    "get_wallet_label",
    "get_ethereum_wallet_label",
    "get_bsc_wallet_label",
    "get_bitcoin_wallet_label",
    "is_exchange_address",
    "get_short_address",
]
