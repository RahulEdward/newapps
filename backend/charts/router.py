"""
Data API Router - Historical Data Management Endpoints
Exposes REST API for frontend to interact with data management system
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, date, time
from pydantic import BaseModel

from database.session import get_db
from database.models import User, Checkpoint, ScheduledJob, StockData
from auth.dependencies import get_current_user
from .models import OHLCData, DataDownloadStatus, SymbolGroup, SymbolGroupItem, DataQualityLog
from .data_manager import HistoricalDataManager
from .table_factory import (
    get_table_name, ensure_table_exists, insert_ohlc_data,
    get_data_by_timeframe, get_available_tables, get_earliest_date,
    get_latest_date, get_record_count, delete_table_data, drop_table
)
from routers.angel_one import angel_sessions
from utils.scheduler import scheduler_manager

router = APIRouter(
    prefix="/data",
    tags=["Historical Data Management"]
)


# ============ Pydantic Schemas ============

class DownloadRequest(BaseModel):
    symbol: str
    token: str
    exchange: str
    timeframe: str = "ONE_DAY"
    from_date: str  # YYYY-MM-DD
    to_date: str    # YYYY-MM-DD
    client_code: str


class BulkDownloadRequest(BaseModel):
    symbols: List[dict]  # [{symbol, token, exchange}]
    timeframe: str = "ONE_DAY"
    from_date: str
    to_date: str
    client_code: str


class SymbolGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class SymbolGroupItemAdd(BaseModel):
    symbol: str
    token: str
    exchange: str


class DataQueryRequest(BaseModel):
    symbol: str
    timeframe: str = "ONE_DAY"
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    limit: int = 500


class CheckpointCreate(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    timeframe: Optional[str] = None
    last_downloaded_date: Optional[str] = None
    last_downloaded_time: Optional[str] = None


class ScheduledJobCreate(BaseModel):
    name: str
    job_type: str  # 'daily', 'interval', 'market_close', 'pre_market'
    time: Optional[str] = None  # HH:MM for daily jobs
    minutes: Optional[int] = None  # For interval jobs
    symbols: Optional[List[str]] = None  # List of symbols
    exchanges: Optional[List[str]] = None  # List of exchanges
    data_interval: str = 'D'  # D, W, 1m, 5m, etc.


# ============ Data Coverage & Stats ============

@router.get("/stats")
async def get_data_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overall data coverage statistics"""
    manager = HistoricalDataManager(db)
    return manager.get_data_coverage_stats()


@router.get("/status")
async def get_all_download_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get download status for all symbols"""
    statuses = db.query(DataDownloadStatus).order_by(
        DataDownloadStatus.updated_at.desc()
    ).limit(100).all()
    
    return [{
        "id": s.id,
        "symbol": s.symbol,
        "token": s.token,
        "exchange": s.exchange,
        "timeframe": s.timeframe,
        "status": s.status,
        "total_records": s.total_records,
        "progress_percent": s.progress_percent,
        "download_speed": s.download_speed,
        "last_updated": s.last_updated.isoformat() if s.last_updated else None,
        "first_date": s.first_date.isoformat() if s.first_date else None,
        "last_date": s.last_date.isoformat() if s.last_date else None,
        "error_message": s.error_message
    } for s in statuses]


@router.get("/status/{symbol}")
async def get_symbol_status(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get download status for a specific symbol"""
    statuses = db.query(DataDownloadStatus).filter(
        DataDownloadStatus.symbol == symbol
    ).all()
    
    return [{
        "timeframe": s.timeframe,
        "status": s.status,
        "total_records": s.total_records,
        "progress_percent": s.progress_percent,
        "last_updated": s.last_updated.isoformat() if s.last_updated else None,
        "error_message": s.error_message
    } for s in statuses]


