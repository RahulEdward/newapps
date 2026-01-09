from fastapi import FastAPI, Body, HTTPException, Request, Response, Depends, Cookie
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import secrets
from typing import Optional, Dict
from loguru import logger as log

from src.server.state import global_state
from src.server.database import (
    init_database, get_user, save_broker_credentials, 
    save_broker_token, clear_broker_token, get_broker_credentials,
    save_setting, get_setting, save_llm_settings, get_llm_settings, load_llm_settings_to_env
)

# Load LLM settings from database on startup
load_llm_settings_to_env()

# Input Model
from pydantic import BaseModel
class ControlCommand(BaseModel):
    action: str  # start, pause, stop, restart, set_interval
    interval: float = None  # Optional: interval in minutes for set_interval action

class LoginRequest(BaseModel):
    password: str

class BrokerCredentials(BaseModel):
    client_id: str
    api_key: str
    pin: str

class BrokerConnect(BaseModel):
    totp: str

from fastapi import UploadFile, File
import shutil

app = FastAPI(title="LLM-TradeBot Dashboard")

# Enable CORS (rest unchanged)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get absolute path to the web directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB_DIR = os.path.join(BASE_DIR, 'web')

# Authentication Configuration
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "admin")  # Admin password

# Auto-detect production environment (Railway sets RAILWAY_* env vars and PORT)
IS_RAILWAY = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
IS_PRODUCTION = IS_RAILWAY or os.environ.get("DEPLOYMENT_MODE", "local") != "local"

SESSION_COOKIE_NAME = "tradebot_session"
# Session store: {session_id: role} where role is 'admin' or 'user'
VALID_SESSIONS = {}

def verify_auth(request: Request):
    """Dependency to verify login and return role"""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id or session_id not in VALID_SESSIONS:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return VALID_SESSIONS[session_id]  # Return 'admin' or 'user'

def verify_admin(role: str = Depends(verify_auth)):
    """Dependency to enforce Admin access"""
    if role != 'admin':
        raise HTTPException(status_code=403, detail="User mode: No permission to perform this action.")
    return True

import math

