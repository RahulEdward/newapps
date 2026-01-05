"""
Historical Data Manager - Historify Style
Downloads, validates, and manages OHLCV data from Angel One
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import pandas as pd
import time
import logging

from .models import OHLCData, DataDownloadStatus, DataQualityLog

logger = logging.getLogger(__name__)


# Angel One Timeframe Mappings
TIMEFRAME_MAP = {
    "ONE_MINUTE": "ONE_MINUTE",
    "THREE_MINUTE": "THREE_MINUTE",
    "FIVE_MINUTE": "FIVE_MINUTE",
    "TEN_MINUTE": "TEN_MINUTE",
    "FIFTEEN_MINUTE": "FIFTEEN_MINUTE",
    "THIRTY_MINUTE": "THIRTY_MINUTE",
    "ONE_HOUR": "ONE_HOUR",
    "ONE_DAY": "ONE_DAY"
}

# Max candles per Angel One API request
MAX_CANDLES_PER_REQUEST = 1000

# Rate limiting: 3 requests per second
RATE_LIMIT_DELAY = 0.35  # seconds between requests


class RateLimiter:
    """Token bucket rate limiter for Angel One API"""
    
    def __init__(self, requests_per_second: float = 3.0):
        self.rate = requests_per_second
        self.tokens = requests_per_second
        self.last_update = time.time()
        self.max_tokens = requests_per_second
    
    async def acquire(self):
        """Wait until a request can be made"""
        while True:
            now = time.time()
            time_passed = now - self.last_update
            self.tokens = min(self.max_tokens, self.tokens + time_passed * self.rate)
            self.last_update = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return
            
            wait_time = (1 - self.tokens) / self.rate
            await asyncio.sleep(wait_time)


class HistoricalDataManager:
    """
    Main class for managing historical OHLCV data
    Implements Historify-style data management
    """
    
    def __init__(self, db: Session, angel_client=None):
        self.db = db
        self.angel_client = angel_client
        self.rate_limiter = RateLimiter(3.0)
        self._download_progress = {}
    
    def get_download_status(self, symbol: str, timeframe: str) -> Optional[DataDownloadStatus]:
        """Get download status for a symbol/timeframe"""
        return self.db.query(DataDownloadStatus).filter(
            and_(
                DataDownloadStatus.symbol == symbol,
                DataDownloadStatus.timeframe == timeframe
            )
        ).first()
    
    def get_all_download_status(self) -> List[DataDownloadStatus]:
        """Get all download statuses"""
        return self.db.query(DataDownloadStatus).order_by(
            DataDownloadStatus.updated_at.desc()
        ).all()
    
    def get_data_coverage_stats(self) -> Dict:
        """Get overall data coverage statistics"""
        total_symbols = self.db.query(func.count(func.distinct(OHLCData.symbol))).scalar() or 0
        total_records = self.db.query(func.count(OHLCData.id)).scalar() or 0
        
        # Get status counts
        status_counts = self.db.query(
            DataDownloadStatus.status,
            func.count(DataDownloadStatus.id)
        ).group_by(DataDownloadStatus.status).all()
        
        status_dict = {status: count for status, count in status_counts}
        
        # Get timeframe distribution
        timeframe_counts = self.db.query(
            OHLCData.timeframe,
            func.count(OHLCData.id)
        ).group_by(OHLCData.timeframe).all()
        
        return {
            "total_symbols": total_symbols,
            "total_records": total_records,
            "status_breakdown": status_dict,
            "timeframe_distribution": {tf: count for tf, count in timeframe_counts},
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime = None,
        to_date: datetime = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch historical data from database as pandas DataFrame
        """
        query = self.db.query(OHLCData).filter(
            and_(
                OHLCData.symbol == symbol,
                OHLCData.timeframe == timeframe
            )
        )
        
        if from_date:
            query = query.filter(OHLCData.timestamp >= from_date)
        if to_date:
            query = query.filter(OHLCData.timestamp <= to_date)
        
        query = query.order_by(OHLCData.timestamp.desc()).limit(limit)
        records = query.all()
        
        if not records:
            return pd.DataFrame()
        
        data = [{
            'timestamp': r.timestamp,
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume,
            'oi': r.oi
        } for r in records]
        
        df = pd.DataFrame(data)
        df = df.sort_values('timestamp').reset_index(drop=True)
        return df
    
    async def download_historical_data(
        self,
        symbol: str,
        token: str,
        exchange: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime,
        client_code: str
    ) -> Dict:
        """
        Download historical data from Angel One API
        Implements pagination and rate limiting
        """
        if not self.angel_client:
            return {"status": "error", "message": "Angel One client not initialized"}
        
        # Create or update status record
        status = self.get_download_status(symbol, timeframe)
        if not status:
            status = DataDownloadStatus(
                symbol=symbol,
                token=token,
                exchange=exchange,
                timeframe=timeframe,
                status='downloading',
                first_date=from_date,
                last_date=to_date
            )
            self.db.add(status)
        else:
            status.status = 'downloading'
            status.error_message = None
        
        self.db.commit()
        
        try:
            total_downloaded = 0
            current_from = from_date
            start_time = time.time()
            
            while current_from < to_date:
                # Rate limiting
                await self.rate_limiter.acquire()
                
                # Calculate chunk end date based on timeframe
                chunk_to = min(current_from + timedelta(days=30), to_date)
                
                # Call Angel One Historical API
                candles = await self._fetch_candles_from_api(
                    token=token,
                    exchange=exchange,
                    timeframe=timeframe,
                    from_date=current_from,
                    to_date=chunk_to
                )
                
                if candles:
                    # Bulk insert candles
                    self._bulk_insert_candles(symbol, token, exchange, timeframe, candles)
                    total_downloaded += len(candles)
                    
                    # Update progress
                    elapsed = time.time() - start_time
                    status.progress_percent = min(
                        ((chunk_to - from_date).total_seconds() / 
                         (to_date - from_date).total_seconds()) * 100,
                        100
                    )
                    status.download_speed = total_downloaded / elapsed if elapsed > 0 else 0
                    status.total_records = total_downloaded
                    self.db.commit()
                
                current_from = chunk_to
            
            # Mark as completed
            status.status = 'completed'
            status.last_updated = datetime.utcnow()
            status.progress_percent = 100
            self.db.commit()
            
            # Run data validation
            self._validate_downloaded_data(symbol, timeframe)
            
            return {
                "status": "success",
                "symbol": symbol,
                "timeframe": timeframe,
                "records_downloaded": total_downloaded
            }
            
        except Exception as e:
            logger.error(f"Download failed for {symbol}: {str(e)}")
            status.status = 'failed'
            status.error_message = str(e)
            self.db.commit()
            return {"status": "error", "message": str(e)}
    
    async def _fetch_candles_from_api(
        self,
        token: str,
        exchange: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict]:
        """
        Fetch candles from Angel One Historical Data API
        """
        if not self.angel_client or not self.angel_client.jwt_token:
            return []
        
        url = f"{self.angel_client.BASE_URL}/rest/secure/angelbroking/historical/v1/getCandleData"
        
        payload = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": timeframe,
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M")
        }
        
        try:
            import requests
            response = requests.post(
                url,
                headers=self.angel_client._get_headers(),
                json=payload
            )
            data = response.json()
            
            if data.get('status') and data.get('data'):
                # Parse candles: [timestamp, open, high, low, close, volume]
                candles = []
                for candle in data['data']:
                    candles.append({
                        'timestamp': datetime.strptime(candle[0], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None),
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': int(candle[5]) if len(candle) > 5 else 0
                    })
                return candles
            return []
        except Exception as e:
            logger.error(f"API fetch error: {str(e)}")
            return []
    
    def _bulk_insert_candles(
        self,
        symbol: str,
        token: str,
        exchange: str,
        timeframe: str,
        candles: List[Dict]
    ):
        """Bulk insert candles with duplicate handling"""
        for candle in candles:
            # Check for existing record
            existing = self.db.query(OHLCData).filter(
                and_(
                    OHLCData.symbol == symbol,
                    OHLCData.timeframe == timeframe,
                    OHLCData.timestamp == candle['timestamp']
                )
            ).first()
            
            if not existing:
                record = OHLCData(
                    symbol=symbol,
                    token=token,
                    exchange=exchange,
                    timeframe=timeframe,
                    timestamp=candle['timestamp'],
                    open=candle['open'],
                    high=candle['high'],
                    low=candle['low'],
                    close=candle['close'],
                    volume=candle['volume'],
                    oi=candle.get('oi', 0)
                )
                self.db.add(record)
        
        self.db.commit()
    
    def _validate_downloaded_data(self, symbol: str, timeframe: str):
        """
        Validate downloaded data for quality issues
        Historify-style data validation
        """
        # Get recent data
        records = self.db.query(OHLCData).filter(
            and_(
                OHLCData.symbol == symbol,
                OHLCData.timeframe == timeframe
            )
        ).order_by(OHLCData.timestamp).all()
        
        if not records:
            return
        
        issues = []
        completeness = 100.0
        accuracy = 100.0
        
        for i, record in enumerate(records):
            # OHLC validation
            if not (record.low <= record.open <= record.high and
                    record.low <= record.close <= record.high):
                issues.append({
                    'type': 'ohlc_validation',
                    'severity': 'warning',
                    'message': f"Invalid OHLC at {record.timestamp}: O={record.open}, H={record.high}, L={record.low}, C={record.close}"
                })
                accuracy -= 0.5
            
            # Zero/negative value check
            if any(v <= 0 for v in [record.open, record.high, record.low, record.close]):
                issues.append({
                    'type': 'invalid_values',
                    'severity': 'error',
                    'message': f"Zero or negative values at {record.timestamp}"
                })
                accuracy -= 1.0
            
            # Gap detection (for minute data)
            if i > 0 and timeframe in ['ONE_MINUTE', 'FIVE_MINUTE']:
                expected_gap = timedelta(minutes=1 if timeframe == 'ONE_MINUTE' else 5)
                actual_gap = record.timestamp - records[i-1].timestamp
                
                # Allow for market hours gaps
                if actual_gap > expected_gap * 2 and actual_gap < timedelta(hours=18):
                    issues.append({
                        'type': 'gap_detection',
                        'severity': 'info',
                        'message': f"Data gap detected: {records[i-1].timestamp} to {record.timestamp}"
                    })
                    completeness -= 0.1
        
        # Log quality issues
        for issue in issues[:10]:  # Log first 10 issues
            log = DataQualityLog(
                symbol=symbol,
                token=records[0].token if records else '',
                timeframe=timeframe,
                check_type=issue['type'],
                severity=issue['severity'],
                message=issue['message'],
                completeness_score=max(0, completeness),
                accuracy_score=max(0, accuracy)
            )
            self.db.add(log)
        
        self.db.commit()
    
    def get_quality_logs(self, symbol: str = None, limit: int = 100) -> List[DataQualityLog]:
        """Get data quality logs"""
        query = self.db.query(DataQualityLog)
        if symbol:
            query = query.filter(DataQualityLog.symbol == symbol)
        return query.order_by(DataQualityLog.checked_at.desc()).limit(limit).all()
    
    def delete_data(self, symbol: str, timeframe: str = None) -> int:
        """Delete historical data for a symbol"""
        query = self.db.query(OHLCData).filter(OHLCData.symbol == symbol)
        if timeframe:
            query = query.filter(OHLCData.timeframe == timeframe)
        
        count = query.count()
        query.delete()
        
        # Also delete status
        status_query = self.db.query(DataDownloadStatus).filter(
            DataDownloadStatus.symbol == symbol
        )
        if timeframe:
            status_query = status_query.filter(DataDownloadStatus.timeframe == timeframe)
        status_query.delete()
        
        self.db.commit()
        return count
