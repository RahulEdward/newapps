"""
Trading Maven - Dynamic Table Factory for Symbol-Exchange-Interval Combinations
Creates separate tables for each symbol's historical data
"""
from sqlalchemy import Column, Integer, Float, Date, Time, DateTime, UniqueConstraint, inspect
from sqlalchemy.orm import declarative_base
from datetime import datetime
import re
import logging

from database.session import Base, engine, SessionLocal

# Dictionary to store dynamically created model classes
_table_models = {}


def get_table_name(symbol, exchange, interval):
    """
    Generate a valid table name for the symbol-exchange-interval combination
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE')
        exchange: Exchange code (e.g., 'NSE')
        interval: Data interval (e.g., '1m', 'D', 'ONE_DAY')
    
    Returns:
        Valid table name string
    """
    # Replace any non-alphanumeric characters with underscore
    symbol_clean = re.sub(r'[^a-zA-Z0-9]', '_', symbol)
    exchange_clean = re.sub(r'[^a-zA-Z0-9]', '_', exchange)
    interval_clean = re.sub(r'[^a-zA-Z0-9]', '_', interval)
    
    # Create table name in format: data_symbol_exchange_interval
    return f"data_{symbol_clean}_{exchange_clean}_{interval_clean}".lower()


def get_table_model(symbol, exchange, interval):
    """
    Get or create a SQLAlchemy model for the specified symbol-exchange-interval
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE')
        exchange: Exchange code (e.g., 'NSE')
        interval: Data interval (e.g., '1m', 'D')
    
    Returns:
        SQLAlchemy model class for the specified combination
    """
    table_name = get_table_name(symbol, exchange, interval)
    
    # If model already exists, return it
    if table_name in _table_models:
        return _table_models[table_name]
    
    # Create a new model class dynamically
    class_name = f"Data_{symbol}_{exchange}_{interval}".replace('-', '_').replace(' ', '_')
    
    # Create the model class dynamically
    model = type(class_name, (Base,), {
        '__tablename__': table_name,
        '__table_args__': (
            UniqueConstraint('date', 'time', name=f'uix_{table_name}_date_time'),
            {'extend_existing': True}
        ),
        'id': Column(Integer, primary_key=True, index=True),
        'date': Column(Date, nullable=False, index=True),
        'time': Column(Time, nullable=True, index=True),
        'open': Column(Float, nullable=False),
        'high': Column(Float, nullable=False),
        'low': Column(Float, nullable=False),
        'close': Column(Float, nullable=False),
        'volume': Column(Integer, nullable=False, default=0),
        'oi': Column(Integer, nullable=True, default=0),  # Open Interest for F&O
        'created_at': Column(DateTime, default=datetime.utcnow),
    })
    
    # Add to_dict method to the model
    def to_dict(self):
        return {
            'id': self.id,
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
    
    model.to_dict = to_dict
    
    # Store the model in our dictionary
    _table_models[table_name] = model
    logging.info(f"Created dynamic table model: {class_name} ({table_name})")
    
    return model


def ensure_table_exists(symbol, exchange, interval):
    """
    Ensure the table for the specified combination exists in the database
    
    Args:
        symbol: Stock symbol
        exchange: Exchange code
        interval: Data interval
    
    Returns:
        The model class for the table
    """
    model = get_table_model(symbol, exchange, interval)
    
    # Create the table if it doesn't exist
    inspector = inspect(engine)
    if not inspector.has_table(model.__tablename__):
        model.__table__.create(engine)
        logging.info(f"Created table in database: {model.__tablename__}")
    
    return model


def insert_ohlc_data(symbol, exchange, interval, data_list):
    """
    Insert OHLC data into the appropriate table
    
    Args:
        symbol: Stock symbol
        exchange: Exchange code
        interval: Data interval
        data_list: List of dicts with date, time, open, high, low, close, volume
    
    Returns:
        Number of records inserted
    """
    model = ensure_table_exists(symbol, exchange, interval)
    db = SessionLocal()
    
    try:
        inserted = 0
        for data in data_list:
            # Check if record already exists
            existing = db.query(model).filter(
                model.date == data['date'],
                model.time == data.get('time')
            ).first()
            
            if not existing:
                record = model(
                    date=data['date'],
                    time=data.get('time'),
                    open=data['open'],
                    high=data['high'],
                    low=data['low'],
                    close=data['close'],
                    volume=data.get('volume', 0),
                    oi=data.get('oi', 0)
                )
                db.add(record)
                inserted += 1
        
        db.commit()
        return inserted
    except Exception as e:
        db.rollback()
        logging.error(f"Error inserting data: {str(e)}")
        raise
    finally:
        db.close()


def get_data_by_timeframe(symbol, exchange, interval, start_date=None, end_date=None, limit=None):
    """
    Get data for the specified symbol, exchange, interval and date range
    
    Args:
        symbol: Stock symbol
        exchange: Exchange code
        interval: Data interval
        start_date: Start date (datetime.date)
        end_date: End date (datetime.date)
        limit: Maximum number of records to return
    
    Returns:
        List of data points as dictionaries
    """
    model = ensure_table_exists(symbol, exchange, interval)
    db = SessionLocal()
    
    try:
        query = db.query(model)
        
        if start_date:
            query = query.filter(model.date >= start_date)
        if end_date:
            query = query.filter(model.date <= end_date)
        
        query = query.order_by(model.date.desc(), model.time.desc() if model.time else model.date.desc())
        
        if limit:
            query = query.limit(limit)
        
        results = query.all()
        return [r.to_dict() for r in results]
    finally:
        db.close()


def get_available_tables():
    """
    Get a list of all available data tables
    
    Returns:
        List of dictionaries with symbol, exchange, interval info
    """
    inspector = inspect(engine)
    tables = []
    
    for table_name in inspector.get_table_names():
        if table_name.startswith('data_'):
            # Parse table name to extract symbol, exchange, interval
            parts = table_name.split('_')
            if len(parts) >= 4:  # data_symbol_exchange_interval
                tables.append({
                    'table_name': table_name,
                    'symbol': parts[1].upper(),
                    'exchange': parts[2].upper(),
                    'interval': '_'.join(parts[3:])  # Handle intervals like ONE_DAY
                })
    
    return tables


def get_earliest_date(symbol, exchange, interval):
    """
    Get the earliest available date for the specified symbol, exchange, and interval
    
    Args:
        symbol: Stock symbol
        exchange: Exchange code
        interval: Data interval
    
    Returns:
        datetime.date: Earliest available date or None if no data exists
    """
    try:
        model = ensure_table_exists(symbol, exchange, interval)
        db = SessionLocal()
        
        try:
            earliest_record = db.query(model).order_by(model.date.asc()).first()
            if earliest_record:
                return earliest_record.date
            return None
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error getting earliest date for {symbol} ({exchange}) {interval}: {str(e)}")
        return None


def get_latest_date(symbol, exchange, interval):
    """
    Get the latest available date for the specified symbol, exchange, and interval
    
    Args:
        symbol: Stock symbol
        exchange: Exchange code
        interval: Data interval
    
    Returns:
        datetime.date: Latest available date or None if no data exists
    """
    try:
        model = ensure_table_exists(symbol, exchange, interval)
        db = SessionLocal()
        
        try:
            latest_record = db.query(model).order_by(model.date.desc()).first()
            if latest_record:
                return latest_record.date
            return None
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error getting latest date for {symbol} ({exchange}) {interval}: {str(e)}")
        return None


def get_record_count(symbol, exchange, interval):
    """
    Get the total number of records for the specified symbol
    
    Args:
        symbol: Stock symbol
        exchange: Exchange code
        interval: Data interval
    
    Returns:
        int: Number of records
    """
    try:
        model = ensure_table_exists(symbol, exchange, interval)
        db = SessionLocal()
        
        try:
            count = db.query(model).count()
            return count
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error getting record count for {symbol} ({exchange}) {interval}: {str(e)}")
        return 0


def delete_table_data(symbol, exchange, interval):
    """
    Delete all data from a specific table
    
    Args:
        symbol: Stock symbol
        exchange: Exchange code
        interval: Data interval
    
    Returns:
        int: Number of records deleted
    """
    try:
        model = ensure_table_exists(symbol, exchange, interval)
        db = SessionLocal()
        
        try:
            count = db.query(model).delete()
            db.commit()
            return count
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error deleting data for {symbol} ({exchange}) {interval}: {str(e)}")
        return 0


def drop_table(symbol, exchange, interval):
    """
    Drop the entire table for a symbol
    
    Args:
        symbol: Stock symbol
        exchange: Exchange code
        interval: Data interval
    
    Returns:
        bool: True if successful
    """
    try:
        table_name = get_table_name(symbol, exchange, interval)
        
        # Remove from cache
        if table_name in _table_models:
            model = _table_models[table_name]
            model.__table__.drop(engine)
            del _table_models[table_name]
            logging.info(f"Dropped table: {table_name}")
            return True
        return False
    except Exception as e:
        logging.error(f"Error dropping table for {symbol} ({exchange}) {interval}: {str(e)}")
        return False
