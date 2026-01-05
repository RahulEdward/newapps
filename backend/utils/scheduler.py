"""
Trading Maven - Scheduler Module for Automated Data Downloads
Uses APScheduler for background job scheduling with IST timezone
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import pytz
import logging
import asyncio
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')


class SchedulerManager:
    """
    Manages scheduled jobs for automated data downloads
    Supports daily, interval, market close, and pre-market jobs
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=IST)
        self.jobs: Dict[str, Dict] = {}
        self._initialized = False
    
    def init_app(self, app=None):
        """Initialize and start the scheduler"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self._initialized = True
                logger.info("Scheduler started with IST timezone")
                # Load persisted jobs
                asyncio.create_task(self._load_persisted_jobs())
            else:
                logger.info("Scheduler already running")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}")
    
    def add_daily_download_job(
        self,
        time_str: str,
        symbols: Optional[List[str]] = None,
        exchanges: Optional[List[str]] = None,
        interval: str = 'ONE_DAY',
        job_id: Optional[str] = None,
        job_name: Optional[str] = None,
        persist: bool = True
    ) -> str:
        """
        Add a daily download job at specified IST time
        
        Args:
            time_str: Time in HH:MM format (24-hour)
            symbols: List of symbols to download
            exchanges: List of exchanges
            interval: Data interval
            job_id: Unique job identifier
            job_name: Human-readable job name
            persist: Whether to save to database
        """
        try:
            hour, minute = map(int, time_str.split(':'))
            
            if job_id is None:
                job_id = f"daily_download_{time_str.replace(':', '')}"
            
            if job_name is None:
                job_name = f"Daily Download at {time_str} IST"
            
            # Add job with cron trigger
            job = self.scheduler.add_job(
                func=self._execute_download,
                trigger=CronTrigger(hour=hour, minute=minute, timezone=IST),
                id=job_id,
                replace_existing=True,
                name=job_name,
                kwargs={
                    'symbols': symbols,
                    'exchanges': exchanges,
                    'interval': interval
                }
            )
            
            self.jobs[job_id] = {
                'type': 'daily',
                'time': time_str,
                'symbols': symbols,
                'exchanges': exchanges,
                'interval': interval,
                'name': job_name,
                'paused': False,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None
            }
            
            logger.info(f"Added daily download job '{job_name}' at {time_str} IST")
            
            # Persist to database
            if persist:
                asyncio.create_task(self._persist_job(job_id, 'daily', time_str, None, symbols, exchanges, interval, job_name))
            
            return job_id
            
        except Exception as e:
            logger.error(f"Error adding daily download job: {str(e)}")
            raise
    
    def add_interval_download_job(
        self,
        minutes: int,
        symbols: Optional[List[str]] = None,
        exchanges: Optional[List[str]] = None,
        interval: str = 'ONE_DAY',
        job_id: Optional[str] = None,
        job_name: Optional[str] = None,
        persist: bool = True
    ) -> str:
        """
        Add a recurring download job that runs every N minutes
        """
        try:
            if job_id is None:
                job_id = f"interval_download_{minutes}min"
            
            if job_name is None:
                job_name = f"Download every {minutes} minutes"
            
            # Add job with interval trigger
            job = self.scheduler.add_job(
                func=self._execute_download,
                trigger=IntervalTrigger(minutes=minutes),
                id=job_id,
                replace_existing=True,
                name=job_name,
                kwargs={
                    'symbols': symbols,
                    'exchanges': exchanges,
                    'interval': interval
                }
            )
            
            self.jobs[job_id] = {
                'type': 'interval',
                'minutes': minutes,
                'symbols': symbols,
                'exchanges': exchanges,
                'interval': interval,
                'name': job_name,
                'paused': False,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None
            }
            
            logger.info(f"Added interval download job every {minutes} minutes")
            
            # Persist to database
            if persist:
                asyncio.create_task(self._persist_job(job_id, 'interval', None, minutes, symbols, exchanges, interval, job_name))
            
            return job_id
            
        except Exception as e:
            logger.error(f"Error adding interval download job: {str(e)}")
            raise
    
    def add_market_close_job(self, job_id: Optional[str] = None) -> str:
        """Add a job that runs after market close (3:35 PM IST for NSE)"""
        job_id = job_id or "market_close_download"
        return self.add_daily_download_job(
            time_str="15:35",
            job_id=job_id,
            job_name="Market Close Download",
            persist=True
        )
    
    def add_pre_market_job(self, job_id: Optional[str] = None) -> str:
        """Add a job that runs before market open (8:30 AM IST)"""
        job_id = job_id or "pre_market_download"
        return self.add_daily_download_job(
            time_str="08:30",
            job_id=job_id,
            job_name="Pre-Market Download",
            persist=True
        )
    
    async def _execute_download(
        self,
        symbols: Optional[List[str]] = None,
        exchanges: Optional[List[str]] = None,
        interval: str = 'ONE_DAY'
    ):
        """Execute the actual download process"""
        from database.session import SessionLocal
        from database.models import Checkpoint, StockData
        from charts.data_fetcher import ChunkedDataFetcher
        from routers.angel_one import angel_sessions
        
        logger.info(f"Starting scheduled download at {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
        
        db = SessionLocal()
        try:
            # Get active broker session
            angel_client = None
            for client_code, client in angel_sessions.items():
                angel_client = client
                break
            
            if not angel_client:
                logger.warning("No active broker session for scheduled download")
                return
            
            # If no symbols specified, get from checkpoints (previously downloaded)
            if symbols is None:
                checkpoints = db.query(Checkpoint).all()
                if checkpoints:
                    symbols = [cp.symbol for cp in checkpoints]
                    exchanges = [cp.exchange for cp in checkpoints]
                else:
                    logger.warning("No symbols to download")
                    return
            
            if not symbols:
                logger.warning("No symbols to download")
                return
            
            # Create fetcher and download
            fetcher = ChunkedDataFetcher(angel_client)
            
            success_count = 0
            failed_count = 0
            
            for symbol, exchange in zip(symbols, exchanges or ['NSE'] * len(symbols)):
                try:
                    result = await fetcher.fetch_with_checkpoint(
                        symbol=symbol,
                        token="",  # Will need to lookup
                        exchange=exchange,
                        interval=interval
                    )
                    
                    if result.get('status') in ['success', 'up_to_date']:
                        success_count += 1
                        logger.info(f"Downloaded data for {symbol}: {result.get('records', 0)} records")
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to download {symbol}: {result.get('error')}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error downloading {symbol}: {str(e)}")
                
                # Rate limiting
                await asyncio.sleep(0.5)
            
            logger.info(f"Scheduled download completed: {success_count} success, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error in scheduled download: {str(e)}")
        finally:
            db.close()
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.jobs:
                del self.jobs[job_id]
            
            # Remove from database
            asyncio.create_task(self._delete_job_from_db(job_id))
            
            logger.info(f"Removed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing job {job_id}: {str(e)}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job"""
        try:
            self.scheduler.pause_job(job_id)
            if job_id in self.jobs:
                self.jobs[job_id]['paused'] = True
            
            asyncio.create_task(self._update_job_status(job_id, is_paused=True))
            
            logger.info(f"Paused job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error pausing job {job_id}: {str(e)}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        try:
            self.scheduler.resume_job(job_id)
            if job_id in self.jobs:
                self.jobs[job_id]['paused'] = False
            
            asyncio.create_task(self._update_job_status(job_id, is_paused=False))
            
            logger.info(f"Resumed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error resuming job {job_id}: {str(e)}")
            return False
    
    def run_job_now(self, job_id: str) -> bool:
        """Manually trigger a job to run immediately"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now(IST))
                logger.info(f"Triggered immediate run for job: {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error running job {job_id}: {str(e)}")
            return False
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get all scheduled jobs"""
        jobs_list = []
        try:
            if self.scheduler and self.scheduler.running:
                for job in self.scheduler.get_jobs():
                    job_info = {
                        'id': job.id,
                        'name': job.name,
                        'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                        'paused': job.next_run_time is None
                    }
                    
                    if job.id in self.jobs:
                        job_info.update(self.jobs[job.id])
                    
                    jobs_list.append(job_info)
        except Exception as e:
            logger.error(f"Error getting jobs: {str(e)}")
        
        return jobs_list
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job by ID"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job_info = {
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'paused': job.next_run_time is None
                }
                if job.id in self.jobs:
                    job_info.update(self.jobs[job.id])
                return job_info
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {str(e)}")
        return None
    
    async def _persist_job(
        self,
        job_id: str,
        job_type: str,
        time_str: Optional[str],
        minutes: Optional[int],
        symbols: Optional[List[str]],
        exchanges: Optional[List[str]],
        interval: str,
        name: str
    ):
        """Save job to database"""
        from database.session import SessionLocal
        from database.models import ScheduledJob
        
        db = SessionLocal()
        try:
            job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
            if not job:
                job = ScheduledJob(id=job_id)
                db.add(job)
            
            job.name = name
            job.job_type = job_type
            job.time = time_str
            job.minutes = minutes
            job.data_interval = interval
            job.is_paused = False
            job.set_symbols(symbols)
            job.set_exchanges(exchanges)
            
            db.commit()
            logger.info(f"Persisted job to database: {job_id}")
        except Exception as e:
            logger.error(f"Error persisting job: {str(e)}")
            db.rollback()
        finally:
            db.close()
    
    async def _delete_job_from_db(self, job_id: str):
        """Delete job from database"""
        from database.session import SessionLocal
        from database.models import ScheduledJob
        
        db = SessionLocal()
        try:
            job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
            if job:
                db.delete(job)
                db.commit()
        except Exception as e:
            logger.error(f"Error deleting job from db: {str(e)}")
        finally:
            db.close()
    
    async def _update_job_status(self, job_id: str, is_paused: bool):
        """Update job pause status in database"""
        from database.session import SessionLocal
        from database.models import ScheduledJob
        
        db = SessionLocal()
        try:
            job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
            if job:
                job.is_paused = is_paused
                db.commit()
        except Exception as e:
            logger.error(f"Error updating job status: {str(e)}")
        finally:
            db.close()
    
    async def _load_persisted_jobs(self):
        """Load persisted jobs from database on startup"""
        from database.session import SessionLocal
        from database.models import ScheduledJob
        
        db = SessionLocal()
        try:
            logger.info("Loading persisted scheduler jobs from database")
            jobs = db.query(ScheduledJob).all()
            
            for job in jobs:
                try:
                    if job.job_type == 'daily':
                        self.add_daily_download_job(
                            time_str=job.time,
                            symbols=job.get_symbols(),
                            exchanges=job.get_exchanges(),
                            interval=job.data_interval or 'ONE_DAY',
                            job_id=job.id,
                            job_name=job.name,
                            persist=False
                        )
                    elif job.job_type == 'interval':
                        self.add_interval_download_job(
                            minutes=job.minutes,
                            symbols=job.get_symbols(),
                            exchanges=job.get_exchanges(),
                            interval=job.data_interval or 'ONE_DAY',
                            job_id=job.id,
                            job_name=job.name,
                            persist=False
                        )
                    elif job.job_type == 'market_close':
                        self.add_market_close_job(job_id=job.id)
                    elif job.job_type == 'pre_market':
                        self.add_pre_market_job(job_id=job.id)
                    
                    # Pause if was paused
                    if job.is_paused:
                        self.pause_job(job.id)
                    
                    logger.info(f"Loaded persisted job: {job.id}")
                    
                except Exception as e:
                    logger.error(f"Error loading job {job.id}: {str(e)}")
            
            logger.info(f"Loaded {len(jobs)} persisted jobs")
            
        except Exception as e:
            logger.error(f"Error loading persisted jobs: {str(e)}")
        finally:
            db.close()
    
    def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down")


# Global scheduler instance
scheduler_manager = SchedulerManager()
