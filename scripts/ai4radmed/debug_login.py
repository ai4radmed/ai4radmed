#!/usr/bin/env python3
import os
import sys
import requests
import subprocess
import base64

# Configuration
LDAP_HOST = "localhost"
LDAP_PORT = "389"
KEYCLOAK_URL = "http://localhost:8484"
REALM = "ai4radmed"
USER_DN = "uid=ben,ou=users,ou=ai4rm,dc=ai4radmed,dc=internal"
PASSWORD = "ben"
CLIENT_ID = "nginx-gateway"
CLIENT_SECRET = "orthanc-secret"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def check_ldap_bind():
    log("Testing Direct LDAP Bind...")
    try:
        # Use ldapwhoami or ldapsearch with bind credentials
        # We assume ldap-utils is installed or we use python-ldap? 
        # Better to use docker exec to run ldapwhoami inside the container or just use subprocess if available
        # But we can verify via simple ldapsearch command too.
        
        cmd = [
            "docker", "exec", "ai4radmed-ldap", 
            "ldapwhoami", 
            "-x", 
            "-H", "ldap://localhost", 
            "-D", USER_DN, 
            "-w", PASSWORD
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log("LDAP Bind SUCCESS", "PASS")
            return True
        else:
            log(f"LDAP Bind FAILED: {result.stderr}", "FAIL")
            return False
    except Exception as e:
        log(f"LDAP Check Exception: {e}", "FAIL")
        return False

def get_admin_token():
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    payload = {
        "client_id": "admin-cli",
        "username": "admin",
        "password": "admin",
        "grant_type": "password"
    }
    try:
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        log(f"Failed to get admin token: {e}", "FAIL")
        return None

def check_keycloak_user_sync():
    log("Testing Keycloak User Sync...")
    token = get_admin_token()
    if not token: return False
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users"
    try:
        # Search for ben
        resp = requests.get(url, headers=headers, params={"username": "ben"})
        users = resp.json()
        if users:
            log(f"Keycloak found user: {users[0]['username']} (ID: {users[0]['id']})", "PASS")
            return True
        else:
            log("Keycloak could NOT find user 'ben'. Sync failed?", "FAIL")
            # Trigger sync manually?
            return False
    except Exception as e:
        log(f"Keycloak Sync Check Exception: {e}", "FAIL")
        return False

def check_keycloak_auth():
    log("Testing Keycloak Direct Login (Direct Grant)...")
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": "ben",
        "password": PASSWORD,
        "grant_type": "password"
    }
    try:
        resp = requests.post(url, data=payload)
        if resp.status_code == 200:
            log("Keycloak Login SUCCESS", "PASS")
            return True
        else:
            log(f"Keycloak Login FAILED: {resp.status_code} {resp.text}", "FAIL")
            return False
    except Exception as e:
        log(f"Keycloak Auth Exception: {e}", "FAIL")
        return False

def run_diagnostics():
    print("=== STARTING DIAGNOSTICS ===")
    
    ldap_ok = check_ldap_bind()
    print("-" * 30)
    
    kc_sync_ok = check_keycloak_user_sync()
    print("-" * 30)
    
    kc_auth_ok = check_keycloak_auth()
    print("-" * 30)
    
    if ldap_ok and kc_sync_ok and kc_auth_ok:
        print("=== ALL TESTS PASSED ===")
        print("The backend is 100% working. If browser login fails, it's likely a browser/cookie/redirect issue.")
    else:
        print("=== DIAGNOSTIC FAILED ===")
        if not ldap_ok: print("-> LDAP Password/User is wrong.")
        if ldap_ok and not kc_sync_ok: print("-> Keycloak hasn't synced the user yet.")
        if kc_sync_ok and not kc_auth_ok: print("-> Keycloak has the user but password mismatch or client config issue.")

if __name__ == "__main__":
    run_diagnostics()