def clean_nans(obj):
    """Recursively replace NaN/Inf with None for JSON compliance"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    elif isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(i) for i in obj]
    return obj

# Public endpoint for system info (no auth required)
@app.get("/api/info")
async def get_system_info():
    return {
        "deployment_mode": "railway" if IS_RAILWAY else ("production" if IS_PRODUCTION else "local"),
        "requires_auth": True
    }

# Authentication Endpoints
@app.post("/api/login")
async def login(response: Response, data: LoginRequest):
    role = None
    
    # Universal Login Logic (Robust for both Local and Railway)
    # 1. Admin Login: Password matches WEB_PASSWORD or hardcoded known admin passwords
    if data.password == WEB_PASSWORD or data.password == "admin":
        role = 'admin'
    # 2. User Login: Password is 'guest' OR Empty -> Read Only
    elif not data.password or data.password == "guest":
        role = 'user'

    if role:
        session_id = secrets.token_urlsafe(32)
        VALID_SESSIONS[session_id] = role
        
        # Cookie settings for both local (HTTP) and Railway (HTTPS) deployment
        response.set_cookie(
            key=SESSION_COOKIE_NAME, 
            value=session_id, 
            httponly=True, 
            max_age=86400 * 7,  # 7 days
            samesite="none" if IS_PRODUCTION else "lax",  # "none" required for cross-site HTTPS
            secure=IS_PRODUCTION  # Must be True for HTTPS (Railway)
        )
        return {"status": "success", "role": role}
    else:
        raise HTTPException(status_code=401, detail="Invalid password")

@app.post("/api/logout")
async def logout(response: Response, request: Request):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id in VALID_SESSIONS:
        del VALID_SESSIONS[session_id]
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"status": "success"}

@app.get("/api/auth/status")
async def check_auth_status(request: Request):
    try:
        verify_auth(request)
        return {"status": "authenticated"}
    except HTTPException:
        return {"status": "unauthenticated"}

# Chart Data API for Lightweight Charts
@app.get("/api/chart/candles")
async def get_chart_candles(
    symbol: str = "RELIANCE",
    interval: str = "5m",
    limit: int = 100,
    authenticated: bool = Depends(verify_auth)
):
    """
    Get candlestick data for chart display
    Returns data in Lightweight Charts format
    """
    import time
    import random
    
    try:
        # Try to get real data from broker client if connected
        if _broker_client and _broker_client.is_connected:
            try:
                log.info(f"📊 Fetching real data for {symbol} from broker...")
                candles = _broker_client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=limit
                )
                if candles and len(candles) > 0:
                    # Convert to Lightweight Charts format
                    chart_data = []
                    for c in candles:
                        chart_data.append({
                            'time': int(c.get('timestamp', c.get('time', 0)) / 1000),
                            'open': float(c.get('open', 0)),
                            'high': float(c.get('high', 0)),
                            'low': float(c.get('low', 0)),
                            'close': float(c.get('close', 0))
                        })
                    log.info(f"📊 Returning {len(chart_data)} real candles for {symbol}")
                    global_state.add_log(f"📊 Chart: {len(chart_data)} candles for {symbol}")
                    return {'candles': chart_data, 'symbol': symbol, 'source': 'angelone'}
                else:
                    log.info(f"📊 No real data from broker, falling back to demo for {symbol}")
            except Exception as e:
                log.warning(f"Failed to get real candle data: {e}, using demo data")
                global_state.add_log(f"⚠️ Chart data error: {e}")
        
        # Generate demo data if no real data available
        log.info(f"📊 Generating demo data for {symbol}")
        now = int(time.time())
        interval_seconds = 5 * 60  # 5 minutes default
        
        # Base prices for different symbols
        base_prices = {
            'RELIANCE': 2500,
            'TCS': 4000,
            'INFY': 1800,
            'HDFCBANK': 1600,
            'ICICIBANK': 1100,
            'SBIN': 800,
            'BHARTIARTL': 1500,
            'ITC': 450,
            'KOTAKBANK': 1800,
            'AXISBANK': 1100,
        }
        
        base_price = base_prices.get(symbol.upper(), 1000)
        price = base_price
        
        chart_data = []
        for i in range(limit, 0, -1):
            candle_time = now - (i * interval_seconds)
            change = (random.random() - 0.5) * base_price * 0.01
            open_price = price
            close_price = price + change
            high_price = max(open_price, close_price) + random.random() * base_price * 0.005
            low_price = min(open_price, close_price) - random.random() * base_price * 0.005
            
            chart_data.append({
                'time': candle_time,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2)
            })
            
            price = close_price
        
        return {'candles': chart_data, 'symbol': symbol, 'demo': True}
        
    except Exception as e:
        log.error(f"Chart data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Broker Connection APIs ====================

# Global broker client
_broker_client = None

@app.get("/api/broker/status")
async def get_broker_status(authenticated: bool = Depends(verify_auth)):
    """Get broker connection status"""
    creds = get_broker_credentials()
    return {
        'is_connected': creds.get('is_connected', False) if creds else False,
        'has_credentials': bool(creds and creds.get('client_id')),
        'client_id': creds.get('client_id', '') if creds else ''
    }

@app.post("/api/broker/credentials")
async def save_credentials(data: BrokerCredentials, authenticated: bool = Depends(verify_auth)):
    """Save broker credentials (Client ID, API Key, PIN)"""
    try:
        success = save_broker_credentials(
            client_id=data.client_id,
            api_key=data.api_key,
            pin=data.pin
        )
        if success:
            return {'status': 'success', 'message': 'Credentials saved successfully'}
        else:
            raise HTTPException(status_code=500, detail='Failed to save credentials')
    except Exception as e:
        log.error(f"Save credentials error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/broker/credentials")
async def get_credentials(authenticated: bool = Depends(verify_auth)):
    """Get saved broker credentials and token status"""
    creds = get_broker_credentials()
    if creds:
        return {
            'client_id': creds.get('client_id', ''),
            'api_key': '****' + creds.get('api_key', '')[-4:] if creds.get('api_key') else '',
            'pin': '****' if creds.get('pin') else '',
            'is_connected': creds.get('is_connected', False),
            'has_jwt_token': bool(creds.get('broker_token')),
            'has_refresh_token': bool(creds.get('refresh_token')),
            'has_feed_token': bool(creds.get('feed_token')),
            'token_expiry': creds.get('token_expiry', '')
        }
    return {'client_id': '', 'api_key': '', 'pin': '', 'is_connected': False}

# ==================== LLM Settings APIs ====================

class LLMSettings(BaseModel):
    llm_provider: str
    api_key: str

@app.get("/api/llm/settings")
async def get_llm_settings_endpoint(authenticated: bool = Depends(verify_auth)):
    """Get saved LLM settings"""
    settings = get_llm_settings()
    if settings:
        # Mask API keys for security
        def mask_key(key):
            if not key or len(key) < 8:
                return ''
            return f"{key[:4]}...{key[-4:]}"
        
        return {
            'llm_provider': settings.get('llm_provider', 'deepseek'),
            'deepseek_api_key': mask_key(settings.get('deepseek_api_key', '')),
            'openai_api_key': mask_key(settings.get('openai_api_key', '')),
            'claude_api_key': mask_key(settings.get('claude_api_key', '')),
            'qwen_api_key': mask_key(settings.get('qwen_api_key', '')),
            'gemini_api_key': mask_key(settings.get('gemini_api_key', ''))
        }
    return {'llm_provider': 'deepseek'}

@app.post("/api/llm/settings")
async def save_llm_settings_endpoint(data: LLMSettings, authenticated: bool = Depends(verify_auth)):
    """Save LLM provider and API key"""
    try:
        success = save_llm_settings(
            llm_provider=data.llm_provider,
            api_key=data.api_key
        )
        if success:
            # Reload config from database
            try:
                from src.config import config
                config.reload_from_database()
                log.info("Config reloaded from database")
            except Exception as e:
                log.warning(f"Could not reload config: {e}")
            
            global_state.add_log(f"🤖 LLM settings saved: {data.llm_provider}")
            return {'status': 'success', 'message': f'LLM settings saved ({data.llm_provider}). Restart recommended for full effect.'}
        else:
            raise HTTPException(status_code=500, detail='Failed to save LLM settings')
    except Exception as e:
        log.error(f"Save LLM settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# AngelOne API Wrapper - Direct REST API (NO SDK)
class BrokerClientWrapper:
    """AngelOne API wrapper using direct REST API calls only"""
    def __init__(self, unused, client_code: str, api_key: str, auth_token: str = None):
        self._client_code = client_code
        self._api_key = api_key
        self._auth_token = auth_token  # JWT token for direct API calls
        self._connected = True
        global_state.add_log(f"🔧 BrokerClientWrapper initialized for {client_code}")
    
    @property
    def is_connected(self):
        return self._connected
    
    @property
    def client_code(self):
        return self._client_code
    
    def _get_api_response(self, endpoint: str, method: str = "GET", payload: dict = None):
        """Make direct API call to AngelOne"""
        import requests
        
        # JWT token - AngelOne returns with "Bearer " prefix
        auth_token = self._auth_token
        if auth_token and not auth_token.startswith('Bearer '):
            auth_token = f'Bearer {auth_token}'
        
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '127.0.0.1',
            'X-ClientPublicIP': '127.0.0.1',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-PrivateKey': self._api_key
        }
        
        url = f"https://apiconnect.angelone.in{endpoint}"
        
        # Debug log
        log.info(f"API Call: {method} {endpoint}")
        log.info(f"API Key: {self._api_key}")
        log.info(f"Token (first 50): {auth_token[:50] if auth_token else 'None'}...")
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            else:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            result = response.json()
            log.info(f"API Response: {result.get('status')}, {result.get('message')}")
            return result
            
            return response.json()
        except Exception as e:
            log.error(f"API call failed: {e}")
            global_state.add_log(f"❌ API call failed: {e}")
            return None
    
    def get_klines(self, symbol: str, interval: str = '5m', limit: int = 100, **kwargs):
        """Get historical candle data using direct REST API"""
        from datetime import datetime, timedelta
        
        interval_map = {
            '1m': 'ONE_MINUTE', '3m': 'THREE_MINUTE', '5m': 'FIVE_MINUTE',
            '10m': 'TEN_MINUTE', '15m': 'FIFTEEN_MINUTE', '30m': 'THIRTY_MINUTE', 
            '1h': 'ONE_HOUR', '1d': 'ONE_DAY'
        }
        ao_interval = interval_map.get(interval, 'FIVE_MINUTE')
        
        symbol_tokens = {
            # Nifty 50 Stocks
            'RELIANCE': '2885', 'TCS': '11536', 'INFY': '1594', 'HDFCBANK': '1333',
            'ICICIBANK': '4963', 'SBIN': '3045', 'BHARTIARTL': '10604', 'ITC': '1660',
            'KOTAKBANK': '1922', 'AXISBANK': '5900', 'HINDUNILVR': '1394', 'LT': '11483',
            'BAJFINANCE': '317', 'MARUTI': '10999', 'ASIANPAINT': '236', 'TITAN': '3506',
            'SUNPHARMA': '3351', 'WIPRO': '3787', 'HCLTECH': '7229', 'ULTRACEMCO': '11532',
            'TATAMOTORS': '3456', 'TATASTEEL': '3499', 'POWERGRID': '14977', 'NTPC': '11630',
            'ONGC': '2083', 'COALINDIA': '20374', 'JSWSTEEL': '11723', 'ADANIENT': '25', 
            'ADANIPORTS': '15083', 'TECHM': '13538', 'BAJAJFINSV': '16675', 'NESTLEIND': '17963',
            'DRREDDY': '881', 'CIPLA': '694', 'DIVISLAB': '10940', 'APOLLOHOSP': '157',
            'EICHERMOT': '910', 'HEROMOTOCO': '1348', 'BPCL': '526', 'GRASIM': '1232',
            'BRITANNIA': '547', 'HINDALCO': '1363', 'INDUSINDBK': '5258', 'TATACONSUM': '3432',
            'M&M': '2031', 'SBILIFE': '21808', 'HDFCLIFE': '467', 'UPL': '11287',
            # Indices
            'NIFTY': '99926000', 'BANKNIFTY': '99926009', 'NIFTYIT': '99926013'
        }
        
        clean_symbol = symbol.upper().replace('-EQ', '').replace('NSE:', '')
        token = symbol_tokens.get(clean_symbol, '2885')
        
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)
        
        global_state.add_log(f"📊 Fetching {clean_symbol} data...")
        
        try:
            payload = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": ao_interval,
                "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
                "todate": to_date.strftime("%Y-%m-%d %H:%M")
            }
            
            response = self._get_api_response("/rest/secure/angelbroking/historical/v1/getCandleData", "POST", payload)
            
            if response and response.get('status') and response.get('data'):
                candles = []
                for c in response['data']:
                    try:
                        ts = c[0]
                        if isinstance(ts, str):
                            if 'T' in ts:
                                ts = datetime.strptime(ts.split('+')[0], "%Y-%m-%dT%H:%M:%S")
                            else:
                                ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                            ts = int(ts.timestamp() * 1000)
                        
                        candles.append({
                            'timestamp': ts,
                            'open': float(c[1]),
                            'high': float(c[2]),
                            'low': float(c[3]),
                            'close': float(c[4]),
                            'volume': float(c[5]) if len(c) > 5 else 0
                        })
                    except Exception as parse_err:
                        log.warning(f"Failed to parse candle: {c}, error: {parse_err}")
                
                global_state.add_log(f"✅ Fetched {len(candles)} candles for {clean_symbol}")
                return candles
            else:
                error_msg = response.get('message', 'Unknown') if response else 'No response'
                global_state.add_log(f"⚠️ {clean_symbol} error: {error_msg}")
                return []
                
        except Exception as e:
            global_state.add_log(f"❌ Failed to fetch {clean_symbol}: {str(e)}")
            return []
    
    def get_ticker_price(self, symbol: str, **kwargs):
        """Get current price using direct REST API"""
        import time
        
        symbol_tokens = {
            # Nifty 50 Stocks
            'RELIANCE': '2885', 'TCS': '11536', 'INFY': '1594', 'HDFCBANK': '1333',
            'ICICIBANK': '4963', 'SBIN': '3045', 'BHARTIARTL': '10604', 'ITC': '1660',
            'KOTAKBANK': '1922', 'AXISBANK': '5900', 'HINDUNILVR': '1394', 'LT': '11483',
            'BAJFINANCE': '317', 'MARUTI': '10999', 'ASIANPAINT': '236', 'TITAN': '3506',
            'SUNPHARMA': '3351', 'WIPRO': '3787', 'HCLTECH': '7229', 'ULTRACEMCO': '11532',
            'TATAMOTORS': '3456', 'TATASTEEL': '3499', 'POWERGRID': '14977', 'NTPC': '11630',
            'ONGC': '2083', 'COALINDIA': '20374', 'JSWSTEEL': '11723', 'ADANIENT': '25', 
            'ADANIPORTS': '15083', 'TECHM': '13538'
        }
        clean_symbol = symbol.upper().replace('-EQ', '').replace('NSE:', '')
        token = symbol_tokens.get(clean_symbol, '2885')
        
        try:
            payload = {"mode": "LTP", "exchangeTokens": {"NSE": [token]}}
            response = self._get_api_response("/rest/secure/angelbroking/market/v1/quote/", "POST", payload)
            
            if response and response.get('status') and response.get('data'):
                fetched = response['data'].get('fetched', [])
                if fetched:
                    price = float(fetched[0].get('ltp', 0))
                    return {'symbol': symbol, 'price': price, 'time': int(time.time() * 1000)}
        except Exception as e:
            log.warning(f"Failed to get ticker: {e}")
        
        return {'symbol': symbol, 'price': 0.0, 'time': 0}
    
    def get_account(self):
        """Get account info using direct REST API"""
        try:
            response = self._get_api_response("/rest/secure/angelbroking/user/v1/getRMS", "GET")
            
            if response and response.get('status') and response.get('data'):
                data = response['data']
                net = float(data.get('net', 0) or data.get('availablecash', 0) or 0)
                available = float(data.get('availablecash', 0) or data.get('net', 0) or 0)
                global_state.add_log(f"💰 Account: Net ₹{net:.2f}, Available ₹{available:.2f}")
                return {'totalBalance': net, 'availableBalance': available, 'totalUnrealizedProfit': 0.0}
            else:
                error_msg = response.get('message', 'Unknown') if response else 'No response'
                global_state.add_log(f"⚠️ RMS error: {error_msg}")
        except Exception as e:
            global_state.add_log(f"⚠️ Account fetch error: {e}")
        
        return {'totalBalance': 0.0, 'availableBalance': 0.0, 'totalUnrealizedProfit': 0.0}
    
    def disconnect(self):
        """Disconnect"""
        try:
            self._get_api_response("/rest/secure/angelbroking/user/v1/logout", "POST", {})
            global_state.add_log(f"🔌 Disconnected from AngelOne")
        except:
            pass
        self._connected = False

@app.post("/api/broker/connect")
async def connect_broker(data: BrokerConnect, authenticated: bool = Depends(verify_auth)):
    """Connect to broker using TOTP code (6-digit) - Direct REST API"""
    global _broker_client
    import requests
    
    try:
        creds = get_broker_credentials()
        if not creds or not creds.get('client_id'):
            global_state.add_log("❌ No credentials saved. Please save credentials first.")
            raise HTTPException(status_code=400, detail='No credentials saved. Please save credentials first.')
        
        totp_code = data.totp.strip()
        
        global_state.add_log(f"🔐 Attempting AngelOne login for client: {creds['client_id']}")
        log.info(f"Attempting AngelOne login for client: {creds['client_id']}")
        
        # Direct REST API login (no SDK)
        login_url = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
        login_payload = {
            "clientcode": creds['client_id'],
            "password": creds['pin'],
            "totp": totp_code
        }
        login_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '127.0.0.1',
            'X-ClientPublicIP': '127.0.0.1',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-PrivateKey': creds['api_key']
        }
        
        resp = requests.post(login_url, json=login_payload, headers=login_headers, timeout=30)
        response = resp.json()
        
        log.info(f"Login response status: {response.get('status')}, message: {response.get('message')}")
        
        if response and response.get('status') and response.get('data'):
            session_data = response['data']
            jwt_token = session_data.get('jwtToken', '')
            refresh_token = session_data.get('refreshToken', '')
            feed_token = session_data.get('feedToken', '')
            
            # Save all tokens to database
            save_broker_token(
                token=jwt_token,
                refresh_token=refresh_token,
                feed_token=feed_token,
                expiry=None  # AngelOne tokens expire at end of day
            )
            
            global_state.add_log(f"✅ Broker connected successfully! Client: {creds['client_id']}")
            global_state.add_log(f"🔑 JWT: {'✓' if jwt_token else '✗'} | Refresh: {'✓' if refresh_token else '✗'} | Feed: {'✓' if feed_token else '✗'}")
            log.info(f"Tokens saved - JWT length: {len(jwt_token)}")
            
            # Create wrapper with auth token for direct API calls
            wrapper = BrokerClientWrapper(None, creds['client_id'], creds['api_key'], jwt_token)
            _broker_client = wrapper
            global_state.exchange_client = wrapper
            
            log.info(f"AngelOne login successful for {creds['client_id']}")
            
            return {
                'status': 'success',
                'message': 'Connected to AngelOne successfully',
                'client_id': creds['client_id'],
                'has_jwt': bool(jwt_token),
                'has_refresh': bool(refresh_token),
                'has_feed': bool(feed_token)
            }
        else:
            error_msg = response.get('message', 'Login failed') if response else 'No response from AngelOne'
            global_state.add_log(f"❌ AngelOne login failed: {error_msg}")
            log.error(f"AngelOne login failed: {error_msg}")
            raise HTTPException(status_code=401, detail=error_msg)
            
    except HTTPException:
        raise
    except Exception as e:
        global_state.add_log(f"❌ Broker connect error: {str(e)}")
        log.error(f"Broker connect error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/broker/disconnect")
async def disconnect_broker(authenticated: bool = Depends(verify_auth)):
    """Disconnect from broker"""
    global _broker_client
    
    try:
        if _broker_client:
            _broker_client.disconnect()
            _broker_client = None
        
        global_state.exchange_client = None
        clear_broker_token()
        
        global_state.add_log("🔌 Broker disconnected")
        return {'status': 'success', 'message': 'Disconnected from broker'}
    except Exception as e:
        log.error(f"Broker disconnect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/broker/test")
async def test_broker_connection(authenticated: bool = Depends(verify_auth)):
    """Test broker connection by fetching data"""
    global _broker_client
    
    results = {
        'connected': False,
        'account': None,
        'ltp': None,
        'historical': None,
        'errors': []
    }
    
    if not _broker_client:
        results['errors'].append("Broker not connected")
        global_state.add_log("⚠️ Test failed: Broker not connected")
        return results
    
    results['connected'] = True
    global_state.add_log("🧪 Testing broker connection...")
    
    # Test 1: Get account info
    try:
        account = _broker_client.get_account()
        results['account'] = account
        global_state.add_log(f"✅ Account test: Net ₹{account.get('totalBalance', 0):.2f}")
    except Exception as e:
        results['errors'].append(f"Account error: {str(e)}")
        global_state.add_log(f"❌ Account test failed: {e}")
    
    # Test 2: Get LTP
    try:
        ltp = _broker_client.get_ticker_price("RELIANCE")
        results['ltp'] = ltp
        if ltp.get('price', 0) > 0:
            global_state.add_log(f"✅ LTP test: RELIANCE ₹{ltp.get('price', 0):.2f}")
        else:
            global_state.add_log(f"⚠️ LTP test: No price data")
    except Exception as e:
        results['errors'].append(f"LTP error: {str(e)}")
        global_state.add_log(f"❌ LTP test failed: {e}")
    
    # Test 3: Get historical data
    try:
        candles = _broker_client.get_klines("RELIANCE", "5m", 10)
        results['historical'] = {
            'count': len(candles) if candles else 0,
            'sample': candles[0] if candles else None
        }
        if candles and len(candles) > 0:
            global_state.add_log(f"✅ Historical test: {len(candles)} candles fetched")
        else:
            global_state.add_log(f"⚠️ Historical test: No candle data")
    except Exception as e:
        results['errors'].append(f"Historical error: {str(e)}")
        global_state.add_log(f"❌ Historical test failed: {e}")
    
    return results

# API Endpoints
@app.get("/api/status")
async def get_status(authenticated: bool = Depends(verify_auth)):
    import time
    
    # Check and update demo expiration status
    if global_state.demo_mode_active and global_state.demo_start_time:
        elapsed = time.time() - global_state.demo_start_time
        if elapsed >= global_state.demo_limit_seconds:
            global_state.demo_expired = True
            if global_state.execution_mode == "Running":
                global_state.execution_mode = "Stopped"
                global_state.add_log("⏰ Demo time expired (20-minute limit), system has automatically stopped. Please configure your own API Key to continue.")
    
    # Calculate demo time remaining
    demo_time_remaining = 0
    if global_state.demo_mode_active and global_state.demo_start_time and not global_state.demo_expired:
        elapsed = time.time() - global_state.demo_start_time
        demo_time_remaining = max(0, global_state.demo_limit_seconds - elapsed)
    
    # Fetch real account data if broker is connected
    account_data = global_state.account_overview.copy()
    broker_connected = False
    
    if _broker_client and _broker_client.is_connected:
        broker_connected = True
        try:
            real_account = _broker_client.get_account()
            if real_account:
                account_data = {
                    "total_equity": real_account.get('totalBalance', 0),
                    "available_balance": real_account.get('availableBalance', 0),
                    "wallet_balance": real_account.get('totalBalance', 0),
                    "total_pnl": real_account.get('totalUnrealizedProfit', 0),
                    "is_real": True  # Flag to indicate real broker data
                }
                # Update global state too
                global_state.account_overview = account_data
        except Exception as e:
            log.warning(f"Failed to fetch real account data: {e}")
    
    data = {
        "system": {
            "running": global_state.is_running,
            "mode": global_state.execution_mode,
            "is_test_mode": global_state.is_test_mode,
            "cycle_counter": global_state.cycle_counter,
            "cycle_interval": global_state.cycle_interval,
            "current_cycle_id": global_state.current_cycle_id,
            "uptime_start": global_state.start_time,
            "last_heartbeat": global_state.last_update,
            "symbols": global_state.symbols  # 🆕 Active trading symbols (AI500 Top5 support)
        },
        "demo": {
            "demo_mode_active": global_state.demo_mode_active,
            "demo_expired": global_state.demo_expired,
            "demo_time_remaining": int(demo_time_remaining)
        },
        "broker": {
            "connected": broker_connected,
            "client_id": _broker_client.client_code if _broker_client else None
        },
        "market": {
            "price": global_state.current_price,
            "regime": global_state.market_regime,
            "position": global_state.price_position
        },
        "agents": {
            "critic_confidence": global_state.critic_confidence,
            "guardian_status": global_state.guardian_status
        },
        "account": account_data,
        "virtual_account": {
            "is_test_mode": global_state.is_test_mode,
            "initial_balance": global_state.virtual_initial_balance,
            "current_balance": global_state.virtual_balance,
            "available_balance": global_state.virtual_balance - sum((pos.get('position_value', 0) / pos.get('leverage', 1)) for pos in global_state.virtual_positions.values()),
            "positions": global_state.virtual_positions,
            "total_unrealized_pnl": sum(pos.get('unrealized_pnl', 0) for pos in global_state.virtual_positions.values())
        },
        "account_alert": {
            "active": global_state.account_alert_active,
            "failure_count": global_state.account_failure_count
        },
        "chart_data": {
            "equity": global_state.equity_history,
            "balance_history": global_state.balance_history,
            "initial_balance": global_state.initial_balance
        },
        "decision": global_state.latest_decision,
        "decision_history": global_state.decision_history[:10],
        "trade_history": global_state.trade_history[:20],
        "logs": global_state.recent_logs[-50:]  # Return latest 50 logs (reversed: newest at end)
    }
    return clean_nans(data)

@app.post("/api/control")
async def control_bot(cmd: ControlCommand, authenticated: bool = Depends(verify_admin)):
    import time
    action = cmd.action.lower()
    
    # Default API key detection (check if user has configured their own key)
    DEFAULT_API_KEY_PREFIX = "sk-"  # Most default keys start with this or are empty
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    # Consider using default API if all keys are empty or match known demo patterns
    is_using_default_api = (
        not deepseek_key or 
        deepseek_key.startswith("demo_") or 
        deepseek_key == "your_deepseek_api_key_here"
    ) and not openai_key and not claude_key
    
    if action == "start":
        # Check if demo has expired
        if global_state.demo_expired:
            raise HTTPException(
                status_code=403, 
                detail="Demo time exhausted (20-minute limit). Please configure your own API Key in Settings > API Keys and try again."
            )
        
        # Activate demo mode if using default API
        if is_using_default_api:
            if not global_state.demo_mode_active:
                global_state.demo_mode_active = True
                global_state.demo_start_time = time.time()
                global_state.add_log("⚠️ Using default API, will auto-stop after 20 minutes. Please configure your own API Key to remove this limit.")
        else:
            # User has their own API key, disable demo mode
            global_state.demo_mode_active = False
            global_state.demo_expired = False
            global_state.demo_start_time = None
        
        global_state.execution_mode = "Running"
        global_state.add_log("▶️ System Resumed by User")
        
    elif action == "pause":
        global_state.execution_mode = "Paused"
        global_state.add_log("⏸️ System Paused by User")
        
    elif action == "stop":
        global_state.execution_mode = "Stopped"
        global_state.add_log("⏹️ System Stopped by User")

    elif action == "set_interval":
        if cmd.interval and cmd.interval in [0.5, 1, 3, 5, 15, 30, 60]:
            global_state.cycle_interval = cmd.interval
            global_state.add_log(f"⏱️ Cycle interval updated to {cmd.interval} minutes")
            return {"status": "success", "interval": cmd.interval}
        else:
            raise HTTPException(status_code=400, detail="Invalid interval. Must be 0.5, 1, 3, 5, 15, 30, or 60 minutes.")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    return {
        "status": "success", 
        "mode": global_state.execution_mode,
        "demo_mode_active": global_state.demo_mode_active,
        "demo_expired": global_state.demo_expired
    }

@app.post("/api/upload_prompt")
async def upload_prompt(file: UploadFile = File(...), authenticated: bool = Depends(verify_admin)):
    try:
        # Determine config directory
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')
        os.makedirs(config_dir, exist_ok=True)
        
        file_path = os.path.join(config_dir, 'custom_prompt.md')
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        global_state.add_log(f"📝 Custom prompt uploaded: {file.filename}")
        log.info(f"Custom prompt saved to: {file_path}")
        return {"status": "success", "message": "Custom prompt uploaded successfully. It will be used in the next decision cycle."}
    except Exception as e:
        log.error(f"Failed to upload prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from src.server.config_manager import ConfigManager
config_manager = ConfigManager(BASE_DIR)

@app.get("/api/config")
async def get_config(authenticated: bool = Depends(verify_auth)):
    """Get current configuration (masked)"""
    return config_manager.get_config()

@app.get("/api/config/prompt")
async def get_prompt_content(authenticated: bool = Depends(verify_auth)):
    """Get content of custom prompt file"""
    return {"content": config_manager.get_prompt()}

@app.post("/api/config")
async def update_config_endpoint(data: dict = Body(...), authenticated: bool = Depends(verify_admin)):
    """Update configuration. On Railway, applies to runtime environment only."""
    success = config_manager.update_config(data, railway_mode=IS_RAILWAY)
    if success:
        if IS_RAILWAY:
            return {
                "status": "success", 
                "message": "✅ Configuration applied to runtime! Note: Changes will take effect immediately but won't persist after Railway redeploys. For permanent settings, add them to Railway Dashboard → Variables."
            }
        else:
            return {"status": "success", "message": "Configuration updated. Please restart the bot if you changed API keys."}
    else:
        raise HTTPException(status_code=500, detail="Failed to update configuration")

@app.post("/api/config/prompt")
async def update_prompt_text(data: dict = Body(...), authenticated: bool = Depends(verify_admin)):
    """Update custom prompt via text editor"""
    content = data.get("content", "")
    success = config_manager.update_prompt(content)
    if success:
        return {"status": "success", "message": "Prompt updated successfully. Will effect next cycle."}
    else:
        raise HTTPException(status_code=500, detail="Failed to save prompt")

@app.get("/api/config/default_prompt")
async def get_default_prompt(authenticated: bool = Depends(verify_auth)):
    """Get the system default prompt template"""
    try:
        from src.config.default_prompt_template import DEFAULT_SYSTEM_PROMPT
        return {"content": DEFAULT_SYSTEM_PROMPT}
    except ImportError:
         raise HTTPException(status_code=500, detail="Default prompt template not found")

# ============================================================================
# Multi-Account API Endpoints
# ============================================================================

from src.exchanges import AccountManager, ExchangeAccount, ExchangeType

# Initialize account manager for API use
_account_manager = None

def get_account_manager():
    """Lazy initialization of account manager"""
    global _account_manager
    if _account_manager is None:
        import os
        from pathlib import Path
        config_path = Path(BASE_DIR) / "config" / "accounts.json"
        _account_manager = AccountManager(str(config_path))
        _account_manager.load_from_file()
    return _account_manager

@app.get("/api/accounts")
async def list_accounts(authenticated: bool = Depends(verify_auth)):
    """List all configured trading accounts"""
    manager = get_account_manager()
    accounts = manager.list_accounts()
    return {
        "accounts": [acc.to_dict() for acc in accounts],
        "count": len(accounts)
    }

@app.get("/api/accounts/{account_id}")
async def get_account(account_id: str, authenticated: bool = Depends(verify_auth)):
    """Get details of a specific account"""
    manager = get_account_manager()
    account = manager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account.to_dict()

class AccountCreate(BaseModel):
    id: str
    name: str
    exchange: str = "binance"
    enabled: bool = True
    testnet: bool = True

@app.post("/api/accounts")
async def create_account(data: AccountCreate, authenticated: bool = Depends(verify_auth)):
    """Create a new trading account"""
    manager = get_account_manager()
    
    # Validate exchange type
    try:
        exchange_type = ExchangeType(data.exchange.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported exchange: {data.exchange}")
    
    # Check if ID already exists
    if manager.get_account(data.id):
        raise HTTPException(status_code=400, detail=f"Account ID already exists: {data.id}")
    
    # Create account (API keys should be set via .env)
    import os
    env_prefix = f"ACCOUNT_{data.id.upper().replace('-', '_')}"
    api_key = os.environ.get(f"{env_prefix}_API_KEY", "")
    secret_key = os.environ.get(f"{env_prefix}_SECRET_KEY", "")
    
    account = ExchangeAccount(
        id=data.id,
        exchange_type=exchange_type,
        account_name=data.name,
        enabled=data.enabled,
        testnet=data.testnet,
        api_key=api_key,
        secret_key=secret_key
    )
    
    manager.add_account(account)
    manager.save_to_file()
    
    global_state.add_log(f"➕ Added account: {data.name} ({data.exchange})")
    return {"status": "success", "account": account.to_dict()}

@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str, authenticated: bool = Depends(verify_auth)):
    """Delete a trading account"""
    manager = get_account_manager()
    
    account = manager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    name = account.account_name
    success = manager.remove_account(account_id)
    
    if success:
        manager.save_to_file()
        global_state.add_log(f"➖ Removed account: {name}")
        return {"status": "success", "message": f"Account '{name}' removed"}
    else:
        raise HTTPException(status_code=500, detail="Failed to remove account")

@app.get("/api/exchanges")
async def list_exchanges(authenticated: bool = Depends(verify_auth)):
    """List supported exchanges"""
    from src.exchanges import get_supported_exchanges
    return {"exchanges": get_supported_exchanges()}

# ============================================================================
# Backtest API Endpoints
# ============================================================================

# Global tracking for active backtest sessions
import asyncio
from collections import defaultdict
from typing import List
import uuid as uuid_lib
from datetime import datetime

class BacktestSession:
    """Track a running backtest session"""
    def __init__(self, session_id: str, config: dict):
        self.session_id = session_id
        self.config = config
        self.status = 'running'  # running, completed, error
        self.progress = 0
        self.current_timepoint = 0
        self.total_timepoints = 0
        self.start_time = datetime.now()
        self.result = None
        self.error = None
        self.subscribers: List[asyncio.Queue] = []  # Multiple clients can subscribe
        self.latest_data = {}  # Store latest progress data for new subscribers

ACTIVE_BACKTESTS: Dict[str, BacktestSession] = {}  # session_id -> BacktestSession

@app.get("/api/backtest/active")
async def get_active_backtests(authenticated: bool = Depends(verify_auth)):
    """Get list of currently running backtests"""
    result = []
    for session_id, session in ACTIVE_BACKTESTS.items():
        result.append({
            'session_id': session_id,
            'symbol': session.config.get('symbol'),
            'status': session.status,
            'progress': session.progress,
            'current_timepoint': session.current_timepoint,
            'total_timepoints': session.total_timepoints,
            'start_time': session.start_time.isoformat(),
            'latest_data': session.latest_data
        })
    return {'active_backtests': result}

@app.get("/api/backtest/subscribe/{session_id}")
async def subscribe_to_backtest(session_id: str, authenticated: bool = Depends(verify_auth)):
    """Subscribe to a running backtest's progress stream"""
    from fastapi.responses import StreamingResponse
    
    if session_id not in ACTIVE_BACKTESTS:
        raise HTTPException(status_code=404, detail="Backtest session not found")
    
    session = ACTIVE_BACKTESTS[session_id]
    
    async def event_generator():
        queue = asyncio.Queue()
        session.subscribers.append(queue)
        
        # First, send the latest state to catch up
        if session.latest_data:
            yield json.dumps({
                'type': 'progress',
                'session_id': session_id,
                **session.latest_data
            }) + '\n'
        
        try:
            while session.status == 'running':
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield json.dumps(data) + '\n'
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield json.dumps({'type': 'keepalive'}) + '\n'
            
            # Session completed, send final result if available
            if session.result:
                yield json.dumps({
                    'type': 'result',
                    'data': session.result,
                    'session_id': session_id
                }) + '\n'
            elif session.error:
                yield json.dumps({
                    'type': 'error',
                    'message': session.error,
                    'session_id': session_id
                }) + '\n'
        finally:
            if queue in session.subscribers:
                session.subscribers.remove(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson"
    )

