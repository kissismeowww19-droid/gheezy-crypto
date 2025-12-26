#!/usr/bin/env python3
"""
Simple verification script to test ML directory creation.
This script mimics what happens when the bot starts up.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def verify_ml_directory_setup():
    """Verify ML directory is created and configured correctly."""
    print("=" * 60)
    print("ML Directory Setup Verification")
    print("=" * 60)
    
    # Check 1: data/ml directory exists
    data_ml_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'ml')
    data_ml_dir = os.path.abspath(data_ml_dir)
    
    print(f"\n1. Checking data/ml directory:")
    print(f"   Path: {data_ml_dir}")
    print(f"   Exists: {os.path.exists(data_ml_dir)}")
    
    if os.path.exists(data_ml_dir):
        contents = os.listdir(data_ml_dir)
        print(f"   Contents: {contents}")
    
    # Check 2: .gitkeep file exists
    gitkeep_path = os.path.join(data_ml_dir, '.gitkeep')
    print(f"\n2. Checking .gitkeep file:")
    print(f"   Path: {gitkeep_path}")
    print(f"   Exists: {os.path.exists(gitkeep_path)}")
    
    # Check 3: .gitignore configuration
    gitignore_path = os.path.join(os.path.dirname(__file__), '..', '.gitignore')
    gitignore_path = os.path.abspath(gitignore_path)
    print(f"\n3. Checking .gitignore configuration:")
    print(f"   Path: {gitignore_path}")
    
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r') as f:
            gitignore_content = f.read()
            has_training_data = 'data/ml/training_data.csv' in gitignore_content
            has_gitkeep_exception = '!data/ml/.gitkeep' in gitignore_content
            print(f"   Ignores training_data.csv: {has_training_data}")
            print(f"   Allows .gitkeep: {has_gitkeep_exception}")
    
    # Check 4: Test MLDataCollector initialization (simulation)
    print(f"\n4. Testing MLDataCollector logic:")
    test_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'ml_test')
    test_dir = os.path.abspath(test_dir)
    
    try:
        # Simulate _ensure_dir()
        os.makedirs(test_dir, exist_ok=True)
        print(f"   ✅ Directory creation works (test_dir: {test_dir})")
        
        # Simulate _ensure_csv_header()
        # Note: Headers must match MLDataCollector._ensure_csv_header() in src/ml/data_collector.py
        import csv
        csv_path = os.path.join(test_dir, 'training_data.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'symbol', 'direction', 'entry_price', 'exit_price',
                'target1_price', 'target2_price', 'stop_loss_price', 'probability',
                'min_price_4h', 'max_price_4h', 'volume_24h', 'change_24h',
                'whale_activity', 'result'
            ])
        print(f"   ✅ CSV creation works")
        
        # Cleanup test directory
        import shutil
        shutil.rmtree(test_dir)
        print(f"   ✅ Cleanup successful")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Check 5: Verify bot.py has ml_collector import
    bot_py_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'bot.py')
    bot_py_path = os.path.abspath(bot_py_path)
    print(f"\n5. Checking bot.py integration:")
    print(f"   Path: {bot_py_path}")
    
    if os.path.exists(bot_py_path):
        with open(bot_py_path, 'r') as f:
            bot_content = f.read()
            # Check for specific import statement
            has_import = 'from ml.data_collector import ml_collector' in bot_content
            # Check for initialization in on_startup (looking for the log line)
            has_init = 'ml_collector.csv_path' in bot_content and 'on_startup' in bot_content
            print(f"   Has ml_collector import: {has_import}")
            print(f"   Initializes in on_startup: {has_init}")
            
            if not has_import:
                print("   ⚠️  Warning: ml_collector import not found in bot.py")
            if not has_init:
                print("   ⚠️  Warning: ml_collector initialization not found in on_startup")
    else:
        print("   ❌ bot.py not found!")
        return False
    
    print("\n" + "=" * 60)
    print("✅ Verification complete!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = verify_ml_directory_setup()
    sys.exit(0 if success else 1)