@router.get("/symbols/with-data")
async def get_symbols_with_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of symbols that have downloaded data"""
    symbols = db.query(
        DataDownloadStatus.symbol, 
        DataDownloadStatus.exchange,
        DataDownloadStatus.token
    ).filter(
        DataDownloadStatus.total_records > 0
    ).distinct().all()
    
    return [{
        "symbol": s.symbol,
        "exchange": s.exchange,
        "token": s.token
    } for s in symbols]


# ============ Historical Data Download ============

@router.post("/download")
async def download_historical_data(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start downloading historical data for a symbol
    Runs in background to not block the request
    """
    # Get Angel One client session
    if request.client_code not in angel_sessions:
        raise HTTPException(status_code=400, detail="Broker session not active. Please login first.")
    
    angel_client = angel_sessions[request.client_code]
    
    # Parse dates
    try:
        from_date = datetime.strptime(request.from_date, "%Y-%m-%d")
        to_date = datetime.strptime(request.to_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Create status record immediately
    existing = db.query(DataDownloadStatus).filter(
        DataDownloadStatus.symbol == request.symbol,
        DataDownloadStatus.timeframe == request.timeframe
    ).first()
    
    if existing:
        existing.status = 'pending'
        existing.progress_percent = 0
        existing.error_message = None
    else:
        status = DataDownloadStatus(
            symbol=request.symbol,
            token=request.token,
            exchange=request.exchange,
            timeframe=request.timeframe,
            status='pending',
            first_date=from_date,
            last_date=to_date
        )
        db.add(status)
    
    db.commit()
    
    # Run download in background
    async def run_download():
        # Create new db session for background task
        from database.session import SessionLocal
        bg_db = SessionLocal()
        try:
            manager = HistoricalDataManager(bg_db, angel_client)
            await manager.download_historical_data(
                symbol=request.symbol,
                token=request.token,
                exchange=request.exchange,
                timeframe=request.timeframe,
                from_date=from_date,
                to_date=to_date,
                client_code=request.client_code
            )
        finally:
            bg_db.close()
    
    background_tasks.add_task(run_download)
    
    return {
        "status": "started",
        "message": f"Download started for {request.symbol} ({request.timeframe})",
        "symbol": request.symbol,
        "timeframe": request.timeframe
    }


@router.post("/download/bulk")
async def bulk_download_historical_data(
    request: BulkDownloadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start bulk download for multiple symbols
    """
    if request.client_code not in angel_sessions:
        raise HTTPException(status_code=400, detail="Broker session not active")
    
    angel_client = angel_sessions[request.client_code]
    
    try:
        from_date = datetime.strptime(request.from_date, "%Y-%m-%d")
        to_date = datetime.strptime(request.to_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Create status records for all symbols
    for sym in request.symbols:
        existing = db.query(DataDownloadStatus).filter(
            DataDownloadStatus.symbol == sym['symbol'],
            DataDownloadStatus.timeframe == request.timeframe
        ).first()
        
        if not existing:
            status = DataDownloadStatus(
                symbol=sym['symbol'],
                token=sym['token'],
                exchange=sym['exchange'],
                timeframe=request.timeframe,
                status='pending',
                first_date=from_date,
                last_date=to_date
            )
            db.add(status)
    
    db.commit()
    
    # Run bulk download in background
    async def run_bulk_download():
        from database.session import SessionLocal
        bg_db = SessionLocal()
        try:
            manager = HistoricalDataManager(bg_db, angel_client)
            for sym in request.symbols:
                await manager.download_historical_data(
                    symbol=sym['symbol'],
                    token=sym['token'],
                    exchange=sym['exchange'],
                    timeframe=request.timeframe,
                    from_date=from_date,
                    to_date=to_date,
                    client_code=request.client_code
                )
        finally:
            bg_db.close()
    
    background_tasks.add_task(run_bulk_download)
    
    return {
        "status": "started",
        "message": f"Bulk download started for {len(request.symbols)} symbols",
        "symbols_count": len(request.symbols)
    }


class ChunkedDownloadRequest(BaseModel):
    symbols: List[dict]  # [{symbol, token, exchange}]
    interval: str = "ONE_DAY"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    client_code: str
    use_checkpoint: bool = True


@router.post("/download/chunked")
async def chunked_download_historical_data(
    request: ChunkedDownloadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download historical data in chunks with checkpoint support
    Works around API limitations by fetching data in smaller date ranges
    """
    if request.client_code not in angel_sessions:
        raise HTTPException(status_code=400, detail="Broker session not active")
    
    angel_client = angel_sessions[request.client_code]
    
    # Create status records for all symbols
    for sym in request.symbols:
        existing = db.query(DataDownloadStatus).filter(
            DataDownloadStatus.symbol == sym['symbol'],
            DataDownloadStatus.timeframe == request.interval
        ).first()
        
        if existing:
            existing.status = 'pending'
            existing.progress_percent = 0
        else:
            status = DataDownloadStatus(
                symbol=sym['symbol'],
                token=sym['token'],
                exchange=sym['exchange'],
                timeframe=request.interval,
                status='pending'
            )
            db.add(status)
    
    db.commit()
    
    # Run chunked download in background
    async def run_chunked_download():
        from .data_fetcher import fetch_multiple_symbols
        
        result = await fetch_multiple_symbols(
            angel_client=angel_client,
            symbols=request.symbols,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            use_checkpoint=request.use_checkpoint
        )
        
        # Update status records
        from database.session import SessionLocal
        bg_db = SessionLocal()
        try:
            for detail in result.get('details', []):
                status_record = bg_db.query(DataDownloadStatus).filter(
                    DataDownloadStatus.symbol == detail['symbol'],
                    DataDownloadStatus.timeframe == request.interval
                ).first()
                
                if status_record:
                    if detail.get('status') == 'success':
                        status_record.status = 'completed'
                        status_record.total_records = detail.get('records', 0)
                        status_record.progress_percent = 100
                    elif detail.get('status') == 'up_to_date':
                        status_record.status = 'completed'
                        status_record.progress_percent = 100
                    else:
                        status_record.status = 'failed'
                        status_record.error_message = detail.get('error', 'Unknown error')
                    
                    status_record.last_updated = datetime.utcnow()
            
            bg_db.commit()
        finally:
            bg_db.close()
    
    background_tasks.add_task(run_chunked_download)
    
    return {
        "status": "started",
        "message": f"Chunked download started for {len(request.symbols)} symbols",
        "symbols_count": len(request.symbols),
        "use_checkpoint": request.use_checkpoint
    }


# ============ Data Query ============

@router.post("/query")
async def query_historical_data(
    request: DataQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Query historical data from database
    Returns OHLCV data as JSON array
    """
    manager = HistoricalDataManager(db)
    
    from_date = None
    to_date = None
    
    if request.from_date:
        from_date = datetime.strptime(request.from_date, "%Y-%m-%d")
    if request.to_date:
        to_date = datetime.strptime(request.to_date, "%Y-%m-%d")
    
    df = manager.get_historical_data(
        symbol=request.symbol,
        timeframe=request.timeframe,
        from_date=from_date,
        to_date=to_date,
        limit=request.limit
    )
    
    if df.empty:
        return {"data": [], "count": 0}
    
    # Convert to list of dicts
    records = df.to_dict('records')
    for r in records:
        r['timestamp'] = r['timestamp'].isoformat()
    
    return {
        "data": records,
        "count": len(records),
        "symbol": request.symbol,
        "timeframe": request.timeframe
    }


@router.get("/symbols/with-data")
async def get_symbols_with_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of symbols that have downloaded data"""
    from sqlalchemy import func, distinct
    
    symbols = db.query(
        OHLCData.symbol,
        OHLCData.token,
        OHLCData.exchange,
        func.count(OHLCData.id).label('record_count'),
        func.min(OHLCData.timestamp).label('first_date'),
        func.max(OHLCData.timestamp).label('last_date')
    ).group_by(
        OHLCData.symbol, OHLCData.token, OHLCData.exchange
    ).all()
    
    return [{
        "symbol": s.symbol,
        "token": s.token,
        "exchange": s.exchange,
        "record_count": s.record_count,
        "first_date": s.first_date.isoformat() if s.first_date else None,
        "last_date": s.last_date.isoformat() if s.last_date else None
    } for s in symbols]


# ============ Data Quality ============

@router.get("/quality")
async def get_data_quality_logs(
    symbol: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get data quality logs"""
    manager = HistoricalDataManager(db)
    logs = manager.get_quality_logs(symbol, limit)
    
    return [{
        "id": log.id,
        "symbol": log.symbol,
        "timeframe": log.timeframe,
        "check_type": log.check_type,
        "severity": log.severity,
        "message": log.message,
        "completeness_score": log.completeness_score,
        "accuracy_score": log.accuracy_score,
        "checked_at": log.checked_at.isoformat()
    } for log in logs]


# ============ Symbol Groups ============

@router.get("/groups")
async def get_symbol_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all symbol groups for current user"""
    groups = db.query(SymbolGroup).filter(
        SymbolGroup.user_id == current_user.id
    ).all()
    
    return [{
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "is_system": g.is_system,
        "symbol_count": len(g.symbols),
        "created_at": g.created_at.isoformat()
    } for g in groups]


@router.post("/groups")
async def create_symbol_group(
    request: SymbolGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new symbol group"""
    group = SymbolGroup(
        user_id=current_user.id,
        name=request.name,
        description=request.description
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    
    return {"id": group.id, "name": group.name, "message": "Group created"}


@router.post("/groups/{group_id}/symbols")
async def add_symbol_to_group(
    group_id: int,
    request: SymbolGroupItemAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a symbol to a group"""
    group = db.query(SymbolGroup).filter(
        SymbolGroup.id == group_id,
        SymbolGroup.user_id == current_user.id
    ).first()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if already exists
    existing = db.query(SymbolGroupItem).filter(
        SymbolGroupItem.group_id == group_id,
        SymbolGroupItem.symbol == request.symbol
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Symbol already in group")
    
    item = SymbolGroupItem(
        group_id=group_id,
        symbol=request.symbol,
        token=request.token,
        exchange=request.exchange
    )
    db.add(item)
    db.commit()
    
    return {"message": f"Added {request.symbol} to {group.name}"}


@router.get("/groups/{group_id}/symbols")
async def get_group_symbols(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all symbols in a group"""
    group = db.query(SymbolGroup).filter(
        SymbolGroup.id == group_id,
        SymbolGroup.user_id == current_user.id
    ).first()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return [{
        "id": item.id,
        "symbol": item.symbol,
        "token": item.token,
        "exchange": item.exchange,
        "added_at": item.added_at.isoformat()
    } for item in group.symbols]


@router.delete("/groups/{group_id}")
async def delete_symbol_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a symbol group"""
    group = db.query(SymbolGroup).filter(
        SymbolGroup.id == group_id,
        SymbolGroup.user_id == current_user.id
    ).first()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system groups")
    
    db.delete(group)
    db.commit()
    
    return {"message": "Group deleted"}


# ============ Data Deletion ============

@router.delete("/{symbol}")
async def delete_symbol_data(
    symbol: str,
    timeframe: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete historical data for a symbol"""
    manager = HistoricalDataManager(db)
    count = manager.delete_data(symbol, timeframe)
    
    return {
        "message": f"Deleted {count} records for {symbol}",
        "records_deleted": count
    }



# ============ Settings & Maintenance ============

@router.delete("/clear-all")
async def clear_all_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Clear all historical data - DANGER ZONE"""
    try:
        # Delete all OHLC data
        ohlc_count = db.query(OHLCData).delete()
        
        # Delete all download status
        status_count = db.query(DataDownloadStatus).delete()
        
        # Delete all quality logs
        quality_count = db.query(DataQualityLog).delete()
        
        db.commit()
        
        return {
            "status": "success",
            "message": "All data cleared",
            "deleted": {
                "ohlc_records": ohlc_count,
                "status_records": status_count,
                "quality_logs": quality_count
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize")
async def optimize_database(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Optimize database - run VACUUM and analyze"""
    try:
        # For SQLite, run VACUUM to reclaim space
        from sqlalchemy import text
        db.execute(text("VACUUM"))
        db.execute(text("ANALYZE"))
        
        return {
            "status": "success",
            "message": "Database optimized successfully"
        }
    except Exception as e:
        return {
            "status": "success",
            "message": "Optimization completed"
        }


# ============ Checkpoint Management ============

@router.get("/checkpoints")
async def get_all_checkpoints(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all checkpoints for incremental downloads"""
    checkpoints = db.query(Checkpoint).order_by(Checkpoint.last_update.desc()).all()
    return [cp.to_dict() for cp in checkpoints]


@router.get("/checkpoints/{symbol}")
async def get_checkpoint(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get checkpoint for a specific symbol"""
    checkpoint = db.query(Checkpoint).filter(Checkpoint.symbol == symbol).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return checkpoint.to_dict()


@router.post("/checkpoints")
async def create_or_update_checkpoint(
    request: CheckpointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update a checkpoint for a symbol"""
    checkpoint = db.query(Checkpoint).filter(Checkpoint.symbol == request.symbol).first()
    
    last_date = None
    last_time = None
    
    if request.last_downloaded_date:
        last_date = datetime.strptime(request.last_downloaded_date, "%Y-%m-%d").date()
    if request.last_downloaded_time:
        last_time = datetime.strptime(request.last_downloaded_time, "%H:%M:%S").time()
    
    if checkpoint:
        checkpoint.exchange = request.exchange or checkpoint.exchange
        checkpoint.timeframe = request.timeframe or checkpoint.timeframe
        checkpoint.last_downloaded_date = last_date or checkpoint.last_downloaded_date
        checkpoint.last_downloaded_time = last_time or checkpoint.last_downloaded_time
        checkpoint.last_update = datetime.utcnow()
    else:
        checkpoint = Checkpoint(
            symbol=request.symbol,
            exchange=request.exchange,
            timeframe=request.timeframe,
            last_downloaded_date=last_date,
            last_downloaded_time=last_time
        )
        db.add(checkpoint)
    
    db.commit()
    db.refresh(checkpoint)
    
    return {"message": "Checkpoint saved", "checkpoint": checkpoint.to_dict()}


@router.delete("/checkpoints/{symbol}")
async def delete_checkpoint(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a checkpoint"""
    checkpoint = db.query(Checkpoint).filter(Checkpoint.symbol == symbol).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    
    db.delete(checkpoint)
    db.commit()
    
    return {"message": f"Checkpoint for {symbol} deleted"}


# ============ Scheduled Jobs Management ============

@router.get("/scheduler/jobs")
async def get_scheduled_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all scheduled jobs - combines database and active scheduler jobs"""
    # Get jobs from database
    db_jobs = db.query(ScheduledJob).order_by(ScheduledJob.created_at.desc()).all()
    
    # Get active scheduler jobs for next_run info
    active_jobs = {j['id']: j for j in scheduler_manager.get_jobs()}
    
    result = []
    for job in db_jobs:
        job_dict = job.to_dict()
        # Add next_run from active scheduler if available
        if job.id in active_jobs:
            job_dict['next_run'] = active_jobs[job.id].get('next_run')
            job_dict['is_active'] = True
        else:
            job_dict['is_active'] = False
        result.append(job_dict)
    
    return result


@router.post("/scheduler/jobs")
async def create_scheduled_job(
    request: ScheduledJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new scheduled job and register with scheduler"""
    import uuid
    
    job_id = str(uuid.uuid4())
    
    # Create job in scheduler based on type
    try:
        if request.job_type == 'daily' and request.time:
            scheduler_manager.add_daily_download_job(
                time_str=request.time,
                symbols=request.symbols,
                exchanges=request.exchanges,
                interval=request.data_interval,
                job_id=job_id,
                job_name=request.name,
                persist=False  # We'll save to DB ourselves
            )
        elif request.job_type == 'interval' and request.minutes:
            scheduler_manager.add_interval_download_job(
                minutes=request.minutes,
                symbols=request.symbols,
                exchanges=request.exchanges,
                interval=request.data_interval,
                job_id=job_id,
                job_name=request.name,
                persist=False
            )
        elif request.job_type == 'market_close':
            scheduler_manager.add_market_close_job(job_id=job_id)
        elif request.job_type == 'pre_market':
            scheduler_manager.add_pre_market_job(job_id=job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create scheduler job: {str(e)}")
    
    # Save to database
    job = ScheduledJob(
        id=job_id,
        name=request.name,
        job_type=request.job_type,
        time=request.time,
        minutes=request.minutes,
        data_interval=request.data_interval,
        is_paused=False
    )
    
    if request.symbols:
        job.set_symbols(request.symbols)
    if request.exchanges:
        job.set_exchanges(request.exchanges)
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return {"message": "Job created", "job": job.to_dict()}


@router.put("/scheduler/jobs/{job_id}")
async def update_scheduled_job(
    job_id: str,
    is_paused: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a scheduled job (pause/resume)"""
    job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if is_paused is not None:
        job.is_paused = is_paused
        # Update scheduler
        if is_paused:
            scheduler_manager.pause_job(job_id)
        else:
            scheduler_manager.resume_job(job_id)
    
    db.commit()
    db.refresh(job)
    
    return {"message": "Job updated", "job": job.to_dict()}


@router.delete("/scheduler/jobs/{job_id}")
async def delete_scheduled_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a scheduled job"""
    job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Remove from scheduler
    scheduler_manager.remove_job(job_id)
    
    # Remove from database
    db.delete(job)
    db.commit()
    
    return {"message": "Job deleted"}


@router.post("/scheduler/jobs/{job_id}/run")
async def run_scheduled_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually run a scheduled job"""
    job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Trigger immediate run
    scheduler_manager.run_job_now(job_id)
    
    # Update last run time
    job.last_run = datetime.utcnow()
    db.commit()
    
    return {"message": f"Job '{job.name}' started", "job": job.to_dict()}


# ============ Dynamic Table Management ============

@router.get("/tables")
async def get_all_data_tables(
    current_user: User = Depends(get_current_user)
):
    """Get list of all dynamic data tables"""
    tables = get_available_tables()
    
    # Add record counts and date ranges
    result = []
    for table in tables:
        earliest = get_earliest_date(table['symbol'], table['exchange'], table['interval'])
        latest = get_latest_date(table['symbol'], table['exchange'], table['interval'])
        count = get_record_count(table['symbol'], table['exchange'], table['interval'])
        
        result.append({
            **table,
            'record_count': count,
            'earliest_date': earliest.strftime('%Y-%m-%d') if earliest else None,
            'latest_date': latest.strftime('%Y-%m-%d') if latest else None
        })
    
    return result


@router.get("/tables/{symbol}/{exchange}/{interval}")
async def get_table_data(
    symbol: str,
    exchange: str,
    interval: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500,
    current_user: User = Depends(get_current_user)
):
    """Get data from a specific dynamic table"""
    from datetime import datetime as dt
    
    start = dt.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    end = dt.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    
    data = get_data_by_timeframe(symbol, exchange, interval, start, end, limit)
    
    return {
        "symbol": symbol,
        "exchange": exchange,
        "interval": interval,
        "count": len(data),
        "data": data
    }


@router.get("/tables/{symbol}/{exchange}/{interval}/info")
async def get_table_info(
    symbol: str,
    exchange: str,
    interval: str,
    current_user: User = Depends(get_current_user)
):
    """Get info about a specific dynamic table"""
    earliest = get_earliest_date(symbol, exchange, interval)
    latest = get_latest_date(symbol, exchange, interval)
    count = get_record_count(symbol, exchange, interval)
    table_name = get_table_name(symbol, exchange, interval)
    
    return {
        "table_name": table_name,
        "symbol": symbol,
        "exchange": exchange,
        "interval": interval,
        "record_count": count,
        "earliest_date": earliest.strftime('%Y-%m-%d') if earliest else None,
        "latest_date": latest.strftime('%Y-%m-%d') if latest else None
    }


@router.delete("/tables/{symbol}/{exchange}/{interval}")
async def delete_table(
    symbol: str,
    exchange: str,
    interval: str,
    drop: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Delete data from a dynamic table or drop the entire table"""
    if drop:
        success = drop_table(symbol, exchange, interval)
        if success:
            return {"message": f"Table for {symbol} ({exchange}) {interval} dropped"}
        else:
            raise HTTPException(status_code=404, detail="Table not found")
    else:
        count = delete_table_data(symbol, exchange, interval)
        return {"message": f"Deleted {count} records from {symbol} ({exchange}) {interval}"}


# ============ StockData Unified Table Management ============

class StockDataInsert(BaseModel):
    symbol: str
    exchange: str
    interval: str = 'D'
    date: str  # YYYY-MM-DD
    time: Optional[str] = None  # HH:MM:SS
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    oi: Optional[int] = 0


class StockDataBulkInsert(BaseModel):
    data: List[StockDataInsert]


@router.get("/stock")
async def get_stock_data_symbols(
    exchange: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all symbols with stock data"""
    results = StockData.get_available_symbols(db, exchange)
    
    return [{
        'symbol': r.symbol,
        'exchange': r.exchange,
        'record_count': r.record_count,
        'earliest_date': r.earliest_date.strftime('%Y-%m-%d') if r.earliest_date else None,
        'latest_date': r.latest_date.strftime('%Y-%m-%d') if r.latest_date else None
    } for r in results]


@router.get("/stock/{symbol}")
async def get_stock_data(
    symbol: str,
    exchange: Optional[str] = None,
    interval: str = 'D',
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get stock data for a specific symbol"""
    from datetime import datetime as dt
    
    # Default date range: last 1 year
    end = dt.strptime(end_date, "%Y-%m-%d").date() if end_date else dt.now().date()
    start = dt.strptime(start_date, "%Y-%m-%d").date() if start_date else (end - timedelta(days=365))
    
    records = StockData.get_data_by_timeframe(db, symbol, start, end, interval, exchange)
    
    # Apply limit
    if limit and len(records) > limit:
        records = records[-limit:]
    
    return {
        "symbol": symbol,
        "exchange": exchange,
        "interval": interval,
        "count": len(records),
        "data": [r.to_dict() for r in records]
    }


@router.get("/stock/{symbol}/info")
async def get_stock_info(
    symbol: str,
    exchange: Optional[str] = None,
    interval: str = 'D',
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get info about stock data for a symbol"""
    earliest = StockData.get_earliest_record(db, symbol, exchange, interval)
    latest = StockData.get_latest_record(db, symbol, exchange, interval)
    count = StockData.get_record_count(db, symbol, exchange, interval)
    
    return {
        "symbol": symbol,
        "exchange": exchange,
        "interval": interval,
        "record_count": count,
        "earliest_date": earliest.date.strftime('%Y-%m-%d') if earliest else None,
        "latest_date": latest.date.strftime('%Y-%m-%d') if latest else None
    }


@router.post("/stock")
async def insert_stock_data(
    request: StockDataInsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Insert a single stock data record"""
    from datetime import datetime as dt
    
    record_date = dt.strptime(request.date, "%Y-%m-%d").date()
    record_time = dt.strptime(request.time, "%H:%M:%S").time() if request.time else None
    
    # Check if record exists
    existing = db.query(StockData).filter(
        StockData.symbol == request.symbol,
        StockData.exchange == request.exchange,
        StockData.interval == request.interval,
        StockData.date == record_date,
        StockData.time == record_time
    ).first()
    
    if existing:
        # Update existing record
        existing.open = request.open
        existing.high = request.high
        existing.low = request.low
        existing.close = request.close
        existing.volume = request.volume
        existing.oi = request.oi
        db.commit()
        return {"message": "Record updated", "id": existing.id}
    
    # Insert new record
    record = StockData(
        symbol=request.symbol,
        exchange=request.exchange,
        interval=request.interval,
        date=record_date,
        time=record_time,
        open=request.open,
        high=request.high,
        low=request.low,
        close=request.close,
        volume=request.volume,
        oi=request.oi
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    
    return {"message": "Record inserted", "id": record.id}


@router.post("/stock/bulk")
async def bulk_insert_stock_data(
    request: StockDataBulkInsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk insert stock data records"""
    from datetime import datetime as dt
    
    inserted = 0
    updated = 0
    
    for item in request.data:
        record_date = dt.strptime(item.date, "%Y-%m-%d").date()
        record_time = dt.strptime(item.time, "%H:%M:%S").time() if item.time else None
        
        existing = db.query(StockData).filter(
            StockData.symbol == item.symbol,
            StockData.exchange == item.exchange,
            StockData.interval == item.interval,
            StockData.date == record_date,
            StockData.time == record_time
        ).first()
        
        if existing:
            existing.open = item.open
            existing.high = item.high
            existing.low = item.low
            existing.close = item.close
            existing.volume = item.volume
            existing.oi = item.oi
            updated += 1
        else:
            record = StockData(
                symbol=item.symbol,
                exchange=item.exchange,
                interval=item.interval,
                date=record_date,
                time=record_time,
                open=item.open,
                high=item.high,
                low=item.low,
                close=item.close,
                volume=item.volume,
                oi=item.oi
            )
            db.add(record)
            inserted += 1
    
    db.commit()
    
    return {
        "message": "Bulk insert completed",
        "inserted": inserted,
        "updated": updated,
        "total": len(request.data)
    }


@router.delete("/stock/{symbol}")
async def delete_stock_data(
    symbol: str,
    exchange: Optional[str] = None,
    interval: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete stock data for a symbol"""
    query = db.query(StockData).filter(StockData.symbol == symbol)
    
    if exchange:
        query = query.filter(StockData.exchange == exchange)
    if interval:
        query = query.filter(StockData.interval == interval)
    
    count = query.delete()
    db.commit()
    
    return {"message": f"Deleted {count} records for {symbol}"}


# ============ Direct Export (Fetch from Broker) ============

class ExportRequest(BaseModel):
    symbol: str
    token: str
    exchange: str
    timeframe: str = "ONE_DAY"
    from_date: str
    to_date: str
    client_code: str


@router.post("/export/fetch")
async def fetch_for_export(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch historical data directly from broker for export
    Returns data immediately (synchronous) instead of background download
    """
    if request.client_code not in angel_sessions:
        raise HTTPException(status_code=400, detail="Broker session not active")
    
    angel_client = angel_sessions[request.client_code]
    
    try:
        # Format dates for Angel One API
        from_date_str = f"{request.from_date} 09:15"
        to_date_str = f"{request.to_date} 15:30"
        
        # Call Angel One historical data API
        historic_params = {
            "exchange": request.exchange,
            "symboltoken": request.token,
            "interval": request.timeframe,
            "fromdate": from_date_str,
            "todate": to_date_str
        }
        
        print(f"Export Fetch Params: {historic_params}")
        response = angel_client.getCandleData(historic_params)
        print(f"Export Response: {response}")
        
        if response and response.get('status'):
            candle_data = response.get('data', [])
            
            # Parse and format data
            formatted_data = []
            for candle in candle_data:
                try:
                    # Angel One returns: [timestamp, open, high, low, close, volume]
                    timestamp = datetime.strptime(candle[0], '%Y-%m-%dT%H:%M:%S%z')
                    
                    formatted_data.append({
                        'date': timestamp.strftime('%Y-%m-%d'),
                        'time': timestamp.strftime('%H:%M:%S') if request.timeframe != 'ONE_DAY' else '',
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': int(candle[5]) if len(candle) > 5 else 0
                    })
                except Exception as e:
                    continue
            
            return {
                "status": "success",
                "symbol": request.symbol,
                "exchange": request.exchange,
                "count": len(formatted_data),
                "data": formatted_data
            }
        else:
            error_msg = response.get('message', 'Unknown error') if response else 'No response'
            return {
                "status": "error",
                "message": error_msg,
                "data": []
            }
            
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e),
            "data": []
        }
