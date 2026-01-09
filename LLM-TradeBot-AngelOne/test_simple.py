"""
Simple AngelOne API Test - Direct REST API only
No SDK, no complexity - just raw API calls
"""
import requests
import json

# Credentials
CLIENT_ID = "LLVR1277"
API_KEY = "z6DaAedv"
PIN = "2105"

def login_and_test():
    print("=" * 50)
    print("Simple AngelOne Test")
    print("=" * 50)
    
    totp = input("\n🔐 Enter 6-digit TOTP: ").strip()
    
    # Step 1: Login via REST API directly
    print("\n📡 Logging in...")
    
    login_url = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
    login_payload = {
        "clientcode": CLIENT_ID,
        "password": PIN,
        "totp": totp
    }
    login_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-UserType': 'USER',
        'X-SourceID': 'WEB',
        'X-ClientLocalIP': '127.0.0.1',
        'X-ClientPublicIP': '127.0.0.1',
        'X-MACAddress': '00:00:00:00:00:00',
        'X-PrivateKey': API_KEY
    }
    
    resp = requests.post(login_url, json=login_payload, headers=login_headers, timeout=30)
    login_data = resp.json()
    
    print(f"\nLogin Response: {json.dumps(login_data, indent=2)}")
    
    if not login_data.get('status'):
        print(f"\n❌ Login Failed: {login_data.get('message')}")
        return
    
    # Get JWT token
    jwt_token = login_data['data'].get('jwtToken', '')
    print(f"\n✅ Login Success!")
    print(f"JWT Token starts with: {jwt_token[:30]}...")
    
    # Step 2: Test API calls with this token
    # Token from AngelOne already has "Bearer " prefix
    auth_header = jwt_token if jwt_token.startswith('Bearer ') else f'Bearer {jwt_token}'
    
    api_headers = {
        'Authorization': auth_header,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-UserType': 'USER',
        'X-SourceID': 'WEB',
        'X-ClientLocalIP': '127.0.0.1',
        'X-ClientPublicIP': '127.0.0.1',
        'X-MACAddress': '00:00:00:00:00:00',
        'X-PrivateKey': API_KEY
    }
    
    # Test 1: RMS (Account Balance)
    print("\n" + "=" * 40)
    print("Test 1: Account Balance (RMS)")
    print("=" * 40)
    
    rms_url = "https://apiconnect.angelone.in/rest/secure/angelbroking/user/v1/getRMS"
    resp = requests.get(rms_url, headers=api_headers, timeout=30)
    rms_data = resp.json()
    print(f"RMS Response: {json.dumps(rms_data, indent=2)}")
    
    if rms_data.get('status') and rms_data.get('data'):
        net = rms_data['data'].get('net', 0)
        print(f"\n💰 Account Balance: ₹{net}")
    
    # Test 2: Historical Data
    print("\n" + "=" * 40)
    print("Test 2: Historical Data (RELIANCE)")
    print("=" * 40)
    
    from datetime import datetime, timedelta
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5)
    
    hist_url = "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleData"
    hist_payload = {
        "exchange": "NSE",
        "symboltoken": "2885",
        "interval": "FIVE_MINUTE",
        "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
        "todate": to_date.strftime("%Y-%m-%d %H:%M")
    }
    
    resp = requests.post(hist_url, json=hist_payload, headers=api_headers, timeout=30)
    hist_data = resp.json()
    
    if hist_data.get('status') and hist_data.get('data'):
        candles = hist_data['data']
        print(f"✅ Got {len(candles)} candles!")
        if candles:
            print(f"Latest candle: {candles[-1]}")
    else:
        print(f"❌ Historical Error: {hist_data.get('message')}")
        print(f"Full response: {json.dumps(hist_data, indent=2)}")
    
    # Test 3: LTP
    print("\n" + "=" * 40)
    print("Test 3: LTP (RELIANCE)")
    print("=" * 40)
    
    ltp_url = "https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote/"
    ltp_payload = {
        "mode": "LTP",
        "exchangeTokens": {"NSE": ["2885"]}
    }
    
    resp = requests.post(ltp_url, json=ltp_payload, headers=api_headers, timeout=30)
    ltp_data = resp.json()
    
    if ltp_data.get('status') and ltp_data.get('data'):
        fetched = ltp_data['data'].get('fetched', [])
        if fetched:
            price = fetched[0].get('ltp', 0)
            print(f"✅ RELIANCE LTP: ₹{price}")
    else:
        print(f"❌ LTP Error: {ltp_data.get('message')}")
    
    print("\n" + "=" * 50)
    print("✅ Test Complete!")
    print("=" * 50)
    
    # Return token for use in main app
    return jwt_token

if __name__ == "__main__":
    login_and_test()
