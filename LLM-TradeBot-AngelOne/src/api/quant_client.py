"""
External Quantitative Output API Integration Layer
Supports: Netflow (Institutional/Individual), OI (Binance/ByBit), Price Change
"""
import os
import aiohttp
import asyncio
from typing import Dict, Optional
from src.utils.logger import log

class QuantClient:
    """External Quantitative API Client"""
    
    BASE_URL = "http://nofxaios.com:30006/api/coin"
    @property
    def auth_token(self) -> str:
        """Dynamically get the latest authentication token from environment variables"""
        token = os.getenv('QUANT_AUTH_TOKEN', '')
        if not token:
            log.warning("QUANT_AUTH_TOKEN not set in environment, quant API calls may fail")
        return token
    
    def __init__(self, timeout: int = 10):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session, properly handle event loop changes"""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        
        # Check if session needs to be recreated
        need_new_session = False
        
        if self.session is None:
            need_new_session = True
        elif self.session.closed:
            need_new_session = True
        elif hasattr(self.session, '_loop') and self.session._loop is not current_loop:
            # Event loop changed, need to close old session and create new one
            try:
                await self.session.close()
            except Exception:
                pass  # Ignore close errors
            need_new_session = True
                
        if need_new_session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        
        return self.session

    async def fetch_coin_data(self, symbol: str = "BTCUSDT") -> Dict:
        """
        Get quantitative depth data for specified coin
        """
        clean_symbol = symbol.replace("USDT", "USDT") # Compatibility handling
        url = f"{self.BASE_URL}/{clean_symbol}?include=netflow,oi,price&auth={self.auth_token}"
        
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        return result.get("data", {})
                if response.status == 401:
                    log.error(f"Quant API authentication failed (401): Please check if QUANT_AUTH_TOKEN environment variable is set correctly")
                else:
                    log.error(f"Quant API request failed: {response.status}")
                return {}
        except Exception as e:
            log.error(f"Quant API exception: {e}")
            return {}

    async def fetch_ai500_list(self) -> Dict:
        """
        Get AI500 quality coin pool list
        """
        url = f"http://nofxaios.com:30006/api/ai500/list?auth={self.auth_token}"
        
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        return result.get("data", [])
                log.error(f"AI500 List request failed: {response.status}")
                return []
        except Exception as e:
            log.error(f"AI500 API exception: {e}")
            return []

    async def fetch_oi_ranking(self, ranking_type: str = 'top', limit: int = 20, duration: str = '1h') -> Dict:
        """
        Get OI ranking
        
        Args:
            ranking_type: 'top' (gainers) or 'low' (losers)
            limit: Number of results to return
            duration: Time period (1h, 4h, 24h)
        """
        endpoint = "top-ranking" if ranking_type == 'top' else "low-ranking"
        url = f"http://nofxaios.com:30006/api/oi/{endpoint}?limit={limit}&duration={duration}&auth={self.auth_token}"
        
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        return result.get("data", [])
                log.error(f"OI Ranking request failed: {response.status}")
                return []
        except Exception as e:
            log.error(f"OI Ranking API exception: {e}")
            return []

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

# Global singleton
quant_client = QuantClient()
