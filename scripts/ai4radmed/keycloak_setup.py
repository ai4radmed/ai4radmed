#!/usr/bin/env python3
import os
import sys
import time
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
if PROJECT_ROOT not in sys.path:
    sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from common.logger import log_info, log_error, log_warn

# Configuration
KEYCLOAK_HOST = os.getenv("KC_HOSTNAME", "auth.ai4radmed.internal")
KEYCLOAK_PORT = os.getenv("KEYCLOAK_PORT", "8484")  # Host port
KEYCLOAK_URL = f"http://localhost:{KEYCLOAK_PORT}"  # Access via localhost for setup script
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")

REALM_NAME = "ai4radmed"
LDAP_HOST = "ai4radmed-ldap" # Internal docker name
LDAP_PORT = "389"

def get_admin_token():
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    payload = {
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASSWORD,
        "grant_type": "password"
    }
    try:
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        log_error(f"Failed to get admin token: {e}")
        sys.exit(1)

def create_realm(token):
    url = f"{KEYCLOAK_URL}/admin/realms"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Check if realm exists
    check_url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}"
    resp = requests.get(check_url, headers=headers)
    if resp.status_code == 200:
        log_info(f"Realm '{REALM_NAME}' already exists.")
        return

    payload = {
        "realm": REALM_NAME,
        "enabled": True,
        "displayName": "AI4RadMed Hospital"
    }
    
    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code == 201:
        log_info(f"Realm '{REALM_NAME}' created successfully.")
    else:
        log_error(f"Failed to create realm: {resp.text}")

def configure_ldap(token):
    # Get Realm UUID
    realm_url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(realm_url, headers=headers)
    if resp.status_code != 200:
        log_error(f"Failed to get realm info: {resp.text}")
        return
    realm_id = resp.json()["id"]

    # Check existing storage providers
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/components"
    params = {"parent": realm_id, "type": "org.keycloak.storage.UserStorageProvider"}
    
    resp = requests.get(url, headers=headers, params=params)
    existing = resp.json()
    for comp in existing:
        if comp["name"] == "openldap":
            log_info("LDAP provider found. Deleting to ensure configuration update (and fix parentId)...")
            comp_id = comp["id"]
            requests.delete(f"{url}/{comp_id}", headers=headers)
            break

    # Configure LDAP
    payload = {
        "name": "openldap",
        "providerId": "ldap",
        "providerType": "org.keycloak.storage.UserStorageProvider",
        "parentId": realm_id,
        "config": {
            "vendor": ["other"],
            "usernameLDAPAttribute": ["uid"],
            "rdnLDAPAttribute": ["uid"],
            "uuidLDAPAttribute": ["entryUUID"],
            "userObjectClasses": ["inetOrgPerson, organizationalPerson"],
            "connectionUrl": [f"ldap://{LDAP_HOST}:{LDAP_PORT}"],
            "usersDn": ["dc=ai4radmed,dc=internal"],
            "authType": ["simple"],
            "bindDn": ["cn=admin,dc=ai4radmed,dc=internal"],
            "bindCredential": [os.getenv("LDAP_ADMIN_PASSWORD", "admin")],
            "searchScope": ["2"], # Subtree
            "batchSizeForSync": ["1000"],
            "fullSyncPeriod": ["86400"], # 1 day
            "changedSyncPeriod": ["300"], # 5 min (changed from -1)
            "editMode": ["WRITABLE"], # Allow Keycloak to write to LDAP
            "syncRegistrations": ["true"],
            "importEnabled": ["true"]
        }
    }
    
    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code == 201:
        log_info(f"LDAP provider configured successfully (Parent ID: {realm_id}).")
    else:
        log_error(f"Failed to configure LDAP: {resp.text}")

