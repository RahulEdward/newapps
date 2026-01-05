"""
Market Hours Manager for AngelOne
Manages Indian market trading hours, holidays, and sessions

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

from datetime import datetime, time, timedelta, date
from typing import Optional, List, Tuple
import pytz
from loguru import logger


class MarketHoursManager:
    """
    Manages Indian market trading hours
    
    Features:
    - Track market hours (9:15 AM - 3:30 PM IST)
    - Handle pre-market session (9:00 AM - 9:15 AM)
    - Handle NSE holidays
    - Weekend detection
    - Calculate next market open time
    """
    
    # Market timing constants
    TIMEZONE = pytz.timezone('Asia/Kolkata')
    
    # Regular market hours
    MARKET_OPEN = time(9, 15, 0)   # 9:15 AM IST
    MARKET_CLOSE = time(15, 30, 0)  # 3:30 PM IST
    
    # Pre-market session
    PRE_MARKET_START = time(9, 0, 0)   # 9:00 AM IST
    PRE_MARKET_END = time(9, 15, 0)    # 9:15 AM IST
    
    # Post-market session (for reference)
    POST_MARKET_START = time(15, 40, 0)  # 3:40 PM IST
    POST_MARKET_END = time(16, 0, 0)     # 4:00 PM IST
    
    # NSE Holidays 2025 (sample - should be updated annually)
    NSE_HOLIDAYS_2025 = [
        date(2025, 1, 26),   # Republic Day
        date(2025, 2, 26),   # Mahashivratri
        date(2025, 3, 14),   # Holi
        date(2025, 3, 31),   # Id-Ul-Fitr
        date(2025, 4, 10),   # Shri Mahavir Jayanti
        date(2025, 4, 14),   # Dr. Ambedkar Jayanti
        date(2025, 4, 18),   # Good Friday
        date(2025, 5, 1),    # Maharashtra Day
        date(2025, 8, 15),   # Independence Day
        date(2025, 8, 27),   # Janmashtami
        date(2025, 10, 2),   # Gandhi Jayanti
        date(2025, 10, 21),  # Diwali Laxmi Pujan
        date(2025, 10, 22),  # Diwali Balipratipada
        date(2025, 11, 5),   # Gurunanak Jayanti
        date(2025, 12, 25),  # Christmas
    ]
    
    # NSE Holidays 2026 (sample)
    NSE_HOLIDAYS_2026 = [
        date(2026, 1, 26),   # Republic Day
        date(2026, 3, 10),   # Holi
        date(2026, 4, 3),    # Good Friday
        date(2026, 4, 14),   # Dr. Ambedkar Jayanti
        date(2026, 5, 1),    # Maharashtra Day
        date(2026, 8, 15),   # Independence Day
        date(2026, 10, 2),   # Gandhi Jayanti
        date(2026, 11, 9),   # Diwali
        date(2026, 12, 25),  # Christmas
    ]
    
    def __init__(self, custom_holidays: List[date] = None):
        """
        Initialize MarketHoursManager
        
        Args:
            custom_holidays: Optional list of additional holidays
        """
        self._holidays = set()
        self._holidays.update(self.NSE_HOLIDAYS_2025)
        self._holidays.update(self.NSE_HOLIDAYS_2026)
        
        if custom_holidays:
            self._holidays.update(custom_holidays)
        
        logger.info("MarketHoursManager initialized")
    
    def _get_ist_now(self) -> datetime:
        """Get current time in IST"""
        return datetime.now(self.TIMEZONE)
    
    def _to_ist(self, dt: datetime) -> datetime:
        """Convert datetime to IST"""
        if dt.tzinfo is None:
            return self.TIMEZONE.localize(dt)
        return dt.astimezone(self.TIMEZONE)
    
    def is_market_open(self, dt: datetime = None) -> bool:
        """
        Check if market is currently open
        
        Args:
            dt: Optional datetime to check (default: now)
        
        Returns:
            True if market is open for regular trading
        """
        if dt is None:
            dt = self._get_ist_now()
        else:
            dt = self._to_ist(dt)
        
        # Check if trading day
        if not self.is_trading_day(dt.date()):
            return False
        
        # Check time
        current_time = dt.time()
        return self.MARKET_OPEN <= current_time <= self.MARKET_CLOSE
    
    def is_pre_market(self, dt: datetime = None) -> bool:
        """
        Check if in pre-market session
        
        Args:
            dt: Optional datetime to check
        
        Returns:
            True if in pre-market session
        """
        if dt is None:
            dt = self._get_ist_now()
        else:
            dt = self._to_ist(dt)
        
        if not self.is_trading_day(dt.date()):
            return False
        
        current_time = dt.time()
        return self.PRE_MARKET_START <= current_time < self.PRE_MARKET_END
    
    def is_post_market(self, dt: datetime = None) -> bool:
        """
        Check if in post-market session
        
        Args:
            dt: Optional datetime to check
        
        Returns:
            True if in post-market session
        """
        if dt is None:
            dt = self._get_ist_now()
        else:
            dt = self._to_ist(dt)
        
        if not self.is_trading_day(dt.date()):
            return False
        
        current_time = dt.time()
        return self.POST_MARKET_START <= current_time <= self.POST_MARKET_END
    
    def is_trading_day(self, check_date: date = None) -> bool:
        """
        Check if given date is a trading day
        
        Args:
            check_date: Date to check (default: today)
        
        Returns:
            True if it's a valid trading day
        """
        if check_date is None:
            check_date = self._get_ist_now().date()
        
        # Check weekend (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            return False
        
        # Check holidays
        if check_date in self._holidays:
            return False
        
        return True
    
    def is_holiday(self, check_date: date = None) -> bool:
        """
        Check if given date is a market holiday
        
        Args:
            check_date: Date to check
        
        Returns:
            True if it's a holiday
        """
        if check_date is None:
            check_date = self._get_ist_now().date()
        
        return check_date in self._holidays
    
    def is_weekend(self, check_date: date = None) -> bool:
        """
        Check if given date is a weekend
        
        Args:
            check_date: Date to check
        
        Returns:
            True if it's Saturday or Sunday
        """
        if check_date is None:
            check_date = self._get_ist_now().date()
        
        return check_date.weekday() >= 5
    
    def get_next_market_open(self, from_dt: datetime = None) -> datetime:
        """
        Get next market opening time
        
        Args:
            from_dt: Starting datetime (default: now)
        
        Returns:
            Datetime of next market open in IST
        """
        if from_dt is None:
            from_dt = self._get_ist_now()
        else:
            from_dt = self._to_ist(from_dt)
        
        current_date = from_dt.date()
        current_time = from_dt.time()
        
        # If market is currently open or will open today
        if self.is_trading_day(current_date) and current_time < self.MARKET_OPEN:
            return self.TIMEZONE.localize(
                datetime.combine(current_date, self.MARKET_OPEN)
            )
        
        # Find next trading day
        next_date = current_date + timedelta(days=1)
        max_days = 10  # Safety limit
        
        for _ in range(max_days):
            if self.is_trading_day(next_date):
                return self.TIMEZONE.localize(
                    datetime.combine(next_date, self.MARKET_OPEN)
                )
            next_date += timedelta(days=1)
        
        # Fallback - should not reach here
        return self.TIMEZONE.localize(
            datetime.combine(next_date, self.MARKET_OPEN)
        )
    
    def get_next_market_close(self, from_dt: datetime = None) -> datetime:
        """
        Get next market closing time
        
        Args:
            from_dt: Starting datetime (default: now)
        
        Returns:
            Datetime of next market close in IST
        """
        if from_dt is None:
            from_dt = self._get_ist_now()
        else:
            from_dt = self._to_ist(from_dt)
        
        current_date = from_dt.date()
        current_time = from_dt.time()
        
        # If market is open, return today's close
        if self.is_trading_day(current_date) and current_time < self.MARKET_CLOSE:
            return self.TIMEZONE.localize(
                datetime.combine(current_date, self.MARKET_CLOSE)
            )
        
        # Find next trading day's close
        next_open = self.get_next_market_open(from_dt)
        return self.TIMEZONE.localize(
            datetime.combine(next_open.date(), self.MARKET_CLOSE)
        )
    
    def time_to_market_open(self, from_dt: datetime = None) -> timedelta:
        """
        Get time remaining until market opens
        
        Args:
            from_dt: Starting datetime
        
        Returns:
            Timedelta until market opens (negative if already open)
        """
        if from_dt is None:
            from_dt = self._get_ist_now()
        else:
            from_dt = self._to_ist(from_dt)
        
        if self.is_market_open(from_dt):
            return timedelta(0)
        
        next_open = self.get_next_market_open(from_dt)
        return next_open - from_dt
    
    def time_to_market_close(self, from_dt: datetime = None) -> timedelta:
        """
        Get time remaining until market closes
        
        Args:
            from_dt: Starting datetime
        
        Returns:
            Timedelta until market closes
        """
        if from_dt is None:
            from_dt = self._get_ist_now()
        else:
            from_dt = self._to_ist(from_dt)
        
        if not self.is_market_open(from_dt):
            return timedelta(0)
        
        close_time = self.TIMEZONE.localize(
            datetime.combine(from_dt.date(), self.MARKET_CLOSE)
        )
        return close_time - from_dt
    
    def get_market_session(self, dt: datetime = None) -> str:
        """
        Get current market session name
        
        Args:
            dt: Datetime to check
        
        Returns:
            Session name: 'pre_market', 'market', 'post_market', 'closed'
        """
        if dt is None:
            dt = self._get_ist_now()
        
        if self.is_pre_market(dt):
            return 'pre_market'
        elif self.is_market_open(dt):
            return 'market'
        elif self.is_post_market(dt):
            return 'post_market'
        else:
            return 'closed'
    
    def add_holiday(self, holiday_date: date) -> None:
        """Add a holiday to the list"""
        self._holidays.add(holiday_date)
        logger.info(f"Added holiday: {holiday_date}")
    
    def remove_holiday(self, holiday_date: date) -> None:
        """Remove a holiday from the list"""
        self._holidays.discard(holiday_date)
        logger.info(f"Removed holiday: {holiday_date}")
    
    def get_holidays(self, year: int = None) -> List[date]:
        """
        Get list of holidays
        
        Args:
            year: Optional year filter
        
        Returns:
            List of holiday dates
        """
        if year:
            return sorted([h for h in self._holidays if h.year == year])
        return sorted(list(self._holidays))
    
    def get_trading_days_in_range(
        self, 
        start_date: date, 
        end_date: date
    ) -> List[date]:
        """
        Get list of trading days in a date range
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            List of trading days
        """
        trading_days = []
        current = start_date
        
        while current <= end_date:
            if self.is_trading_day(current):
                trading_days.append(current)
            current += timedelta(days=1)
        
        return trading_days
