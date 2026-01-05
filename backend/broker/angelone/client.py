import requests
import json
import socket
import logging

class AngelOneClient:
    BASE_URL = "https://apiconnect.angelbroking.com"

    def __init__(self, api_key):
        self.api_key = api_key
        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None
        self.client_code = None
        
        # Get local IP for requests
        hostname = socket.gethostname()
        self.local_ip = socket.gethostbyname(hostname)

    def _get_headers(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": self.local_ip,
            "X-ClientPublicIP": self.local_ip,
            "X-MACAddress": "MAC_ADDRESS",
            "X-PrivateKey": self.api_key
        }
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers

    def login(self, client_code, pin, totp):
        """
        Login using Client Code, PIN and TOTP
        """
        url = f"{self.BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword"
        
        payload = {
            "clientcode": client_code,
            "password": pin,
            "totp": totp
        }
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data['status']:
                tokens = data['data']
                self.jwt_token = tokens['jwtToken']
                self.refresh_token = tokens['refreshToken']
                self.feed_token = tokens['feedToken']
                self.client_code = client_code
                return {"status": True, "message": "Login Successful", "data": data['data']}
            else:
                return {"status": False, "message": data['message'], "error_code": data['errorcode']}
                
        except Exception as e:
            return {"status": False, "message": str(e)}

    def get_profile(self):
        """Fetch User Profile"""
        if not self.jwt_token:
            return {"status": False, "message": "Not Logged In"}
            
        url = f"{self.BASE_URL}/rest/secure/angelbroking/user/v1/getProfile"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            data = response.json()
            return data
        except Exception as e:
            return {"status": False, "message": str(e)}

    def place_order(self, order_params):
        """Place an order"""
        if not self.jwt_token:
            return {"status": False, "message": "Not Logged In"}
            
        url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/placeOrder"
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=order_params)
            data = response.json()
            return data
        except Exception as e:
            return {"status": False, "message": str(e)}

    def get_holdings(self):
        """Fetch User Holdings"""
        if not self.jwt_token:
            return {"status": False, "message": "Not Logged In"}
        url = f"{self.BASE_URL}/rest/secure/angelbroking/portfolio/v1/getHolding"
        try:
            response = requests.get(url, headers=self._get_headers())
            return response.json()
        except Exception as e:
            return {"status": False, "message": str(e)}

    def get_positions(self):
        """Fetch User Positions"""
        if not self.jwt_token:
            return {"status": False, "message": "Not Logged In"}
        url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/getPosition"
        try:
            response = requests.get(url, headers=self._get_headers())
            return response.json()
        except Exception as e:
            return {"status": False, "message": str(e)}

    def get_order_book(self):
        """Fetch Order Book"""
        if not self.jwt_token:
            return {"status": False, "message": "Not Logged In"}
        url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/getOrderBook"
        try:
            response = requests.get(url, headers=self._get_headers())
            return response.json()
        except Exception as e:
            return {"status": False, "message": str(e)}

    def get_ltp(self, exchange, tradingsymbol, symboltoken):
        """Get Last Traded Price"""
        if not self.jwt_token:
            return {"status": False, "message": "Not Logged In"}
        url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/getLtpData"
        payload = {
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "symboltoken": symboltoken
        }
        try:
            response = requests.post(url, headers=self._get_headers(), json=payload)
            return response.json()
        except Exception as e:
            return {"status": False, "message": str(e)}

    def getCandleData(self, historic_params):
        """Get Historical Date (Candle Data)"""
        if not self.jwt_token:
            return {"status": False, "message": "Not Logged In"}
        
        url = f"{self.BASE_URL}/rest/secure/angelbroking/historical/v1/getCandleData"
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=historic_params)
            return response.json()
        except Exception as e:
            return {"status": False, "message": str(e)}