class BacktestRequest(BaseModel):
    symbol: str = "BTCUSDT"
    start_date: str
    end_date: str
    initial_capital: float = 10000.0
    step: int = 3
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    strategy_mode: str = "technical" # "technical" or "agent"
    use_llm: bool = False  # Enable LLM calls in backtest
    llm_cache: bool = True  # Cache LLM responses
    llm_throttle_ms: int = 100  # Throttle between LLM calls (ms)

@app.post("/api/backtest/run")
async def run_backtest(config: BacktestRequest, authenticated: bool = Depends(verify_auth)):
    """Run a backtest with the given configuration (Streaming)"""
    from src.backtest.engine import BacktestEngine, BacktestConfig
    from fastapi.responses import StreamingResponse
    import asyncio
    import json
    from datetime import datetime
    import uuid
    import math
    import logging

    try:
        # Log received config for debugging
        import logging
        log = logging.getLogger(__name__)
        log.info(f"📋 Backtest request received: symbol={config.symbol}, step={config.step}, dates={config.start_date} to {config.end_date}")
        
        bt_config = BacktestConfig(
            symbol=config.symbol,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
            step=config.step,
            stop_loss_pct=config.stop_loss_pct,
            take_profit_pct=config.take_profit_pct,
            strategy_mode='agent',  # Force Multi-Agent Mode
            use_llm=True,  # Force LLM ON for agent mode (required for prompt rules)
            llm_cache=config.llm_cache,  # Cache LLM responses
            llm_throttle_ms=config.llm_throttle_ms  # Rate limiting
        )
        
        engine = BacktestEngine(bt_config)
        
        # Create session for tracking
        session_id = str(uuid.uuid4())[:8]
        session = BacktestSession(session_id, {
            'symbol': config.symbol,
            'start_date': config.start_date,
            'end_date': config.end_date,
            'step': config.step
        })
        ACTIVE_BACKTESTS[session_id] = session
        
        # Generator for Streaming Response
        async def event_generator():
            queue = asyncio.Queue()
            
            # Progress callback (Async) - receives a dict from engine
            async def progress_callback(data: dict):
                # Extract data from the dict
                progress = data.get('progress', 0)
                current = data.get('current_timepoint', 0)
                total = data.get('total_timepoints', 0)
                
                # Update session state
                session.progress = progress
                session.current_timepoint = current
                session.total_timepoints = total
                
                progress_msg = {
                    "type": "progress",
                    "session_id": session_id,
                    "current": current,
                    "total": total,
                    "percent": round(progress, 1),
                    "current_timepoint": current,
                    "total_timepoints": total,
                    "current_equity": data.get('current_equity'),
                    "profit": data.get('profit'),
                    "profit_pct": data.get('profit_pct'),
                    "equity_point": data.get('latest_equity_point'),
                    "recent_trades": data.get('latest_trade'),
                    "metrics": data.get('metrics')
                }
                
                # Store latest data for reconnecting subscribers
                session.latest_data = progress_msg
                
                # Send to main queue
                await queue.put(progress_msg)
                
                # Notify all subscribers
                for subscriber_queue in session.subscribers:
                    try:
                        subscriber_queue.put_nowait(progress_msg)
                    except asyncio.QueueFull:
                        pass  # Skip if queue is full
            
            # Run engine in background task
            async def run_engine():
                try:
                    result = await engine.run(progress_callback=progress_callback)
                    
                    # --- Data Processing ---
                    equity_curve = []
                    for _, row in result.equity_curve.iterrows():
                        equity_curve.append({
                            'timestamp': row.name.isoformat() if hasattr(row.name, 'isoformat') else str(row.name),
                            'total_equity': float(row['total_equity']),
                            'drawdown_pct': float(row['drawdown_pct'])
                        })
                    
                    trades = []
                    for t in result.trades:
                        trades.append({
                            'trade_id': getattr(t, 'trade_id', str(uuid.uuid4())),
                            'symbol': t.symbol,
                            'side': t.side.value,
                            'action': t.action,
                            'quantity': float(t.quantity or 0),
                            'price': float(t.price or 0),
                            'timestamp': t.timestamp.isoformat(),
                            'pnl': float(t.pnl or 0),
                            'pnl_pct': float(t.pnl_pct or 0),
                            'entry_price': float(t.entry_price or 0),
                            'holding_time': float(t.holding_time or 0),
                            'close_reason': t.close_reason
                        })

                    # --- Extract Decisions ---
                    decisions = []
                    # Filter: Last 50 + any non-hold action
                    filtered_decisions = [d for d in result.decisions if d.get('action') != 'hold']
                    filtered_decisions += result.decisions[-50:] # Add last 50
                    
                    # Deduplicate by timestamp if needed, but simple list is fine for now
                    # Sanitize
                    for d in filtered_decisions:
                         decisions.append({
                            'timestamp': d.get('timestamp').isoformat() if hasattr(d.get('timestamp'), 'isoformat') else str(d.get('timestamp')),
                            'action': d.get('action'),
                            'confidence': d.get('confidence'),
                            'reason': d.get('reason'),
                            'vote_details': d.get('vote_details'),
                            'price': float(d.get('price', 0))
                         })
                    
                    # Helper for NaNs
                    def recursive_clean(obj):
                        if isinstance(obj, float):
                            if math.isnan(obj) or math.isinf(obj): return 0.0
                            return obj
                        if isinstance(obj, dict):
                            return {k: recursive_clean(v) for k, v in obj.items()}
                        if isinstance(obj, list):
                            return [recursive_clean(v) for v in obj]
                        return obj

                    response_data = recursive_clean({
                        'metrics': result.metrics.to_dict(),
                        'equity_curve': equity_curve,
                        'trades': trades,
                        'duration_seconds': result.duration_seconds,
                        'decisions': decisions
                    })

                    # --- 1. Database Storage (First to get ID) ---
                    db_id = None
                    run_id = f"bt_{uuid.uuid4().hex[:12]}"
                    
                    try:
                        from src.backtest.storage import BacktestStorage
                        storage = BacktestStorage()
                        
                        db_id = storage.save_backtest(
                            run_id=run_id,
                            config=config.dict(),
                            metrics=response_data['metrics'],
                            trades=trades,
                            equity_curve=equity_curve
                        )
                        
                        if db_id:
                             print(f"📊 Backtest saved to DB: #{db_id} ({run_id})")
                             response_data['run_id'] = run_id
                             response_data['id'] = db_id
                        else:
                             print(f"⚠️ Backtest save returned None")
                             
                    except Exception as db_err:
                        print(f"⚠️ DB save failed: {db_err}")

                    # --- 2. Comprehensive Folder Logging (Now uses DB ID) ---
                    try:
                        run_time = datetime.now()
                        clean_start = config.start_date.replace('-', '').replace('/', '')
                        clean_end = config.end_date.replace('-', '').replace('/', '')
                        id_str = f"id{db_id}" if db_id else "id_unknown"
                        
                        # Create dedicated folder for this backtest
                        folder_name = f"{run_time.strftime('%Y%m%d_%H%M%S')}_{id_str}_{clean_start}_{clean_end}"
                        backtest_dir = os.path.join(BASE_DIR, 'logs', 'backtest', folder_name)
                        os.makedirs(backtest_dir, exist_ok=True)
                        
                        # 1. Save config
                        config_path = os.path.join(backtest_dir, 'config.json')
                        with open(config_path, 'w', encoding='utf-8') as f:
                            json.dump({
                                'id': db_id,
                                'run_id': run_id,
                                'run_time': run_time.isoformat(),
                                'config': config.dict()
                            }, f, indent=2, ensure_ascii=False)
                        
                        # 2. Save results summary
                        results_path = os.path.join(backtest_dir, 'results.json')
                        with open(results_path, 'w', encoding='utf-8') as f:
                            json.dump({
                                'id': db_id,
                                'run_id': run_id,
                                'metrics': response_data['metrics'],
                                'duration_seconds': result.duration_seconds
                            }, f, indent=2, ensure_ascii=False)
                        
                        # 3. Save all trades
                        trades_path = os.path.join(backtest_dir, 'trades.json')
                        with open(trades_path, 'w', encoding='utf-8') as f:
                            json.dump({
                                'total_trades': len(trades),
                                'trades': trades
                            }, f, indent=2, ensure_ascii=False)
                        
                        # 4. Save equity curve
                        equity_path = os.path.join(backtest_dir, 'equity_curve.json')
                        with open(equity_path, 'w', encoding='utf-8') as f:
                            json.dump({
                                'equity_curve': equity_curve
                            }, f, indent=2, ensure_ascii=False)
                        
                        # 5. Save decisions (agent processing data)
                        decisions_path = os.path.join(backtest_dir, 'decisions.json')
                        with open(decisions_path, 'w', encoding='utf-8') as f:
                            json.dump({
                                'total_decisions': len(decisions),
                                'decisions': decisions
                            }, f, indent=2, ensure_ascii=False)
                        
                        # 6. Save K-line data (input data for analysis)
                        kline_dir = os.path.join(backtest_dir, 'kline_data')
                        os.makedirs(kline_dir, exist_ok=True)
                        
                        # Get K-line data from engine's data replay
                        if hasattr(engine, 'data_replay') and engine.data_replay:
                            data_cache = engine.data_replay.data_cache
                            
                            # Save 5m K-line data
                            if hasattr(data_cache, 'df_5m') and data_cache.df_5m is not None:
                                df_5m_path = os.path.join(kline_dir, 'kline_5m.csv')
                                data_cache.df_5m.to_csv(df_5m_path)
                            
                            # Save 15m K-line data
                            if hasattr(data_cache, 'df_15m') and data_cache.df_15m is not None:
                                df_15m_path = os.path.join(kline_dir, 'kline_15m.csv')
                                data_cache.df_15m.to_csv(df_15m_path)
                            
                            # Save 1h K-line data
                            if hasattr(data_cache, 'df_1h') and data_cache.df_1h is not None:
                                df_1h_path = os.path.join(kline_dir, 'kline_1h.csv')
                                data_cache.df_1h.to_csv(df_1h_path)
                        
                        # 7. Save LLM logs (if any)
                        llm_log_count = 0
                        if hasattr(engine, 'agent_runner') and engine.agent_runner and hasattr(engine.agent_runner, 'llm_logs'):
                            llm_logs = engine.agent_runner.llm_logs
                            if llm_logs:
                                llm_dir = os.path.join(backtest_dir, 'llm_logs')
                                os.makedirs(llm_dir, exist_ok=True)
                                
                                for idx, log_entry in enumerate(llm_logs):
                                    # Create markdown file for each LLM interaction
                                    log_filename = f"llm_log_{idx+1:04d}_{log_entry['timestamp'].replace(':', '').replace('-', '')[:15]}.md"
                                    log_path = os.path.join(llm_dir, log_filename)
                                    
                                    # Format as markdown
                                    md_content = f"""# LLM Decision Log #{idx+1}

**Timestamp**: {log_entry['timestamp']}

## Market Context

{log_entry['context']}

## LLM Response

```json
{json.dumps(log_entry['llm_response'], indent=2, ensure_ascii=False)}
```

## Final Decision

- **Action**: {log_entry['final_decision']['action']}
- **Confidence**: {log_entry['final_decision']['confidence']}%
- **Reason**: {log_entry['final_decision']['reason']}
"""
                                    with open(log_path, 'w', encoding='utf-8') as f:
                                        f.write(md_content)
                                
                                llm_log_count = len(llm_logs)
                        
                        print(f"📁 Backtest data saved to folder: {backtest_dir}")
                        print(f"   ├── config.json (input configuration)")
                        print(f"   ├── results.json (metrics summary)")
                        print(f"   ├── trades.json ({len(trades)} trades)")
                        print(f"   ├── equity_curve.json ({len(equity_curve)} points)")
                        print(f"   ├── decisions.json ({len(decisions)} agent decisions)")
                        print(f"   ├── kline_data/ (5m, 15m, 1h K-line CSV files)")
                        if llm_log_count > 0:
                            print(f"   └── llm_logs/ ({llm_log_count} LLM interactions)")
                    except Exception as log_err:
                        print(f"⚠️ Folder logging failed: {log_err}")

                    # --- 3. Send Final Result ---
                    result_msg = {
                        "type": "result",
                        "session_id": session_id,
                        "data": response_data
                    }
                    
                    # Update session status
                    session.status = 'completed'
                    session.result = response_data
                    
                    # Notify all subscribers
                    for subscriber_queue in session.subscribers:
                        try:
                            subscriber_queue.put_nowait(result_msg)
                        except asyncio.QueueFull:
                            pass
                    
                    await queue.put(result_msg)
                    
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    error_msg = {"type": "error", "session_id": session_id, "message": str(e)}
                    
                    # Update session status
                    session.status = 'error'
                    session.error = str(e)
                    
                    # Notify subscribers
                    for subscriber_queue in session.subscribers:
                        try:
                            subscriber_queue.put_nowait(error_msg)
                        except asyncio.QueueFull:
                            pass
                    
                    await queue.put(error_msg)
                finally:
                    await queue.put(None) # End of stream
                    # Clean up session after 5 minutes
                    async def cleanup_session():
                        await asyncio.sleep(300)  # 5 minutes
                        if session_id in ACTIVE_BACKTESTS:
                            del ACTIVE_BACKTESTS[session_id]
                    asyncio.create_task(cleanup_session())

            # Start the engine task
            asyncio.create_task(run_engine())
            
            # Stream Loop
            while True:
                data = await queue.get()
                if data is None:
                    break
                yield json.dumps(data) + "\n"
        
        return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest/history")
