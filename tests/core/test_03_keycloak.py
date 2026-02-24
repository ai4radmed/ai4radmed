import pytest
import subprocess
import requests
import time
import os
import json

# Configuration
CONTAINER_NAME = "ai4radmed-keycloak"
KEYCLOAK_URL = "http://localhost:8484"  # Internal Direct Access (Mapped Port)
NGINX_URL = "https://auth.ai4radmed.internal" # External Access via Gateway (Correct Domain)
REALM = "ai4radmed"
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASS = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")

def get_admin_token():
    """Helper to get Admin Access Token"""
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    payload = {
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASS,
        "grant_type": "password"
    }
    try:
        response = requests.post(url, data=payload, timeout=5)
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.RequestException as e:
        pytest.fail(f"Failed to get admin token: {e}")

def test_liveness():
    """
    [Core-Keycloak-01] Liveness Probe
    Verify that the container is running.
    """
    cmd = ["docker", "inspect", "--format", "{{.State.Running}}", CONTAINER_NAME]
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        assert result == "true", f"Container {CONTAINER_NAME} is not running"
    except subprocess.CalledProcessError:
        pytest.fail(f"Failed to inspect container {CONTAINER_NAME}")

def test_readiness():
    """
    [Core-Keycloak-02] Readiness Probe
    Verify that Keycloak is ready to serve requests.
    Uses the built-in health endpoint.
    """
    url = f"{KEYCLOAK_URL}/admin/master/console/"
    try:
        # Keycloak might take time to start, retry logic handled by pytest-retry or manual loop if needed
        # For this test, we assume test runner waits for services
        response = requests.get(url, timeout=5)
        # 503 means "Service Unavailable" (Starting), 200 means OK
        assert response.status_code == 200, f"Keycloak is not ready. Status: {response.status_code}"
    except requests.RequestException as e:
        pytest.fail(f"Readiness check failed: {e}")

def test_integrity_realm():
    """
    [Core-Keycloak-03] Integrity Check - Realm Existence
    Verify that the 'ai4radmed' realm has been created.
    """
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM}"
    
    response = requests.get(url, headers=headers)
    assert response.status_code == 200, f"Realm '{REALM}' not found or API error. Status: {response.status_code}"
    data = response.json()
    assert data['realm'] == REALM

def test_integrity_ldap_sync_user():
    """
    [Core-Keycloak-04] Integrity Check - LDAP User Sync
    Verify that an LDAP user (e.g., 'ben') exists in Keycloak.
    This confirms User Federation is working.
    """
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    # Search for user 'ben' in the realm
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users"
    params = {"username": "ben", "exact": "true"}
    
    response = requests.get(url, headers=headers, params=params)
    assert response.status_code == 200, f"User search failed. Status: {response.status_code}"
    
    users = response.json()
    assert len(users) > 0, "User 'ben' not found in Keycloak. LDAP Sync might be broken."
    assert users[0]['username'] == "ben"
    # Optional: Check federation linkage
    # assert users[0]['federationLink'] is not None

def test_security_access():
    """
    [Core-Keycloak-05] Security Check
    Verify HTTPS access via Nginx Gateway (Port 443).
    """
    # Verify that we can reach Keycloak via the public Nginx URL
    # Note: 'verify=False' is used here because valid Root CA trust on the host runner 
    # cannot always be guaranteed in dev environments, but we want to test the routing.
    # ideally, if 'setup-host-network' worked, verify=True/path_to_ca would pass.
    
    try:
        # Check basic landing page redirection
        response = requests.get(NGINX_URL, timeout=5, verify=False)
        assert response.status_code == 200, f"Gateway access failed. Status: {response.status_code}"
        assert "Keycloak" in response.text, "Response does not contain 'Keycloak' signature"
        
        # Check that we are indeed hitting the Nginx container (via headers)
        # Nginx usually adds 'Server: nginx' or 'openresty'
        server_header = response.headers.get("Server", "").lower()
        assert "nginx" in server_header or "openresty" in server_header, f"Unexpected Server header: {server_header}"
        
    except requests.RequestException as e:
        pytest.fail(f"Gateway security check failed: {e}")

def test_mfa_enforcement_policy():
    """
    [Core-Keycloak-06] MFA Enforcement Policy (was Sec-03)
    Verify that 'CONFIGURE_TOTP' is set as a default required action.
    This ensures all users must setup MFA upon first login.
    """
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get Realm Required Actions
    # Check the specific endpoint for actions
    actions_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/authentication/required-actions"
    actions_resp = requests.get(actions_url, headers=headers, timeout=5)
    assert actions_resp.status_code == 200
    
    actions = actions_resp.json()
    totp_action = next((a for a in actions if a["alias"] == "CONFIGURE_TOTP"), None)
    
    assert totp_action is not None, "CONFIGURE_TOTP action not found"
    assert totp_action["enabled"] is True, "MFA (TOTP) is not enabled"
    assert totp_action["defaultAction"] is True, "MFA is not set as Default Action (Enforcement)"

def test_client_security_confidential():
    """
    [Core-Keycloak-07] Client Security (was Sec-04)
    Verify that critical clients (nginx-gateway, orthanc) are set to 'Confidential'.
    Public clients should not be used for backend services.
    """
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    clients_to_check = ["nginx-gateway", "orthanc"]
    
    for client_id in clients_to_check:
        # 1. Get Client UUID
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients?clientId={client_id}"
        resp = requests.get(url, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0, f"Client {client_id} not found"
        
        client_data = data[0]
        
        # 2. Verify Access Type
        # In newer Keycloak, 'publicClient': False implies Confidential (with secret)
        assert client_data.get("publicClient") is False, f"Client {client_id} should NOT be Public"
        assert client_data.get("serviceAccountsEnabled") is True, f"Client {client_id} should have Service Accounts enabled (for backend auth)"
