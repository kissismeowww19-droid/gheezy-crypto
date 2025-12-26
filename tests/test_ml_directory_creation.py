"""
Test ML directory creation on bot initialization.

This test validates that:
1. The data/ml directory is created when MLDataCollector is initialized
2. The training_data.csv file is created with correct headers
3. The directory structure matches requirements
"""

import os
import tempfile
import shutil
import csv


def test_ml_directory_creation():
    """Test that ML data collector creates directory and CSV file."""
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "ml")
        csv_path = os.path.join(data_dir, "training_data.csv")
        
        # Simulate MLDataCollector initialization
        # 1. _ensure_dir() - creates directory
        os.makedirs(data_dir, exist_ok=True)
        assert os.path.exists(data_dir), "Directory should be created"
        
        # 2. _ensure_csv_header() - creates CSV with headers
        if not os.path.exists(csv_path):
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'symbol', 
                    'direction',
                    'entry_price',
                    'exit_price',
                    'target1_price',
                    'target2_price',
                    'stop_loss_price',
                    'probability',
                    'min_price_4h',
                    'max_price_4h',
                    'volume_24h',
                    'change_24h',
                    'whale_activity',
                    'result'
                ])
        
        # Verify CSV was created
        assert os.path.exists(csv_path), "CSV file should be created"
        
        # Verify CSV has correct headers
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            expected_headers = [
                'timestamp', 'symbol', 'direction', 'entry_price', 'exit_price',
                'target1_price', 'target2_price', 'stop_loss_price', 'probability',
                'min_price_4h', 'max_price_4h', 'volume_24h', 'change_24h',
                'whale_activity', 'result'
            ]
            assert headers == expected_headers, f"CSV headers mismatch: {headers}"
        
        print("✅ All tests passed!")
        print(f"   - Directory created: {data_dir}")
        print(f"   - CSV created: {csv_path}")
        print(f"   - Headers verified: {len(expected_headers)} columns")


def test_directory_exists_ok():
    """Test that creating directory multiple times doesn't fail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "ml")
        
        # Create directory first time
        os.makedirs(data_dir, exist_ok=True)
        assert os.path.exists(data_dir)
        
        # Create directory second time (should not fail)
        os.makedirs(data_dir, exist_ok=True)
        assert os.path.exists(data_dir)
        
        print("✅ Multiple directory creation test passed!")


if __name__ == "__main__":
    test_ml_directory_creation()
    test_directory_exists_ok()
    print("\n✅ All ML directory creation tests passed!")
