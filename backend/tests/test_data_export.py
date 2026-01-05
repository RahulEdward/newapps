
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import Base
from routers.angel_one import angel_sessions
from routers.auth import utils

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory database"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def mock_angel_client():
    client = MagicMock()
    client.jwt_token = "mock_token"
    # Mock the getCandleData response
    client.getCandleData.return_value = {
        "status": True,
        "message": "SUCCESS",
        "data": [
            ["2023-12-01T09:15:00+05:30", 2000, 2010, 1990, 2005, 1000],
            ["2023-12-02T09:15:00+05:30", 2005, 2020, 2000, 2015, 1200]
        ]
    }
    return client

@patch("routers.angel_one.angel_sessions")
def test_export_data_fetch(mock_sessions, db_session, mock_angel_client):
    """Test the direct data fetch endpoint for export"""
    from fastapi.testclient import TestClient
    from main import app
    from database.session import get_db
    
    # Override DB
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    
    client = TestClient(app)
    
    # Register and Login to get token
    client.post("/auth/register", json={"email": "export@test.com", "password": "pass", "full_name": "Export User"})
    login_res = client.post("/auth/login", json={"email": "export@test.com", "password": "pass"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Setup Mock Session
    # Hand-inject the mock client into the global dictionary (via the patch or directly if preferred, 
    # but since main.py imports it, we need to be careful. 
    # The safest way in a unit test is to just point the import in router to our dict or mock it effectively)
    
    # Actually, because `angel_sessions` is imported in `routers/angel_one.py` and `charts/router.py`,
    # patching it where it is used is key.
    
    # Use the `angel_sessions` dict in `charts.router`
    from charts.router import angel_sessions as charts_angel_sessions
    charts_angel_sessions["TEST_EXPORT"] = mock_angel_client
    
    # 2. Call Export Endpoint
    payload = {
        "symbol": "RELIANCE-EQ",
        "token": "1234",
        "exchange": "NSE",
        "timeframe": "ONE_DAY",
        "from_date": "2023-12-01",
        "to_date": "2023-12-05",
        "client_code": "TEST_EXPORT"
    }
    
    response = client.post("/data/export/fetch", json=payload, headers=headers)
    
    print(response.json())
    
    # 3. Validation
    assert response.status_code == 200
    res_data = response.json()
    
    assert res_data["status"] == "success"
    assert res_data["count"] == 2
    assert res_data["data"][0]["date"] == "2023-12-01"
    assert res_data["data"][0]["close"] == 2005.0
    
    # Verify client was called with correct params
    mock_angel_client.getCandleData.assert_called_once()
    args, kwargs = mock_angel_client.getCandleData.call_args
    # Check args passed to client
    called_params = args[0]
    assert called_params["symboltoken"] == "1234"
    assert called_params["interval"] == "ONE_DAY"
