
import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from src.server.app import app
from src.backtest.engine import BacktestConfig

# Mock the engine run to avoid actual computation time
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.mark.asyncio
def test_backtest_stream_endpoint():
    print("🧪 Testing Backtest Streaming Endpoint...")
    
    # Mock data
    mock_request = {
        "symbol": "BTCUSDT",
        "start_date": "2024-01-01",
        "end_date": "2024-01-02",
        "initial_capital": 10000,
        "strategy_mode": "technical"
    }

    # IMPORTANT: We need to patch the BacktestEngine inside the app module or where it's imported
    # Since the endpoint does a local import `from src.backtest.engine import BacktestEngine`, 
    # mocking it is tricky without standard patching.
    # However, for an integration test, we can just run a very short backtest if we can't mock easily.
    # Let's try to run a real request but very short duration.
    
    client = TestClient(app)
    
    # Needs auth? The endpoint has `Depends(verify_auth)`.
    # We might need to mock verify_auth or provide a token.
    # Let's try to override the dependency.
    from src.server.app import verify_auth
    app.dependency_overrides[verify_auth] = lambda: True
    
    print("🚀 Sending request...")
    with client.stream("POST", "/api/backtest/run", json=mock_request) as response:
        print(f"📡 Status Code: {response.status_code}")
        assert response.status_code == 200
        
        # Read stream
        progress_count = 0
        has_result = False
        
        for line in response.iter_lines():
            if not line: continue
            
            data = json.loads(line)
            print(f"📦 Received Chunk: {data.get('type')}")
            
            if data['type'] == 'progress':
                progress_count += 1
                assert 'percent' in data
            elif data['type'] == 'result':
                has_result = True
                assert 'metrics' in data['data']
                if 'id' in data['data']:
                    print(f"✅ Received Backtest ID: #{data['data']['id']}")
                else:
                    print("⚠️ Backtest ID missing in response")
            elif data['type'] == 'error':
                print(f"❌ Error: {data['message']}")
                raise Exception(data['message'])
                
        print(f"✅ Received {progress_count} progress updates")
        print(f"✅ Received Final Result: {has_result}")
        
        assert has_result
        assert progress_count >= 0

if __name__ == "__main__":
    # Manually run the async test logic if not using pytest runner
    # But TestClient is synchronous wrapper around ASGI.
    # The stream() method returns a sync iterator.
    
    test_backtest_stream_endpoint()
