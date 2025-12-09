"""
Simple verification test for BSC fix.
Tests the logic without full dependency chain.
"""

import asyncio
import inspect


def test_bsc_file_structure():
    """Verify BSC file has the correct method structure."""
    import ast
    from pathlib import Path
    
    # Read the BSC file
    bsc_file = Path(__file__).parent.parent / "src" / "whale" / "bsc.py"
    with open(bsc_file) as f:
        tree = ast.parse(f.read())
    
    # Find the _get_from_rpc_with_rotation method
    method_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            if node.name == "_get_from_rpc_with_rotation":
                method_found = True
                
                # Check method parameters
                args = [arg.arg for arg in node.args.args]
                assert 'self' in args
                assert 'min_value_bnb' in args
                assert 'limit' in args
                
                # Look for RPC endpoints list
                source_code = ast.unparse(node)
                assert 'rpc_endpoints' in source_code
                assert 'bsc-dataseed1.binance.org' in source_code
                assert 'rpc.ankr.com/bsc' in source_code
                
                # Verify it uses simple sequential requests (not batch)
                # Should NOT have make_batch_request
                assert 'make_batch_request' not in source_code
                
                # Should have session.post for simple requests
                assert 'session.post' in source_code
                
                # Should fetch 3 blocks
                assert 'latest_block - 3' in source_code
                
                print("✓ BSC method structure validated")
                print("✓ Uses simple sequential requests (no batch)")
                print("✓ Tries multiple RPC endpoints")
                print("✓ Fetches only 3 blocks")
                break
    
    assert method_found, "_get_from_rpc_with_rotation method not found"


def test_tracker_parallel_structure():
    """Verify tracker.py uses parallel execution."""
    import ast
    from pathlib import Path
    
    # Read the tracker file
    tracker_file = Path(__file__).parent.parent / "src" / "whale" / "tracker.py"
    with open(tracker_file) as f:
        tree = ast.parse(f.read())
    
    # Find the get_all_transactions method
    method_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            if node.name == "get_all_transactions":
                method_found = True
                
                source_code = ast.unparse(node)
                
                # Verify it uses asyncio.gather (parallel execution)
                assert 'asyncio.gather' in source_code, "Should use asyncio.gather for parallel execution"
                
                # Verify it has fetch_with_timeout helper
                assert 'fetch_with_timeout' in source_code
                
                # Verify only BTC and ETH networks are called (post PR requirements)
                assert 'get_bitcoin_transactions' in source_code
                assert 'get_ethereum_transactions' in source_code
                
                # Should NOT have sequential network_methods loop
                assert 'for network in NETWORK_PRIORITY' not in source_code
                
                print("✓ Tracker uses parallel execution with asyncio.gather for BTC and ETH")
                print("✓ Both BTC and ETH networks run in parallel")
                print("✓ Individual timeouts per network")
                break
    
    assert method_found, "get_all_transactions method not found"


def test_polygon_rpc_optimization():
    """Verify Polygon uses RPC directly with 3 blocks."""
    import ast
    from pathlib import Path
    
    # Read the polygon file
    polygon_file = Path(__file__).parent.parent / "src" / "whale" / "polygon.py"
    with open(polygon_file) as f:
        content = f.read()
        tree = ast.parse(content)
    
    # Check get_large_transactions
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            if node.name == "get_large_transactions":
                source_code = ast.unparse(node)
                
                # Should call RPC directly
                assert '_get_from_rpc' in source_code
                
                print("✓ Polygon uses RPC")
                break
    
    # Check _get_from_single_rpc uses 3 blocks
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            if node.name == "_get_from_single_rpc":
                source_code = ast.unparse(node)
                
                # Should scan only 3 blocks
                assert 'latest_block - 3' in source_code
                
                print("✓ Polygon scans only 3 blocks")
                break


def test_ton_optimization():
    """Verify TON uses 3 addresses and 6s timeout."""
    import ast
    from pathlib import Path
    
    # Read the TON file
    ton_file = Path(__file__).parent.parent / "src" / "whale" / "ton.py"
    with open(ton_file) as f:
        content = f.read()
        tree = ast.parse(content)
    
    # Check address limit
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            if node.name in ["_get_from_toncenter_v3", "_get_from_toncenter", "_get_from_tonapi"]:
                source_code = ast.unparse(node)
                
                # Should use [:3] for 3 addresses
                assert '[:3]' in source_code, f"{node.name} should limit to 3 addresses"
                
                print(f"✓ {node.name} uses 3 addresses")
    
    # Check timeout
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            if node.name == "_make_api_request":
                source_code = ast.unparse(node)
                
                # Should have 6 second timeout
                assert 'total=6' in source_code or 'total = 6' in source_code
                
                print("✓ TON uses 6 second timeout")
                break


if __name__ == "__main__":
    print("\n=== Testing BSC Fix ===")
    test_bsc_file_structure()
    
    print("\n=== Testing Parallel Execution ===")
    test_tracker_parallel_structure()
    
    print("\n=== Testing Polygon Optimization ===")
    test_polygon_rpc_optimization()
    
    print("\n=== Testing TON Optimization ===")
    test_ton_optimization()
    
    print("\n✅ All structural tests passed!")