def create_oidc_client(token, client_id, redirect_uris):
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/clients"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Check if client exists (list all and filter, Keycloak Client API is annoying)
    resp = requests.get(url, headers=headers, params={"clientId": client_id})
    clients = resp.json()
    if clients:
        log_info(f"Client '{client_id}' already exists. Deleting to ensure configuration update...")
        client_uuid = clients[0]["id"]
        del_resp = requests.delete(f"{url}/{client_uuid}", headers=headers)
        if del_resp.status_code == 204:
             log_info(f"Client '{client_id}' deleted successfully.")
        else:
             log_error(f"Failed to delete client '{client_id}': {del_resp.text}")
             return

    payload = {
        "clientId": client_id,
        "enabled": True,
        "clientAuthenticatorType": "client-secret",
        "secret": "orthanc-secret", # Fixed secret for simplicity in this demo environment
        "directAccessGrantsEnabled": True,
        "standardFlowEnabled": True, # Authorization Code Flow
        "publicClient": False, # [SEC-04] Confidential Client
        "serviceAccountsEnabled": True, # [SEC-04] Allow backend authentication
        "redirectUris": redirect_uris,
        "protocol": "openid-connect"
    }
    
    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code == 201:
        log_info(f"Client '{client_id}' created successfully.")
        
        # Add Mappers (uid -> preferred_username)
        # Re-fetch id
        resp = requests.get(url, headers=headers, params={"clientId": client_id})
        client_uuid = resp.json()[0]["id"]
        
        mapper_url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/clients/{client_uuid}/protocol-mappers/models"
        mapper_payload = {
            "name": "uid-mapper",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-property-mapper",
            "consentRequired": False,
            "config": {
                "user.attribute": "uid",
                "claim.name": "preferred_username",
                "jsonType.label": "String",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true"
            }
        }
        requests.post(mapper_url, json=mapper_payload, headers=headers)
        
    else:
        log_error(f"Failed to create client '{client_id}': {resp.text}")



def configure_mfa(token):
    """
    [SEC-03] MFA Enforcement
    1. Set OTP Policy to TOTP
    2. Enable CONFIGURE_TOTP required action
    3. Set CONFIGURE_TOTP as Default Action (Enforce for new users)
    """
    log_info("Configuring MFA (TOTP) Policy...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 1. Update Realm OTP Policy
    realm_url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}"
    payload = {
        "otpPolicyType": "totp",
        "otpPolicyAlgorithm": "HmacSHA1",
        "otpPolicyDigits": 6,
        "otpPolicyLookAheadWindow": 1,
        "otpPolicyPeriod": 30
    }
    requests.put(realm_url, json=payload, headers=headers)
    
    # 2. Enable Required Action: CONFIGURE_TOTP
    # First get alias/name
    actions_url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/authentication/required-actions"
    resp = requests.get(actions_url, headers=headers)
    actions = resp.json()
    
    totp_alias = "CONFIGURE_TOTP"
    totp_action = next((a for a in actions if a["alias"] == totp_alias), None)
    
    if totp_action:
        # Update to Enabled=True, DefaultAction=True
        totp_update_url = f"{actions_url}/{totp_alias}"
        update_payload = {
            "alias": totp_alias,
            "name": totp_action["name"],
            "providerId": totp_action["providerId"],
            "enabled": True,
            "defaultAction": True, # [SEC-03] Enforce for all new users
            "priority": totp_action["priority"]
        }
        resp = requests.put(totp_update_url, json=update_payload, headers=headers)
        if resp.status_code == 204:
             log_info("MFA (CONFIGURE_TOTP) set as Default Action successfully.")
        else:
             log_error(f"Failed to set MFA default action: {resp.text}")
    else:
        log_error("CONFIGURE_TOTP action not found in realm.")


def main():
    log_info("Waiting for Keycloak to be ready...")
    # Simple wait loop
    for _ in range(30):
        try:
            requests.get(KEYCLOAK_URL)
            break
        except requests.ConnectionError:
            time.sleep(2)
            print(".", end="", flush=True)
    print("")

    token = get_admin_token()
    create_realm(token)
    configure_ldap(token)
    configure_mfa(token) # [SEC-03]
    
    # PACS Client (Legacy)
    create_oidc_client(token, "orthanc", ["http://localhost:8042/*", "https://pacs.ai4radmed.internal/*"])

    # Nginx Gateway Client (OpenResty)
    # Redirect URI must match lua-resty-openidc default (/redirect_uri)
    gateway_redirects = [
        "http://localhost/redirect_uri",
        "https://ai4radmed.internal/redirect_uri",
        "https://vault.ai4radmed.internal/redirect_uri",
        "https://ldap-admin.ai4radmed.internal/redirect_uri",
        "https://pacs.ai4radmed.internal/redirect_uri",
        "https://pacs-mock.ai4radmed.internal/redirect_uri",
        "https://pacs-raw.ai4radmed.internal/redirect_uri",
        "https://pacs-pseudo.ai4radmed.internal/redirect_uri",
        "https://*.ai4radmed.internal/redirect_uri"
    ]
    create_oidc_client(token, "nginx-gateway", gateway_redirects)

    log_info("Keycloak automated setup complete.")

if __name__ == "__main__":
    main()