async def get_backtest_history(authenticated: bool = Depends(verify_auth)):
    """Get list of saved backtest reports"""
    reports_dir = os.path.join(BASE_DIR, 'reports')
    if not os.path.exists(reports_dir):
        return {"reports": []}
    
    reports = []
    for f in os.listdir(reports_dir):
        if f.endswith('.html') and f.startswith('backtest_'):
            path = os.path.join(reports_dir, f)
            reports.append({
                'filename': f,
                'path': f'/reports/{f}',
                'created': os.path.getmtime(path)
            })
    
    reports.sort(key=lambda x: x['created'], reverse=True)
    return {"reports": reports[:20]}

# Authentication middleware for protected static files
@app.middleware("http")
async def protect_backtest_page(request: Request, call_next):
    """Protect backtest.html from direct access without authentication"""
    # Check if accessing backtest.html directly
    # --- AUTHENTICATION MIDDLEWARE ---
    path = request.url.path
    
    # Define protected extensions and exempt paths
    is_protected_type = path.endswith('.html') or path == '/' or path == '/backtest'
    exempt_paths = ['/login', '/login.html', '/api/login', '/api/info']
    
    # Allow assets (js, css, etc.)
    is_asset = path.startswith('/static/') and not path.endswith('.html')
    
    if is_protected_type and path not in exempt_paths and not is_asset:
        try:
            # Check cookie
            verify_auth(request)
        except HTTPException:
            # Redirect to login if not authenticated
            return RedirectResponse("/login", status_code=302)
    
    response = await call_next(request)
    return response

