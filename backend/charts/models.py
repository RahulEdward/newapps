"""
Historical Data Models - Historify Style
Tables for storing OHLCV data, download status, and symbol groups
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Index, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database.session import Base


class OHLCData(Base):
    """
    OHLCV Historical Data Table
    Stores candle data downloaded from Angel One
    """
    __tablename__ = "ohlc_data"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    token = Column(String(20), nullable=False, index=True)
    exchange = Column(String(20), nullable=False)
    timeframe = Column(String(20), nullable=False)  # ONE_MINUTE, FIVE_MINUTE, ONE_DAY etc
    
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, default=0)
    oi = Column(Integer, default=0)  # Open Interest for F&O
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite indexes for efficient queries
    __table_args__ = (
        Index('idx_symbol_timeframe_timestamp', 'symbol', 'timeframe', 'timestamp'),
        Index('idx_token_timeframe', 'token', 'timeframe'),
    )


class DataDownloadStatus(Base):
    """
    Tracks download status for each symbol/timeframe combination
    Historify-style progress tracking
    """
    __tablename__ = "data_download_status"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False)
    token = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False)
    timeframe = Column(String(20), nullable=False)
    
    status = Column(String(20), default='pending')  # pending, downloading, completed, failed
    total_records = Column(Integer, default=0)
    last_updated = Column(DateTime, nullable=True)
    first_date = Column(DateTime, nullable=True)
    last_date = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Progress tracking
    progress_percent = Column(Float, default=0.0)
    download_speed = Column(Float, default=0.0)  # records per second
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_status_symbol_tf', 'symbol', 'timeframe', unique=True),
    )


class SymbolGroup(Base):
    """
    User-defined symbol groups (like Watchlists, NIFTY50, BankNifty etc)
    """
    __tablename__ = "symbol_groups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False)  # True for NIFTY50, BANKNIFTY etc
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    symbols = relationship("SymbolGroupItem", back_populates="group", cascade="all, delete-orphan")


class SymbolGroupItem(Base):
    """
    Symbols within a group
    """
    __tablename__ = "symbol_group_items"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("symbol_groups.id"), nullable=False)
    symbol = Column(String(50), nullable=False)
    token = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False)
    
    added_at = Column(DateTime, default=datetime.utcnow)
    
    group = relationship("SymbolGroup", back_populates="symbols")


class DataQualityLog(Base):
    """
    Data validation and quality check logs
    """
    __tablename__ = "data_quality_logs"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False)
    token = Column(String(20), nullable=False)
    timeframe = Column(String(20), nullable=False)
    
    check_type = Column(String(50), nullable=False)  # gap_detection, ohlc_validation, volume_spike
    severity = Column(String(20), default='info')  # info, warning, error
    message = Column(Text, nullable=False)
    
    # Quality metrics
    completeness_score = Column(Float, default=100.0)
    accuracy_score = Column(Float, default=100.0)
    
    checked_at = Column(DateTime, default=datetime.utcnow)
