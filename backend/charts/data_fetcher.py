"""
Trading Maven - Chunked Data Fetcher
Fetches historical data in chunks to work around API limitations
Supports Angel One API with rate limiting and checkpoint-based incremental updates
"""
from datetime import datetime, timedelta, time as dt_time
import logging
import asyncio
import random
from typing import List, Dict, Optional, Any

from database.session import SessionLocal
from database.models import Checkpoint, StockData
from utils.rate_limiter import (
    RateLimiter, AsyncRateLimiter, 
    batch_process, async_batch_process,
    broker_rate_limiter, async_rate_limiter
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supported exchanges
SUPPORTED_EXCHANGES = [
    {"code": "NSE", "name": "NSE Equity"},
    {"code": "NFO", "name": "NSE Futures & Options"},
    {"code": "CDS", "name": "NSE Currency"},
    {"code": "NSE_INDEX", "name": "NSE Index"},
    {"code": "BSE", "name": "BSE Equity"},
    {"code": "BFO", "name": "BSE Futures & Options"},
    {"code": "BCD", "name": "BSE Currency"},
    {"code": "BSE_INDEX", "name": "BSE Index"},
    {"code": "MCX", "name": "MCX Commodity"}
]

# Interval mapping for Angel One API
INTERVAL_MAP = {
    '1m': 'ONE_MINUTE',
    '3m': 'THREE_MINUTE',
    '5m': 'FIVE_MINUTE',
    '10m': 'TEN_MINUTE',
    '15m': 'FIFTEEN_MINUTE',
    '30m': 'THIRTY_MINUTE',
    '1h': 'ONE_HOUR',
    '1d': 'ONE_DAY',
    'D': 'ONE_DAY',
    'ONE_MINUTE': 'ONE_MINUTE',
    'FIVE_MINUTE': 'FIVE_MINUTE',
    'FIFTEEN_MINUTE': 'FIFTEEN_MINUTE',
    'THIRTY_MINUTE': 'THIRTY_MINUTE',
    'ONE_HOUR': 'ONE_HOUR',
    'ONE_DAY': 'ONE_DAY'
}


def convert_interval_format(interval: str) -> str:
    """Convert interval format to Angel One API format"""
    return INTERVAL_MAP.get(interval, 'ONE_DAY')


def get_supported_exchanges() -> List[Dict]:
    """Get list of supported exchanges"""
    return SUPPORTED_EXCHANGES


def get_supported_intervals() -> Dict:
    """Get list of supported intervals"""
    return {
        'days': ['ONE_DAY'],
        'hours': ['ONE_HOUR'],
        'minutes': ['ONE_MINUTE', 'FIVE_MINUTE', 'FIFTEEN_MINUTE', 'THIRTY_MINUTE']
    }


# Use the centralized rate limiter
rate_limiter = async_rate_limiter


class ChunkedDataFetcher:
    """
    Fetches historical data in chunks to work around API limitations
    Supports incremental updates using checkpoints
    """
    
    def __init__(self, angel_client=None, chunk_days: int = 30):
        """
        Initialize the chunked data fetcher
        
        Args:
            angel_client: Angel One SmartConnect client instance
            chunk_days: Maximum days per API request (default 30)
        """
        self.angel_client = angel_client
        self.chunk_days = chunk_days
        self.rate_limit_delay = 0.5  # seconds between API calls
    
    async def fetch_historical_data_chunked(
        self,
        symbol: str,
        token: str,
        exchange: str,
        start_date: str,
        end_date: str,
        interval: str = 'ONE_DAY'
    ) -> List[Dict]:
        """
        Fetch historical data in chunks to work around API limitations
        
        Args:
            symbol: Stock symbol
            token: Instrument token
            exchange: Exchange name (NSE, BSE, NFO, etc.)
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            interval: Data interval (ONE_MINUTE, FIVE_MINUTE, ONE_DAY, etc.)
        
        Returns:
            Combined list of all data points
        """
        all_data = []
        
        # Convert dates to datetime objects
        current_start = datetime.strptime(start_date, '%Y-%m-%d')
        final_end = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Adjust chunk size based on interval
        chunk_days = self._get_chunk_days(interval)
        
        total_chunks = ((final_end - current_start).days // chunk_days) + 1
        current_chunk = 0
        
        while current_start < final_end:
            # Calculate chunk end date
            chunk_end = min(current_start + timedelta(days=chunk_days - 1), final_end)
            current_chunk += 1
            
            logger.info(f"Fetching chunk {current_chunk}/{total_chunks}: "
                       f"{current_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
            
            try:
                # Fetch data for this chunk
                chunk_data = await self._fetch_chunk(
                    symbol=symbol,
                    token=token,
                    exchange=exchange,
                    from_date=current_start,
                    to_date=chunk_end,
                    interval=interval
                )
                
                if chunk_data:
                    all_data.extend(chunk_data)
                    logger.info(f"Retrieved {len(chunk_data)} records in chunk {current_chunk}")
                else:
                    logger.warning(f"No data returned for chunk {current_chunk}")
                    
            except Exception as e:
                logger.error(f"Error fetching chunk {current_chunk}: {e}")
                # Continue with next chunk even if one fails
            
            # Rate limiting
            await asyncio.sleep(self.rate_limit_delay)
            
            # Move to next chunk
            current_start = chunk_end + timedelta(days=1)
        
        logger.info(f"Total records retrieved for {symbol}: {len(all_data)}")
        return all_data
    
    async def _fetch_chunk(
        self,
        symbol: str,
        token: str,
        exchange: str,
        from_date: datetime,
        to_date: datetime,
        interval: str
    ) -> List[Dict]:
        """
        Fetch a single chunk of data from Angel One API
        """
        if not self.angel_client:
            logger.error("Angel client not initialized")
            return []
        
        try:
            # Format dates for Angel One API
            from_date_str = from_date.strftime('%Y-%m-%d 09:15')
            to_date_str = to_date.strftime('%Y-%m-%d 15:30')
            
            # Call Angel One historical data API
            historic_params = {
                "exchange": exchange,
                "symboltoken": token,
                "interval": interval,
                "fromdate": from_date_str,
                "todate": to_date_str
            }
            
            response = self.angel_client.getCandleData(historic_params)
            
            if response and response.get('status'):
                data = response.get('data', [])
                return self._parse_candle_data(data, symbol, exchange, interval)
            else:
                logger.warning(f"API returned error: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Error in _fetch_chunk: {e}")
            return []
    
    def _parse_candle_data(
        self,
        data: List,
        symbol: str,
        exchange: str,
        interval: str
    ) -> List[Dict]:
        """
        Parse candle data from Angel One API response
        """
        parsed_data = []
        
        for candle in data:
            try:
                # Angel One returns: [timestamp, open, high, low, close, volume]
                timestamp = datetime.strptime(candle[0], '%Y-%m-%dT%H:%M:%S%z')
                
                parsed_data.append({
                    'symbol': symbol,
                    'exchange': exchange,
                    'interval': interval,
                    'date': timestamp.date(),
                    'time': timestamp.time() if interval != 'ONE_DAY' else None,
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': int(candle[5]) if len(candle) > 5 else 0
                })
            except Exception as e:
                logger.error(f"Error parsing candle: {e}")
                continue
        
        return parsed_data
    
    def _get_chunk_days(self, interval: str) -> int:
        """
        Get appropriate chunk size based on interval
        Smaller intervals need smaller chunks due to data volume
        """
        chunk_map = {
            'ONE_MINUTE': 5,      # 5 days for 1-minute data
            'FIVE_MINUTE': 15,    # 15 days for 5-minute data
            'FIFTEEN_MINUTE': 30, # 30 days for 15-minute data
            'THIRTY_MINUTE': 60,  # 60 days for 30-minute data
            'ONE_HOUR': 90,       # 90 days for hourly data
            'ONE_DAY': 365,       # 365 days for daily data
        }
        return chunk_map.get(interval, self.chunk_days)
    
    async def fetch_with_checkpoint(
        self,
        symbol: str,
        token: str,
        exchange: str,
        interval: str = 'ONE_DAY',
        end_date: str = None
    ) -> Dict[str, Any]:
        """
        Fetch data using checkpoint for incremental updates
        
        Args:
            symbol: Stock symbol
            token: Instrument token
            exchange: Exchange name
            interval: Data interval
            end_date: End date (defaults to today)
        
        Returns:
            Dict with status and record count
        """
        db = SessionLocal()
        
        try:
            # Get checkpoint for this symbol
            checkpoint = db.query(Checkpoint).filter(
                Checkpoint.symbol == symbol,
                Checkpoint.exchange == exchange,
                Checkpoint.interval == interval
            ).first()
            
            # Determine start date
            if checkpoint and checkpoint.last_downloaded_date:
                # Continue from last downloaded date
                start_date = (checkpoint.last_downloaded_date + timedelta(days=1)).strftime('%Y-%m-%d')
                logger.info(f"Continuing from checkpoint: {start_date}")
            else:
                # Default to 1 year ago
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                logger.info(f"No checkpoint found, starting from: {start_date}")
            
            # End date defaults to today
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            # Check if we need to fetch
            if start_date >= end_date:
                logger.info(f"Data already up to date for {symbol}")
                return {'status': 'up_to_date', 'records': 0}
            
            # Fetch data in chunks
            data = await self.fetch_historical_data_chunked(
                symbol=symbol,
                token=token,
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
                interval=interval
            )
            
            if not data:
                return {'status': 'no_data', 'records': 0}
            
            # Save data to database
            records_saved = self._save_to_database(db, data, interval)
            
            # Update checkpoint
            self._update_checkpoint(db, symbol, exchange, interval, data)
            
            return {
                'status': 'success',
                'records': records_saved,
                'start_date': start_date,
                'end_date': end_date
            }
            
        except Exception as e:
            logger.error(f"Error in fetch_with_checkpoint: {e}")
            db.rollback()
            return {'status': 'error', 'error': str(e)}
        finally:
            db.close()
    
    def _save_to_database(self, db, data: List[Dict], interval: str) -> int:
        """
        Save fetched data to StockData table
        """
        saved_count = 0
        
        for record in data:
            try:
                # Check if record exists
                existing = db.query(StockData).filter(
                    StockData.symbol == record['symbol'],
                    StockData.exchange == record['exchange'],
                    StockData.interval == record['interval'],
                    StockData.date == record['date'],
                    StockData.time == record['time']
                ).first()
                
                if existing:
                    # Update existing record
                    existing.open = record['open']
                    existing.high = record['high']
                    existing.low = record['low']
                    existing.close = record['close']
                    existing.volume = record['volume']
                else:
                    # Insert new record
                    stock_data = StockData(
                        symbol=record['symbol'],
                        exchange=record['exchange'],
                        interval=record['interval'],
                        date=record['date'],
                        time=record['time'],
                        open=record['open'],
                        high=record['high'],
                        low=record['low'],
                        close=record['close'],
                        volume=record['volume']
                    )
                    db.add(stock_data)
                    saved_count += 1
                    
            except Exception as e:
                logger.error(f"Error saving record: {e}")
                continue
        
        db.commit()
        logger.info(f"Saved {saved_count} new records to database")
        return saved_count
    
    def _update_checkpoint(self, db, symbol: str, exchange: str, interval: str, data: List[Dict]):
        """
        Update checkpoint after successful data fetch
        """
        if not data:
            return
        
        # Find the latest date in fetched data
        latest_record = max(data, key=lambda x: (x['date'], x['time'] or datetime.min.time()))
        
        # Get or create checkpoint
        checkpoint = db.query(Checkpoint).filter(
            Checkpoint.symbol == symbol,
            Checkpoint.exchange == exchange,
            Checkpoint.interval == interval
        ).first()
        
        if checkpoint:
            checkpoint.last_downloaded_date = latest_record['date']
            checkpoint.last_downloaded_time = latest_record['time']
            checkpoint.total_records = (checkpoint.total_records or 0) + len(data)
            checkpoint.last_update = datetime.utcnow()
        else:
            checkpoint = Checkpoint(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                last_downloaded_date=latest_record['date'],
                last_downloaded_time=latest_record['time'],
                total_records=len(data)
            )
            db.add(checkpoint)
        
        db.commit()
        logger.info(f"Updated checkpoint for {symbol}: {latest_record['date']}")


async def fetch_multiple_symbols(
    angel_client,
    symbols: List[Dict],
    interval: str = 'ONE_DAY',
    start_date: str = None,
    end_date: str = None,
    use_checkpoint: bool = True
) -> Dict[str, Any]:
    """
    Fetch data for multiple symbols with progress tracking
    
    Args:
        angel_client: Angel One client
        symbols: List of dicts with symbol, token, exchange
        interval: Data interval
        start_date: Start date (optional if using checkpoint)
        end_date: End date (defaults to today)
        use_checkpoint: Whether to use checkpoint for incremental updates
    
    Returns:
        Summary of fetch operation
    """
    fetcher = ChunkedDataFetcher(angel_client)
    
    results = {
        'total_symbols': len(symbols),
        'successful': 0,
        'failed': 0,
        'total_records': 0,
        'details': []
    }
    
    for idx, sym in enumerate(symbols):
        logger.info(f"Processing {idx + 1}/{len(symbols)}: {sym['symbol']}")
        
        try:
            if use_checkpoint:
                result = await fetcher.fetch_with_checkpoint(
                    symbol=sym['symbol'],
                    token=sym['token'],
                    exchange=sym['exchange'],
                    interval=interval,
                    end_date=end_date
                )
            else:
                # Fresh download
                if not start_date:
                    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                if not end_date:
                    end_date = datetime.now().strftime('%Y-%m-%d')
                
                data = await fetcher.fetch_historical_data_chunked(
                    symbol=sym['symbol'],
                    token=sym['token'],
                    exchange=sym['exchange'],
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval
                )
                
                # Save to database
                db = SessionLocal()
                try:
                    records = fetcher._save_to_database(db, data, interval)
                    fetcher._update_checkpoint(db, sym['symbol'], sym['exchange'], interval, data)
                    result = {'status': 'success', 'records': records}
                finally:
                    db.close()
            
            if result.get('status') == 'success':
                results['successful'] += 1
                results['total_records'] += result.get('records', 0)
            elif result.get('status') == 'up_to_date':
                results['successful'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append({
                'symbol': sym['symbol'],
                **result
            })
            
        except Exception as e:
            logger.error(f"Error processing {sym['symbol']}: {e}")
            results['failed'] += 1
            results['details'].append({
                'symbol': sym['symbol'],
                'status': 'error',
                'error': str(e)
            })
        
        # Rate limiting between symbols
        await asyncio.sleep(0.5)
    
    logger.info(f"Fetch complete: {results['successful']}/{results['total_symbols']} successful, "
               f"{results['total_records']} total records")
    
    return results



def generate_mock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str = 'ONE_DAY',
    exchange: str = 'NSE'
) -> List[Dict]:
    """
    Generate mock OHLCV data for testing purposes
    
    Args:
        symbol: Stock symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        interval: Data interval
        exchange: Exchange name
    
    Returns:
        List of mock OHLCV data points
    """
    logger.warning(f"Generating mock data for {symbol} from {start_date} to {end_date}")
    
    try:
        # Convert string dates to datetime objects
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Validate dates
        if start_date_obj > end_date_obj:
            raise ValueError("Start date cannot be after end date")
        
        # Generate mock data
        data = []
        current_date = start_date_obj
        base_price = random.uniform(100, 500)
        
        while current_date <= end_date_obj:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday to Friday
                
                if interval in ['ONE_MINUTE', 'FIVE_MINUTE', 'FIFTEEN_MINUTE', 'THIRTY_MINUTE']:
                    # For minute data, generate multiple points per day
                    market_open = datetime.combine(current_date.date(), datetime.strptime('09:15', '%H:%M').time())
                    market_close = datetime.combine(current_date.date(), datetime.strptime('15:30', '%H:%M').time())
                    
                    # Determine minutes to increment based on interval
                    minute_map = {
                        'ONE_MINUTE': 1,
                        'FIVE_MINUTE': 5,
                        'FIFTEEN_MINUTE': 15,
                        'THIRTY_MINUTE': 30
                    }
                    minute_increment = minute_map.get(interval, 5)
                    
                    current_time = market_open
                    while current_time <= market_close:
                        # Simulate price movement
                        price_change = random.uniform(-2, 2)
                        current_price = base_price + price_change
                        
                        # Generate OHLCV data
                        open_price = current_price
                        high_price = current_price * random.uniform(1, 1.01)
                        low_price = current_price * random.uniform(0.99, 1)
                        close_price = current_price * random.uniform(0.995, 1.005)
                        volume = int(random.uniform(1000, 10000))
                        
                        data.append({
                            'symbol': symbol,
                            'exchange': exchange,
                            'interval': interval,
                            'date': current_date.date(),
                            'time': current_time.time(),
                            'open': round(open_price, 2),
                            'high': round(high_price, 2),
                            'low': round(low_price, 2),
                            'close': round(close_price, 2),
                            'volume': volume
                        })
                        
                        # Update base price
                        base_price = close_price
                        
                        # Increment time
                        current_time += timedelta(minutes=minute_increment)
                
                elif interval == 'ONE_HOUR':
                    # For hourly data, generate points for each hour of the trading day
                    for hour in range(9, 16):
                        # Simulate price movement
                        price_change = random.uniform(-5, 5)
                        current_price = base_price + price_change
                        
                        # Generate OHLCV data
                        open_price = current_price
                        high_price = current_price * random.uniform(1, 1.02)
                        low_price = current_price * random.uniform(0.98, 1)
                        close_price = current_price * random.uniform(0.99, 1.01)
                        volume = int(random.uniform(10000, 100000))
                        
                        data.append({
                            'symbol': symbol,
                            'exchange': exchange,
                            'interval': interval,
                            'date': current_date.date(),
                            'time': datetime.strptime(f'{hour}:00', '%H:%M').time(),
                            'open': round(open_price, 2),
                            'high': round(high_price, 2),
                            'low': round(low_price, 2),
                            'close': round(close_price, 2),
                            'volume': volume
                        })
                        
                        # Update base price
                        base_price = close_price
                
                else:  # Daily data (ONE_DAY)
                    # Simulate price movement
                    price_change = random.uniform(-10, 10)
                    current_price = base_price + price_change
                    
                    # Generate OHLCV data
                    open_price = current_price
                    high_price = current_price * random.uniform(1, 1.03)
                    low_price = current_price * random.uniform(0.97, 1)
                    close_price = current_price * random.uniform(0.98, 1.02)
                    volume = int(random.uniform(100000, 1000000))
                    
                    data.append({
                        'symbol': symbol,
                        'exchange': exchange,
                        'interval': interval,
                        'date': current_date.date(),
                        'time': None,  # No specific time for daily data
                        'open': round(open_price, 2),
                        'high': round(high_price, 2),
                        'low': round(low_price, 2),
                        'close': round(close_price, 2),
                        'volume': volume
                    })
                    
                    # Update base price
                    base_price = close_price
            
            # Move to the next day
            current_date += timedelta(days=1)
        
        return data
        
    except Exception as e:
        logger.error(f"Error generating mock data for {symbol}: {str(e)}")
        raise


async def fetch_realtime_quotes(
    angel_client,
    symbols: List[Dict],
    batch_size: int = 10
) -> List[Dict]:
    """
    Fetch real-time quotes for a list of symbols from Angel One API
    
    Args:
        angel_client: Angel One SmartConnect client
        symbols: List of dicts with symbol, token, exchange
        batch_size: Number of symbols per batch (default 10)
    
    Returns:
        List of quote data for each symbol
    """
    quotes = []
    
    if not angel_client:
        logger.error("Cannot fetch quotes: Angel client not initialized")
        raise ValueError("Angel client not initialized")
    
    # Process in batches
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        logger.info(f"Processing quote batch {i // batch_size + 1} ({len(batch)} symbols)")
        
        for sym in batch:
            try:
                await rate_limiter.wait()
                
                # Fetch LTP from Angel One
                ltp_data = angel_client.ltpData(
                    exchange=sym['exchange'],
                    tradingsymbol=sym['symbol'],
                    symboltoken=sym['token']
                )
                
                if ltp_data and ltp_data.get('status'):
                    data = ltp_data.get('data', {})
                    
                    ltp = float(data.get('ltp', 0))
                    open_price = float(data.get('open', ltp))
                    close_price = float(data.get('close', ltp))
                    
                    # Calculate change percentage
                    if close_price > 0:
                        change_percent = ((ltp - close_price) / close_price) * 100
                    else:
                        change_percent = 0
                    
                    quotes.append({
                        'symbol': sym['symbol'],
                        'token': sym['token'],
                        'exchange': sym['exchange'],
                        'ltp': ltp,
                        'open': open_price,
                        'high': float(data.get('high', ltp)),
                        'low': float(data.get('low', ltp)),
                        'close': close_price,
                        'change': round(ltp - close_price, 2),
                        'change_percent': round(change_percent, 2),
                        'volume': int(data.get('volume', 0)),
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    logger.warning(f"No LTP data for {sym['symbol']}")
                    quotes.append(get_fallback_quote(sym))
                    
            except Exception as e:
                logger.error(f"Error fetching quote for {sym['symbol']}: {str(e)}")
                quotes.append(get_fallback_quote(sym))
        
        # Wait between batches
        if i + batch_size < len(symbols):
            await asyncio.sleep(1.0)
    
    return quotes


def get_fallback_quote(sym: Dict) -> Dict:
    """Generate fallback quote data when API is not available"""
    base_price = random.uniform(100, 500)
    change_percent = random.uniform(-3, 3)
    
    return {
        'symbol': sym.get('symbol', 'UNKNOWN'),
        'token': sym.get('token', ''),
        'exchange': sym.get('exchange', 'NSE'),
        'ltp': round(base_price, 2),
        'open': round(base_price * 0.99, 2),
        'high': round(base_price * 1.02, 2),
        'low': round(base_price * 0.98, 2),
        'close': round(base_price, 2),
        'change': round(base_price * change_percent / 100, 2),
        'change_percent': round(change_percent, 2),
        'volume': int(random.uniform(10000, 1000000)),
        'timestamp': datetime.now().isoformat(),
        'is_mock': True
    }


def fetch_historical_data_sync(
    angel_client,
    symbol: str,
    token: str,
    exchange: str,
    start_date: str,
    end_date: str,
    interval: str = 'ONE_DAY'
) -> List[Dict]:
    """
    Synchronous version of historical data fetch (for non-async contexts)
    
    Args:
        angel_client: Angel One SmartConnect client
        symbol: Stock symbol
        token: Instrument token
        exchange: Exchange name
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Data interval
    
    Returns:
        List of OHLCV data points
    """
    if not angel_client:
        logger.warning(f"No angel client, generating mock data for {symbol}")
        return generate_mock_data(symbol, start_date, end_date, interval, exchange)
    
    try:
        # Format dates for Angel One API
        from_date_str = f"{start_date} 09:15"
        to_date_str = f"{end_date} 15:30"
        
        # Call Angel One historical data API
        historic_params = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": convert_interval_format(interval),
            "fromdate": from_date_str,
            "todate": to_date_str
        }
        
        response = angel_client.getCandleData(historic_params)
        
        if response and response.get('status'):
            data = response.get('data', [])
            
            parsed_data = []
            for candle in data:
                try:
                    # Angel One returns: [timestamp, open, high, low, close, volume]
                    timestamp = datetime.strptime(candle[0], '%Y-%m-%dT%H:%M:%S%z')
                    
                    parsed_data.append({
                        'symbol': symbol,
                        'exchange': exchange,
                        'interval': interval,
                        'date': timestamp.date(),
                        'time': timestamp.time() if interval != 'ONE_DAY' else None,
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': int(candle[5]) if len(candle) > 5 else 0
                    })
                except Exception as e:
                    logger.error(f"Error parsing candle: {e}")
                    continue
            
            logger.info(f"Fetched {len(parsed_data)} records for {symbol}")
            return parsed_data
        else:
            logger.warning(f"API returned error for {symbol}: {response}")
            return generate_mock_data(symbol, start_date, end_date, interval, exchange)
            
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return generate_mock_data(symbol, start_date, end_date, interval, exchange)
