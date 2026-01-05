import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional
import aiohttp
from src.utils.logger import log

class BinanceWebSocketClient:
    """
    Binance WebSocket Client (Futures)
    
    Uses wss://fstream.binance.com/ws raw stream interface
    Sends SUBSCRIBE messages via JSON-RPC for dynamic subscription
    """
    BASE_URL = "wss://fstream.binance.com/ws"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.callbacks: List[Callable[[Dict], None]] = []
        self.running = False
        self._subscriptions = []
        self._lock = asyncio.Lock()

    async def start(self):
        """Start WebSocket connection"""
        if self.running:
            return
        self.running = True
        self.session = aiohttp.ClientSession()
        asyncio.create_task(self._connect_loop())
        log.info("🚀 Binance WebSocket Client (Futures) Started")

    async def _connect_loop(self):
        """Connection maintenance loop"""
        while self.running:
            try:
                log.info(f"Connecting to Binance WS: {self.BASE_URL}")
                async with self.session.ws_connect(self.BASE_URL) as ws:
                    self.ws = ws
                    log.info("✅ Binance WS Connected")
                    
                    # Re-subscribe after successful connection
                    if self._subscriptions:
                        await self._send_subscribe(self._subscriptions)
                    
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                self._handle_message(data)
                            except Exception as e:
                                log.error(f"WS Parse Error: {e}")
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            log.error(f"WS Error: {ws.exception()}")
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                             log.warning("WS Closed")
                             break
                            
            except Exception as e:
                log.error(f"WS Connection Loop Error: {e}")
                
            if self.running:
                log.warning("🔄 WS Reconnecting in 5s...")
                await asyncio.sleep(5) 

    async def _send_subscribe(self, streams: List[str]):
        """Send subscription command"""
        if not self.ws:
            return
        
        payload = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        }
        try:
            await self.ws.send_json(payload)
            log.info(f"📡 Subscribed to: {streams}")
        except Exception as e:
            log.error(f"Subscribe failed: {e}")

    def _handle_message(self, data: Dict):
        """Handle push messages"""
        # Ignore subscription responses
        if "result" in data and "id" in data:
            return

        # Handle K-line events (e: kline)
        if data.get("e") == "kline":
            for callback in self.callbacks:
                try:
                    callback(data)
                except Exception as e:
                    log.error(f"Callback error: {e}")
            return
        
        # Can be extended to handle other message types...

    async def subscribe_kline(self, symbol: str, interval: str):
        """
        Subscribe to K-line data
        Topic: <symbol>@kline_<interval>
        """
        stream = f"{symbol.lower()}@kline_{interval}"
        async with self._lock:
            if stream not in self._subscriptions:
                self._subscriptions.append(stream)
                if self.ws:
                    await self._send_subscribe([stream])
            
    def add_callback(self, callback: Callable[[Dict], None]):
        """Register callback function"""
        self.callbacks.append(callback)

    async def stop(self):
        """Stop client"""
        self.running = False
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()

# Singleton pattern
ws_client = BinanceWebSocketClient()
