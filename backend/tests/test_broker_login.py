import pytest
from unittest.mock import patch, MagicMock

def test_broker_login_flow(client):
    # 1. Register a user
    register_response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "password123", "full_name": "Test User"}
    )
    assert register_response.status_code == 200
    
    # 2. Login to get token
    login_response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Configure Angel One Credentials
    config_payload = {
        "api_key": "test_api_key",
        "client_code": "TESTCLIENT",
        "pin": "1234",
        "totp_secret": "JBSWY3DPEHPK3PXP" # Valid base32
    }
    config_response = client.post(
        "/brokers/angelone/configure",
        json=config_payload,
        headers=headers
    )
    assert config_response.status_code == 200
    
    # 4. Mock the Angel One Login Request
    with patch("broker.angelone.client.requests.post") as mock_post:
        # Mock successful login response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": True,
            "message": "SUCCESS",
            "data": {
                "jwtToken": "mock_jwt_token",
                "refreshToken": "mock_refresh_token",
                "feedToken": "mock_feed_token"
            },
            "errorcode": ""
        }
        mock_post.return_value = mock_response
        
        # 5. Perform Login
        # Note: We need to pass TOTP because the backend might require it or generate it.
        # The backend logic generates it if we don't pass it but have the secret.
        # Let's pass it explicitly to be sure, or let backend generate it.
        # Based on code: if not otp_to_use and creds.totp_secret: generate.
        
        login_response = client.post(
            "/brokers/angelone/login?client_code=TESTCLIENT",
            headers=headers
        )
        
        # Check if login was successful
        if login_response.status_code != 200:
            print(f"Login failed: {login_response.json()}")
            
        assert login_response.status_code == 200
        data = login_response.json()
        assert data["status"] == "success"
        assert data["data"]["jwtToken"] == "mock_jwt_token"
        
        # Verify the mock was called correctly
        mock_post.assert_called()
        args, kwargs = mock_post.call_args
        assert kwargs['json']['clientcode'] == "TESTCLIENT"
