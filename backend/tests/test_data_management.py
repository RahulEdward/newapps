
import pytest
from datetime import datetime, timedelta
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import Base
from charts.models import OHLCData, DataDownloadStatus, SymbolGroup, SymbolGroupItem, DataQualityLog
from charts.data_manager import HistoricalDataManager

# Use in-memory SQLite for testing to ensure no harm to user's app
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory database for each test"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def mock_angel_client():
    """Mock Angel One client to avoid real API calls"""
    client = MagicMock()
    client.jwt_token = "mock_token"
    client.BASE_URL = "https://mock.api"
    client._get_headers.return_value = {"Authorization": "Bearer mock_token"}
    return client

@pytest.mark.asyncio
async def test_symbol_group_management(db_session):
    """Test creating groups and adding symbols"""
    # 1. Create a Group
    group = SymbolGroup(user_id=1, name="My Test Watchlist", description="Stocks to watch")
    db_session.add(group)
    db_session.commit()
    
    assert group.id is not None
    assert group.name == "My Test Watchlist"
    
    # 2. Add Symbol to Group
    item = SymbolGroupItem(
        group_id=group.id,
        symbol="RELIANCE-EQ",
        token="12345",
        exchange="NSE"
    )
    db_session.add(item)
    db_session.commit()
    
    # 3. Verify
    saved_group = db_session.query(SymbolGroup).first()
    assert len(saved_group.symbols) == 1
    assert saved_group.symbols[0].symbol == "RELIANCE-EQ"

@pytest.mark.asyncio
async def test_historical_data_download_flow(db_session, mock_angel_client):
    """Test the full download flow with mocked API"""
    manager = HistoricalDataManager(db_session, mock_angel_client)
    
    # Mock the internal API fetch method to return dummy candles
    with patch.object(manager, '_fetch_candles_from_api', new_callable=AsyncMock) as mock_fetch:
        # Prepare dummy data
        now = datetime.utcnow()
        mock_candles = [
            {
                'timestamp': now - timedelta(days=1),
                'open': 100.0, 'high': 105.0, 'low': 99.0, 'close': 102.0, 'volume': 1000
            },
            {
                'timestamp': now,
                'open': 102.0, 'high': 108.0, 'low': 101.0, 'close': 107.0, 'volume': 1500
            }
        ]
        mock_fetch.return_value = mock_candles

        # Trigger Download
        result = await manager.download_historical_data(
            symbol="TCS-EQ",
            token="54321",
            exchange="NSE",
            timeframe="ONE_DAY",
            from_date=now - timedelta(days=2),
            to_date=now,
            client_code="TESTUSER"
        )
        
        # Verify Success
        assert result['status'] == "success"
        assert result['records_downloaded'] == 2
        
        # Verify Data in DB
        saved_data = db_session.query(OHLCData).filter(OHLCData.symbol == "TCS-EQ").all()
        assert len(saved_data) == 2
        assert saved_data[0].open == 100.0
        
        # Verify Status Record
        status = db_session.query(DataDownloadStatus).first()
        assert status.status == "completed"
        assert status.progress_percent == 100

@pytest.mark.asyncio
async def test_data_quality_validation(db_session):
    """Test if invalid data is detected"""
    manager = HistoricalDataManager(db_session)
    
    # Insert some bad data manually
    bad_candle = OHLCData(
        symbol="BAD-DATA-EQ",
        token="99999",
        exchange="NSE",
        timeframe="ONE_DAY",
        timestamp=datetime.utcnow(),
        open=100.0,
        high=90.0, # High < Open (Invalid)
        low=80.0,
        close=95.0,
        volume=0
    )
    db_session.add(bad_candle)
    db_session.commit()
    
    # Run Validation
    manager._validate_downloaded_data("BAD-DATA-EQ", "ONE_DAY")
    
    # Check Logs
    logs = db_session.query(DataQualityLog).filter(DataQualityLog.symbol == "BAD-DATA-EQ").all()
    assert len(logs) > 0
    assert logs[0].check_type == 'ohlc_validation'
    assert "Invalid OHLC" in logs[0].message

@pytest.mark.asyncio
async def test_csv_export_format(db_session):
    """Test fetching data as DataFrame (mimicking CSV ready format)"""
    manager = HistoricalDataManager(db_session)
    
    # Insert data
    candle = OHLCData(
        symbol="INFY-EQ",
        token="1111",
        exchange="NSE",
        timeframe="ONE_DAY",
        timestamp=datetime.utcnow(),
        open=1500.0, high=1520.0, low=1490.0, close=1510.0, volume=5000
    )
    db_session.add(candle)
    db_session.commit()
    
    # Fetch as DataFrame
    df = manager.get_historical_data("INFY-EQ", "ONE_DAY")
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "open" in df.columns
    assert df.iloc[0]['close'] == 1510.0