# Serve Static Files
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

# Serve Reports Directory
reports_dir = os.path.join(BASE_DIR, 'reports')
if os.path.exists(reports_dir):
    app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")

# Root Route -> Checks login
@app.get("/")
async def read_root(request: Request):
    # Check if authenticated
    try:
        verify_auth(request)
        return FileResponse(os.path.join(WEB_DIR, 'index.html'))
    except HTTPException:
        return RedirectResponse("/login")

@app.get("/login")
async def read_login():
    return FileResponse(os.path.join(WEB_DIR, 'login.html'))

# ==================== Backtest Analytics APIs ====================

@app.get("/api/backtest/list")
async def list_backtests(symbol: Optional[str] = None, limit: int = 100, 
                        authenticated: bool = Depends(verify_auth)):
    """List all backtest runs with optional filtering"""
    try:
        from src.backtest.storage import BacktestStorage
        storage = BacktestStorage()
        results = storage.list_backtests(symbol=symbol, limit=limit)
        return {"status": "success", "backtests": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backtest/compare")
async def compare_backtests(request: Dict, authenticated: bool = Depends(verify_auth)):
    """Compare multiple backtest runs"""
    try:
        from src.backtest.analytics import BacktestAnalytics
        
        run_ids = request.get('run_ids', [])
        if not run_ids:
            raise HTTPException(status_code=400, detail="run_ids required")
        
        analytics = BacktestAnalytics()
        comparison = analytics.compare_runs(run_ids)
        
        return {
            "status": "success",
            "comparison": comparison.to_dict(orient='records')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest/trends")
async def get_performance_trends(symbol: str, days: int = 30,
                                authenticated: bool = Depends(verify_auth)):
    """Get performance trends over time"""
    try:
        from src.backtest.analytics import BacktestAnalytics
        
        analytics = BacktestAnalytics()
        trends = analytics.get_performance_trends(symbol=symbol, days=days)
        
        return {"status": "success", "trends": trends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest/optimize/suggest")
async def suggest_optimal_parameters(symbol: str, target: str = 'sharpe',
                                    authenticated: bool = Depends(verify_auth)):
    """Get optimal parameter suggestions"""
    try:
        from src.backtest.analytics import BacktestAnalytics
        
        if target not in ['sharpe', 'return', 'drawdown']:
            raise HTTPException(status_code=400, detail="Invalid target")
        
        analytics = BacktestAnalytics()
        suggestions = analytics.suggest_optimal_parameters(symbol=symbol, target=target)
        
        return {"status": "success", "suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest/analyze/{run_id}")
async def analyze_backtest(run_id: str, authenticated: bool = Depends(verify_auth)):
    """Get detailed analysis for a specific backtest"""
    try:
        from src.backtest.analytics import BacktestAnalytics
        
        analytics = BacktestAnalytics()
        
        # Get win rate analysis
        win_analysis = analytics.get_win_rate_analysis(run_id)
        
        # Get risk metrics
        risk_metrics = analytics.calculate_risk_metrics(run_id)
        
        return {
            "status": "success",
            "run_id": run_id,
            "win_rate_analysis": win_analysis,
            "risk_metrics": risk_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest/export/{run_id}")
async def export_backtest(run_id: str, format: str = 'csv',
                         authenticated: bool = Depends(verify_auth)):
    """Export backtest data"""
    try:
        from src.backtest.storage import BacktestStorage
        import tempfile
        import shutil
        
        if format not in ['csv', 'json']:
            raise HTTPException(status_code=400, detail="Invalid format")
        
        storage = BacktestStorage()
        
        if format == 'csv':
            # Export to temporary directory
            temp_dir = tempfile.mkdtemp()
            storage.export_to_csv(run_id, temp_dir)
            
            # Create zip file
            import zipfile
            zip_path = f"{temp_dir}/{run_id}.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in os.listdir(temp_dir):
                    if file.endswith(('.csv', '.json')):
                        zipf.write(os.path.join(temp_dir, file), file)
            
            return FileResponse(zip_path, filename=f"{run_id}.zip")
        
        else:  # json
            data = storage.get_backtest(run_id)
            if not data:
                raise HTTPException(status_code=404, detail="Backtest not found")
            
            return {"status": "success", "data": data}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/backtest/{run_id}")
async def delete_backtest(run_id: str, authenticated: bool = Depends(verify_auth)):
    """Delete a backtest"""
    try:
        from src.backtest.storage import BacktestStorage
        
        storage = BacktestStorage()
        success = storage.delete_backtest(run_id)
        
        if success:
            return {"status": "success", "message": "Backtest deleted"}
        else:
            raise HTTPException(status_code=404, detail="Backtest not found")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Page Routes ====================

@app.get("/backtest")
async def read_backtest(request: Request):
    """Backtest page"""
    try:
        verify_auth(request)
        return FileResponse(os.path.join(WEB_DIR, 'backtest.html'))
    except HTTPException:
        return RedirectResponse("/login")
