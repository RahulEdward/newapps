"""
AngelOne API Test Script - Direct REST API Only (NO SDK)
Run: python test_angelone.py
Enter TOTP when prompted
"""

import requests
import json
from datetime import datetime, timedelta

# Your AngelOne Credentials
CLIENT_ID = "LLVR1277"
API_KEY = "z6DaAedv"
PIN = "2105"

BASE_URL = "https://apiconnect.angelone.in"

def get_headers(api_key, jwt_token=None):
    """Get API headers"""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-UserType': 'USER',
        'X-SourceID': 'WEB',
        'X-ClientLocalIP': '127.0.0.1',
        'X-ClientPublicIP': '127.0.0.1',
        'X-MACAddress': '00:00:00:00:00:00',
        'X-PrivateKey': api_key
    }
    if jwt_token:
        headers['Authorization'] = jwt_token if jwt_token.startswith('Bearer ') else f'Bearer {jwt_token}'
    return headers

def test_login():
    print("=" * 60)
    print("AngelOne API Test (Direct REST API - NO SDK)")
    print("=" * 60)
    
    totp = input("\n🔐 Enter 6-digit TOTP: ").strip()
    
    if len(totp) != 6:
        print("❌ TOTP must be 6 digits")
        return
    
    print(f"\n📡 Logging in as {CLIENT_ID}...")
    
    # Login via REST API
    login_url = f"{BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword"
    login_payload = {
        "clientcode": CLIENT_ID,
        "password": PIN,
        "totp": totp
    }
    
    resp = requests.post(login_url, json=login_payload, headers=get_headers(API_KEY), timeout=30)
    login_data = resp.json()
    
    print(f"\nLogin Response: {json.dumps(login_data, indent=2)}")
    
    if not login_data.get('status'):
        print(f"\n❌ Login Failed: {login_data.get('message')}")
        return
    
    jwt_token = login_data['data'].get('jwtToken', '')
    print(f"\n✅ Login Success! Token: {jwt_token[:40]}...")
    
    headers = get_headers(API_KEY, jwt_token)
    
    # Test 1: RMS (Account Balance)
    print("\n" + "=" * 40)
    print("Test 1: Account Balance (RMS)")
    print("=" * 40)
    
    url = f"{BASE_URL}/rest/secure/angelbroking/user/v1/getRMS"
    resp = requests.get(url, headers=headers, timeout=30)
    rms = resp.json()
    print(f"Response: {json.dumps(rms, indent=2)}")
    
    if rms.get('status') and rms.get('data'):
        print(f"\n💰 Balance: ₹{rms['data'].get('net', 0)}")
    
    # Test 2: Historical Data
    print("\n" + "=" * 40)
    print("Test 2: Historical Data (RELIANCE)")
    print("=" * 40)
    
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5)
    
    url = f"{BASE_URL}/rest/secure/angelbroking/historical/v1/getCandleData"
    payload = {
        "exchange": "NSE",
        "symboltoken": "2885",
        "interval": "FIVE_MINUTE",
        "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
        "todate": to_date.strftime("%Y-%m-%d %H:%M")
    }
    
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    hist = resp.json()
    
    if hist.get('status') and hist.get('data'):
        print(f"✅ Got {len(hist['data'])} candles!")
        print(f"Latest: {hist['data'][-1]}")
    else:
        print(f"❌ Error: {hist.get('message')}")
    
    # Test 3: LTP
    print("\n" + "=" * 40)
    print("Test 3: LTP (RELIANCE)")
    print("=" * 40)
    
    url = f"{BASE_URL}/rest/secure/angelbroking/market/v1/quote/"
    payload = {"mode": "LTP", "exchangeTokens": {"NSE": ["2885"]}}
    
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    ltp = resp.json()
    
    if ltp.get('status') and ltp.get('data'):
        fetched = ltp['data'].get('fetched', [])
        if fetched:
            print(f"✅ RELIANCE LTP: ₹{fetched[0].get('ltp', 0)}")
    else:
        print(f"❌ Error: {ltp.get('message')}")
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_login()
