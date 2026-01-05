from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, AngelOneCredential, SymToken
from auth.dependencies import get_current_user
from broker.angelone.client import AngelOneClient
import requests
import pandas as pd
from datetime import datetime
from broker.angelone.schemas import AngelOneLoginRequest
from pydantic import BaseModel

router = APIRouter(
    prefix="/brokers/angelone",
    tags=["Angel One Broker"]
)

# In-memory session store: client_code -> AngelOneClient
angel_sessions = {}

def _perform_bulk_import(db: Session):
    """Internal helper to import scrip master using pandas processing"""
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    try:
        print("Downloading Angel One Scrip Master...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Save to temp for pandas
        temp_path = "angel_temp.json"
        with open(temp_path, "wb") as f:
            f.write(response.content)
            
        print("Processing data with pandas...")
        df = pd.read_json(temp_path)
        
        # Renaissance transformations from user example
        df = df.rename(columns={
            'exch_seg': 'exchange',
            'lotsize': 'lotsize',
            'strike': 'strike',
            'symbol': 'symbol',
            'token': 'token',
            'name': 'name',
            'tick_size': 'tick_size'
        })
        
        df['brsymbol'] = df['symbol']
        df['brexchange'] = df['exchange']

        # Update exchange names
        df.loc[(df['instrumenttype'] == 'AMXIDX') & (df['exchange'] == 'NSE'), 'exchange'] = 'NSE_INDEX'
        df.loc[(df['instrumenttype'] == 'AMXIDX') & (df['exchange'] == 'BSE'), 'exchange'] = 'BSE_INDEX'
        df.loc[(df['instrumenttype'] == 'AMXIDX') & (df['exchange'] == 'MCX'), 'exchange'] = 'MCX_INDEX'
        
        # Reformat symbol
        df['symbol'] = df['symbol'].str.replace('-EQ|-BE|-MF|-SG', '', regex=True)
        
        # Expiry conversion
        def convert_date(date_str):
            try:
                return datetime.strptime(date_str, '%d%b%Y').strftime('%d-%b-%y').upper()
            except:
                return str(date_str).upper()
        
        if 'expiry' in df.columns:
            df['expiry'] = df['expiry'].apply(lambda x: convert_date(x) if pd.notnull(x) and x != '' else x)

        # Scale values
        df['strike'] = df['strike'].astype(float) / 100
        df.loc[(df['instrumenttype'] == 'OPTCUR') & (df['exchange'] == 'CDS'), 'strike'] = df['strike'].astype(float) / 1000
        df['lotsize'] = pd.to_numeric(df['lotsize'], errors='coerce').fillna(1).astype(int)
        df['tick_size'] = df['tick_size'].astype(float) / 100

        # Special symbol updates for CDS/MCX/BFO (Simpler version of user's complex logic)
        # Naming normalization
        df['symbol'] = df['symbol'].replace({
            'Nifty 50': 'NIFTY',
            'Nifty Next 50': 'NIFTYNXT50',
            'Nifty Fin Service': 'FINNIFTY',
            'Nifty Bank': 'BANKNIFTY',
            'NIFTY MID SELECT': 'MIDCPNIFTY',
            'India VIX': 'INDIAVIX',
            'SNSX50': 'SENSEX50'
        })

        # Clear existing
        db.query(SymToken).delete()
        db.commit()
        
        # Bulk Insert
        data_dict = df.to_dict(orient='records')
        chunk_size = 5000
        for i in range(0, len(data_dict), chunk_size):
            db.bulk_insert_mappings(SymToken, data_dict[i : i + chunk_size])
            db.commit()
            
        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        print(f"Imported {len(data_dict)} tokens into symtoken table.")
        return True
    except Exception as e:
        print(f"Auto-import error: {e}")
        return False

class AngelOneConfig(BaseModel):
    api_key: str
    client_code: str
    pin: str
    totp_secret: str | None = None

@router.post("/configure")
def configure_angelone(
    config: AngelOneConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(f"Configuring Angel One for user {current_user.email}: {config.client_code}")
    
    # Validate TOTP secret - should be base32 string, not 6-digit code
    totp_secret_to_save = config.totp_secret
    if totp_secret_to_save:
        # Remove spaces and convert to uppercase
        totp_secret_to_save = totp_secret_to_save.strip().replace(" ", "").upper()
        
        # Check if it's a 6-digit code (likely user mistake, they entered the OTP instead of Secret)
        if totp_secret_to_save.isdigit() and len(totp_secret_to_save) == 6:
            # Do NOT raise error, just ignore it so we don't save the dynamic code as a static secret
            totp_secret_to_save = None
        
        # Validate base32 format (if it's not None and not the 6-digit code case above)
        elif len(totp_secret_to_save) < 10:
             raise HTTPException(
                status_code=400,
                detail="TOTP Secret too short. Please enter the full secret key from your authenticator app."
            )
    
    # Check if exists
    existing = db.query(AngelOneCredential).filter(
        AngelOneCredential.user_id == current_user.id,
        AngelOneCredential.client_code == config.client_code
    ).first()

    if existing:
        existing.api_key = config.api_key
        existing.pin = config.pin
        existing.totp_secret = totp_secret_to_save if totp_secret_to_save else None
        existing.is_active = True
    else:
        new_cred = AngelOneCredential(
            user_id=current_user.id,
            api_key=config.api_key,
            client_code=config.client_code,
            pin=config.pin,
            totp_secret=totp_secret_to_save if totp_secret_to_save else None
        )
        db.add(new_cred)
    
    db.commit()
    return {"status": "success", "message": "Angel One credentials saved"}

@router.post("/login")
def login_angelone_session(
    client_code: str,
    totp: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Fetch credentials
    creds = db.query(AngelOneCredential).filter(
        AngelOneCredential.user_id == current_user.id,
        AngelOneCredential.client_code == client_code
    ).first()

    if not creds:
        raise HTTPException(status_code=404, detail="Credentials not found")
    
    client = AngelOneClient(api_key=creds.api_key)
    
    # Use provided TOTP or generate from secret if implemented
    otp_to_use = totp
    if not otp_to_use and creds.totp_secret:
        import pyotp
        totp_obj = pyotp.TOTP(creds.totp_secret)
        otp_to_use = totp_obj.now()
    
    if not otp_to_use:
        raise HTTPException(status_code=400, detail="TOTP required")

    print(f"Attempting login for {client_code} with TOTP: {otp_to_use}")
    result = client.login(
        client_code=creds.client_code,
        pin=creds.pin,
        totp=otp_to_use
    )
    print(f"Login result for {client_code}: {result}")
    
    if result.get("status"):
        # Save tokens to database for persistence
        creds.jwt_token = result['data']['jwtToken']
        creds.refresh_token = result['data']['refreshToken']
        creds.feed_token = result['data'].get('feedToken')  # Save feed token too
        db.commit()  # Commit to save tokens to database
        
        angel_sessions[client_code] = client

        # AUTO-IMPORT: Check if instruments are empty
        instrument_count = db.query(SymToken).count()
        if instrument_count == 0:
            print("Instruments table empty. Starting auto-import...")
            _perform_bulk_import(db)

        return {"status": "success", "message": "Logged in to Angel One", "data": result['data']}
    else:
        raise HTTPException(status_code=400, detail=result.get("message"))

@router.get("/profile")
def get_angelone_profile(
    client_code: str,
    current_user: User = Depends(get_current_user)
):
    if client_code not in angel_sessions:
        raise HTTPException(status_code=400, detail="Session not active. Please login first.")
    
    return angel_sessions[client_code].get_profile()

@router.get("/holdings")
def get_angelone_holdings(
    client_code: str,
    current_user: User = Depends(get_current_user)
):
    if client_code not in angel_sessions:
        raise HTTPException(status_code=400, detail="Session not active. Please login first.")
    return angel_sessions[client_code].get_holdings()

@router.get("/positions")
def get_angelone_positions(
    client_code: str,
    current_user: User = Depends(get_current_user)
):
    if client_code not in angel_sessions:
        raise HTTPException(status_code=400, detail="Session not active. Please login first.")
    return angel_sessions[client_code].get_positions()

@router.get("/orders")
async def get_angelone_orders(
    client_code: str,
    current_user: User = Depends(get_current_user)
):
    if client_code not in angel_sessions:
        raise HTTPException(status_code=400, detail="Session not active. Please login first.")
    return angel_sessions[client_code].get_order_book()

@router.get("/ltp")
async def get_angelone_ltp(
    client_code: str,
    exchange: str,
    symbol: str,
    token: str,
    current_user: User = Depends(get_current_user)
):
    if client_code not in angel_sessions:
        raise HTTPException(status_code=400, detail="Session not active")
    return angel_sessions[client_code].get_ltp(exchange, symbol, token)


@router.delete("/{cred_id}")
async def delete_angelone_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cred = db.query(AngelOneCredential).filter(
        AngelOneCredential.id == cred_id,
        AngelOneCredential.user_id == current_user.id
    ).first()
    
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    
    # Remove from memory session if exists
    if cred.client_code in angel_sessions:
        del angel_sessions[cred.client_code]
        
    db.delete(cred)
    db.commit()
    return {"status": "success", "message": "Broker deleted successfully"}

@router.post("/logout")
async def logout_angelone(
    client_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cred = db.query(AngelOneCredential).filter(
        AngelOneCredential.client_code == client_code,
        AngelOneCredential.user_id == current_user.id
    ).first()
    
    if cred:
        cred.jwt_token = None
        cred.refresh_token = None
        cred.feed_token = None
        db.commit()
        
    if client_code in angel_sessions:
        del angel_sessions[client_code]
        
    return {"status": "success", "message": "Logged out from broker"}

@router.get("/instruments")
async def get_instruments(
    q: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search instruments from database.
    """
    query = db.query(SymToken)
    if q:
        query = query.filter(SymToken.symbol.contains(q.upper()))
    
    instruments = query.limit(limit).all()
    
    # Convert to dict for JSON response
    return [{
        "id": inst.id,
        "symbol": inst.symbol,
        "brsymbol": inst.brsymbol,
        "name": inst.name,
        "exchange": inst.exchange,
        "brexchange": inst.brexchange,
        "token": inst.token,
        "expiry": inst.expiry,
        "strike": inst.strike,
        "lotsize": inst.lotsize,
        "instrumenttype": inst.instrumenttype,
        "tick_size": inst.tick_size
    } for inst in instruments]


@router.post("/import-instruments")
async def import_instruments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download and import Angel One symbol master data manually.
    """
    success = _perform_bulk_import(db)
    if success:
        return {"status": "success", "message": "Successfully imported instruments"}
    else:
        raise HTTPException(status_code=500, detail="Failed to import data")
