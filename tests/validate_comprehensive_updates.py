#!/usr/bin/env python3
"""
Simple validation script for comprehensive updates.
Validates that the code changes are in place without running full tests.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def check_file_content(file_path, expected_strings):
    """Check if file contains expected strings."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        results = []
        for expected in expected_strings:
            if expected in content:
                results.append((True, expected))
            else:
                results.append((False, expected))
        
        return results
    except Exception as e:
        return [(False, f"Error reading file: {e}")]


def main():
    print("=" * 60)
    print("COMPREHENSIVE UPDATES VALIDATION")
    print("=" * 60)
    
    all_passed = True
    
    # Test 1: Solana API Integration
    print("\n1. SOLANA API INTEGRATION")
    print("-" * 60)
    
    solana_checks = [
        'HELIUS_API_URL = "https://api.helius.xyz/v0"',
        'JUPITER_API_URL = "https://api.jup.ag"',
        'SOLANA_TRACKER_API_URL = "https://data.solanatracker.io"',
        'async def _get_from_helius(',
        'async def _get_from_jupiter(',
        'async def _get_from_solana_tracker(',
        '# Priority 1: Helius API',
        '# Priority 2: Jupiter API',
        '# Priority 3: SolanaTracker API',
    ]
    
    results = check_file_content('src/whale/solana.py', solana_checks)
    for passed, check in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {check[:50]}")
        if not passed:
            all_passed = False
    
    # Test 2: Ethereum Improvements
    print("\n2. ETHEREUM IMPROVEMENTS")
    print("-" * 60)
    
    ethereum_checks = [
        'class TransactionType(str, Enum):',
        'DEX_SWAP = "DEX_SWAP"',
        'CONTRACT_INTERACTION = "CONTRACT_INTERACTION"',
        'NFT_TRANSFER = "NFT_TRANSFER"',
        'async def get_internal_transactions(',
        'async def get_gas_prices(',
        '"0x1062a747393198f70f71ec65a582423dba7e5ab3"',  # HTX
        '"0x6262998ced04146fa42253a5c0af90ca02dfd2a3"',  # Crypto.com
        '"0x75e89d5979e4f6fba9f97c104c2f0afb3f1dcb88"',  # MEXC
        '"0x0d0707963952f2fba59dd06f2b425ace40b492fe"',  # Gate.io
        '"0x97b9d2102a9a65a26e1ee82d59e42d1b73b68689"',  # Bitget
    ]
    
    results = check_file_content('src/whale/ethereum.py', ethereum_checks)
    for passed, check in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {check[:50]}")
        if not passed:
            all_passed = False
    
    # Test 3: AI Signal Message Format
    print("\n3. AI SIGNAL MESSAGE FORMAT")
    print("-" * 60)
    
    ai_signal_checks = [
        '"🤖 *AI СИГНАЛ:',
        '"📊 *НАПРАВЛЕНИЕ*',
        '"💰 *ЦЕНА И УРОВНИ*',
        '"📈 *ТРЕНД ЦЕНЫ*',
        '"📊 *РЫНОЧНЫЕ ДАННЫЕ*',
        '"🐋 *АКТИВНОСТЬ КИТОВ*',
        '"⚡ *ТЕХНИЧЕСКИЙ АНАЛИЗ*',
        '"🎯 *УРОВНИ ПОДДЕРЖКИ/СОПРОТИВЛЕНИЯ*',
        '"🔥 *ПРИЧИНЫ СИГНАЛА (TOP 5)*',
        '"📊 *ФАКТОРЫ АНАЛИЗА*',
        'tp1_percent = 1.5',
        'tp2_percent = 2.0',
        'Market Cap:',
        'Volume 24h:',
        'Vol/MCap:',
    ]
    
    results = check_file_content('src/signals/ai_signals.py', ai_signal_checks)
    for passed, check in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {check[:50]}")
        if not passed:
            all_passed = False
    
    # Test 4: Whale Tracker Menu
    print("\n4. WHALE TRACKER MENU (Already Simplified)")
    print("-" * 60)
    
    whale_menu_checks = [
        'callback_data="whale_btc"',
        'callback_data="whale_eth"',
        'callback_data="whale_sol"',
        'def get_whale_keyboard(',
    ]
    
    results = check_file_content('src/bot.py', whale_menu_checks)
    for passed, check in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {check[:50]}")
        if not passed:
            all_passed = False
    
    # Final result
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL VALIDATIONS PASSED!")
        print("=" * 60)
        return 0
    else:
        print("✗ SOME VALIDATIONS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
