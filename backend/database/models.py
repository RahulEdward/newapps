from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Index, Sequence, ForeignKey, Date, Time, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import json
from .session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

class AngelOneCredential(Base):
    __tablename__ = "angel_one_credentials"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    api_key = Column(String, nullable=False)
    client_code = Column(String, nullable=False)
    pin = Column(String, nullable=False)
    totp_secret = Column(String, nullable=True)
    jwt_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    feed_token = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", backref="angel_one_credentials")

class SymToken(Base):
    __tablename__ = 'symtoken'
    id = Column(Integer, Sequence('symtoken_id_seq'), primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    brsymbol = Column(String, nullable=False, index=True)
    name = Column(String)
    exchange = Column(String, index=True)
    brexchange = Column(String, index=True)
    token = Column(String, index=True)
    expiry = Column(String)
    strike = Column(Float)
    lotsize = Column(Integer)
    instrumenttype = Column(String)
    tick_size = Column(Float)
    
    # Composite Index
    __table_args__ = (Index('idx_symbol_exchange', 'symbol', 'exchange'),)


class StockData(Base):
    """Model for storing OHLCV data for all symbols - Historify style unified table"""
    __tablename__ = 'stock_data'

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(20), nullable=False, index=True)
    interval = Column(String(20), nullable=False, default='D', index=True)  # D, W, 1m, 5m, 15m, etc.
    date = Column(Date, nullable=False, index=True)
    time = Column(Time, nullable=True, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False, default=0)
    oi = Column(Integer, nullable=True, default=0)  # Open Interest for F&O
    created_at = Column(DateTime, default=datetime.utcnow)

    # Create composite indexes for efficient querying
    __table_args__ = (
        UniqueConstraint('symbol', 'exchange', 'interval', 'date', 'time', name='uix_symbol_exchange_interval_date_time'),
        Index('idx_stock_symbol_date', 'symbol', 'date'),
        Index('idx_stock_exchange_date', 'exchange', 'date'),
        Index('idx_stock_interval', 'interval'),
    )

    def __repr__(self):
        return f'<StockData {self.symbol} {self.date} {self.time}>'

    def to_dict(self):
        """Convert the model instance to a dictionary"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'interval': self.interval,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'time': self.time.strftime('%H:%M:%S') if self.time else None,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'oi': self.oi,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def get_data_by_timeframe(cls, db_session, symbol, start_date, end_date, interval='D', exchange=None):
        """
        Get stock data for the specified symbol and timeframe
        
        Args:
            db_session: SQLAlchemy session
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            interval: Data interval (D, W, 1m, 5m, etc.)
            exchange: Optional exchange filter
        
        Returns:
            List of StockData records
        """
        query = db_session.query(cls).filter(
            cls.symbol == symbol,
            cls.interval == interval,
            cls.date >= start_date,
            cls.date <= end_date
        )
        
        if exchange:
            query = query.filter(cls.exchange == exchange)
        
        query = query.order_by(cls.date, cls.time)
        return query.all()

    @classmethod
    def get_latest_record(cls, db_session, symbol, exchange=None, interval='D'):
        """Get the latest record for a symbol"""
        query = db_session.query(cls).filter(
            cls.symbol == symbol,
            cls.interval == interval
        )
        if exchange:
            query = query.filter(cls.exchange == exchange)
        
        return query.order_by(cls.date.desc(), cls.time.desc()).first()

    @classmethod
    def get_earliest_record(cls, db_session, symbol, exchange=None, interval='D'):
        """Get the earliest record for a symbol"""
        query = db_session.query(cls).filter(
            cls.symbol == symbol,
            cls.interval == interval
        )
        if exchange:
            query = query.filter(cls.exchange == exchange)
        
        return query.order_by(cls.date.asc(), cls.time.asc()).first()

    @classmethod
    def get_record_count(cls, db_session, symbol=None, exchange=None, interval=None):
        """Get record count with optional filters"""
        query = db_session.query(cls)
        if symbol:
            query = query.filter(cls.symbol == symbol)
        if exchange:
            query = query.filter(cls.exchange == exchange)
        if interval:
            query = query.filter(cls.interval == interval)
        return query.count()

    @classmethod
    def get_available_symbols(cls, db_session, exchange=None):
        """Get list of symbols that have data"""
        from sqlalchemy import distinct, func
        
        query = db_session.query(
            cls.symbol,
            cls.exchange,
            func.count(cls.id).label('record_count'),
            func.min(cls.date).label('earliest_date'),
            func.max(cls.date).label('latest_date')
        ).group_by(cls.symbol, cls.exchange)
        
        if exchange:
            query = query.filter(cls.exchange == exchange)
        
        return query.all()


class Checkpoint(Base):
    """Model for tracking last downloaded data points for incremental updates"""
    __tablename__ = 'checkpoints'

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(20), nullable=True)
    interval = Column(String(20), nullable=True, default='D')
    last_downloaded_date = Column(Date, nullable=True)
    last_downloaded_time = Column(Time, nullable=True)
    total_records = Column(Integer, default=0)
    last_update = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('symbol', 'exchange', 'interval', name='uix_checkpoint_symbol_exchange_interval'),
    )

    def __repr__(self):
        return f'<Checkpoint {self.symbol} {self.last_downloaded_date}>'

    def to_dict(self):
        """Convert the model instance to a dictionary"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'interval': self.interval,
            'last_downloaded_date': self.last_downloaded_date.strftime('%Y-%m-%d') if self.last_downloaded_date else None,
            'last_downloaded_time': self.last_downloaded_time.strftime('%H:%M:%S') if self.last_downloaded_time else None,
            'total_records': self.total_records,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ScheduledJob(Base):
    """Model for persisting scheduler jobs - Historify style"""
    __tablename__ = 'scheduled_jobs'

    id = Column(String(100), primary_key=True)  # UUID or custom ID
    name = Column(String(200), nullable=False)
    job_type = Column(String(50), nullable=False)  # 'daily', 'interval', 'market_close', 'pre_market'
    time = Column(String(10), nullable=True)  # For daily jobs (HH:MM format)
    minutes = Column(Integer, nullable=True)  # For interval jobs
    symbols = Column(Text, nullable=True)  # JSON string of symbols list
    exchanges = Column(Text, nullable=True)  # JSON string of exchanges list
    data_interval = Column(String(20), default='D')  # Data interval (D, W, 1m, 5m, etc.)
    is_paused = Column(Boolean, default=False)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ScheduledJob {self.name} ({self.job_type})>'

    def get_symbols(self):
        """Get symbols as list"""
        if self.symbols:
            return json.loads(self.symbols)
        return None

    def set_symbols(self, symbols_list):
        """Set symbols from list"""
        if symbols_list:
            self.symbols = json.dumps(symbols_list)
        else:
            self.symbols = None

    def get_exchanges(self):
        """Get exchanges as list"""
        if self.exchanges:
            return json.loads(self.exchanges)
        return None

    def set_exchanges(self, exchanges_list):
        """Set exchanges from list"""
        if exchanges_list:
            self.exchanges = json.dumps(exchanges_list)
        else:
            self.exchanges = None

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.job_type,
            'time': self.time,
            'minutes': self.minutes,
            'symbols': self.get_symbols(),
            'exchanges': self.get_exchanges(),
            'interval': self.data_interval,
            'paused': self.is_paused,
            'status': 'paused' if self.is_paused else 'active',
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

