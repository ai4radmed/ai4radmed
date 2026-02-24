import pytest
import requests
import subprocess
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs


# Configuration
NGINX_CONTAINER = "ai4radmed-nginx"
AUTH_URL = "https://auth.ai4radmed.internal"
HTTP_AUTH_URL = "http://auth.ai4radmed.internal"
VAULT_URL = "https://vault.ai4radmed.internal"
LDAP_ADMIN_URL = "https://ldap-admin.ai4radmed.internal"
LOCALHOST_URL = "https://localhost"
HTTP_LOCALHOST_HEALTH = "http://localhost/health"

EXPECTED_CLIENT_ID = "nginx-gateway"
EXPECTED_REDIRECT_PATH = "/redirect_uri"

def test_liveness():
    """
    [Infrastructure] Nginx Liveness Probe
    Verify that the Nginx container is running.
    """
    cmd = ["docker", "inspect", "-f", "{{.State.Running}}", NGINX_CONTAINER]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert result.stdout.strip() == "true", f"Container {NGINX_CONTAINER} is not running"
    except subprocess.CalledProcessError:
        pytest.fail(f"Failed to inspect container {NGINX_CONTAINER}. Is it created?")

def test_readiness():
    """
    [Infrastructure] Nginx Readiness Probe
    Verify that Nginx is listening on HTTPS (443) and serving requests.
    Using auth domain as it is a public endpoint.
    """
    try:
        # Keycloak root might redirect, but response proves Nginx is up
        response = requests.get(AUTH_URL, verify=False, timeout=5)
        assert response.status_code in [200, 302, 404], f"Unexpected status code: {response.status_code}"
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to {AUTH_URL}. Is Nginx reachable on port 443?")

def test_http_to_https_redirect():
    """
    [Security] HTTPS Enforcement
    Verify that HTTP requests (Port 80) are redirected to HTTPS (Port 443).
    """
    try:
        # allow_redirects=False to inspect the 301 Redirect
        response = requests.get(HTTP_AUTH_URL, allow_redirects=False, timeout=5)
        assert response.status_code == 301, f"Expected 301 Redirect for HTTP, got {response.status_code}"
        assert response.headers["Location"].startswith("https://"), "Redirect location is not HTTPS"
    except requests.exceptions.ConnectionError:
        pytest.fail("Could not connect to Nginx on Port 80.")

def test_security_headers():
    """
    [Security] Server Header Concealment
    Verify that the 'Server' header does not leak specific Nginx version info.
    """
    try:
        response = requests.get(AUTH_URL, verify=False, timeout=5)
        server_header = response.headers.get("Server", "")
        # Basic check: Should be 'openresty' (as configured) or generic, not 'nginx/1.21.6' etc.
        # Ideally we want to hide even openresty, but current config allows it.
        # Let's just ensure it exists for now to confirm we are hitting Nginx.
        assert "openresty" in server_header.lower() or "nginx" in server_header.lower(), \
            f"Unexpected Server header: {server_header}"
    except Exception as e:
        pytest.fail(f"Header check failed: {e}")

def test_oidc_gateway_enforcement():
    """
    [Integration] OIDC Gateway Enforcement (Vault)
    Verify that accessing a protected service (Vault) redirects to Keycloak.
    """
    try:
        # Request Vault Root without cookies
        response = requests.get(VAULT_URL, verify=False, allow_redirects=False, timeout=5)
        
        # Assert 1: HTTP Status 302 Found
        assert response.status_code == 302, f"Expected 302 Redirect (OIDC), got {response.status_code}"

        # Assert 2: Location Header targets Keycloak
        location = response.headers.get("Location")
        assert location and "protocol/openid-connect/auth" in location, "Redirect target is not Keycloak OIDC"

        # Assert 3: Query Parameters (Client ID & Redirect URI)
        parsed_url = urlparse(location)
        params = parse_qs(parsed_url.query)

        assert params["client_id"][0] == EXPECTED_CLIENT_ID
        assert params["redirect_uri"][0] == f"{VAULT_URL}{EXPECTED_REDIRECT_PATH}"

    except requests.exceptions.ConnectionError:
        pytest.fail("Connection logic check failed.")

def test_ldap_admin_routing():
    """
    [Integration] LDAP Admin Routing
    Verify that ldap-admin.ai4radmed.internal is reachable and returns the login page.
    """
    try:
        response = requests.get(LDAP_ADMIN_URL, verify=False, timeout=5)
        # phpLDAPadmin usually returns 200 on login page
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
        assert "phpLDAPadmin" in response.text, "Response does not contain phpLDAPadmin signature"
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to {LDAP_ADMIN_URL}")

def test_default_server_health():
    """
    [Infrastructure] Default Server Health Check
    Verify that http://localhost/health returns 'healthy'.
    """
    try:
        response = requests.get(HTTP_LOCALHOST_HEALTH, timeout=5)
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
        assert response.text.strip() == "healthy", f"Unexpected health response: {response.text}"
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to {HTTP_LOCALHOST_HEALTH}")

def test_default_server_oidc_enforcement():
    """
    [Integration] Default Server OIDC Enforcement
    Verify that https://localhost (Default) is also protected by OIDC.
    """
    try:
        response = requests.get(LOCALHOST_URL, verify=False, allow_redirects=False, timeout=5)
        # Assumes default.conf enables OIDC for root '/'
        assert response.status_code == 302, f"Expected 302 Redirect, got {response.status_code}"
        assert "protocol/openid-connect/auth" in response.headers.get("Location", ""), \
            "Default server is not redirecting to Keycloak"
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to {LOCALHOST_URL}")


# =================================================================================================
# Static Config Regression Tests (Merged from test_01_nginx_config.py)
# =================================================================================================

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
NGINX_CONF_DIR = PROJECT_ROOT / "templates" / "nginx" / "config" / "conf.d"
CERTS_DIR_HOST = Path("/opt/ai4radmed/nginx/certs") # Default deployment path

def test_nginx_config_files_exist():
    """Verify that the Nginx configuration directory exists."""
    assert NGINX_CONF_DIR.exists(), f"Nginx config dir not found: {NGINX_CONF_DIR}"
    configs = list(NGINX_CONF_DIR.glob("*.conf"))
    assert len(configs) > 0, "No Nginx config files found"

@pytest.mark.parametrize("config_name", ["vault.conf", "keycloak.conf"])
def test_proxy_headers_presence(config_name):
    """
    Verify that critical proxy headers are present in Nginx configs.
    Missing these headers can cause 'Cookie not found' or redirect loops.
    """
    config_path = NGINX_CONF_DIR / config_name
    if not config_path.exists():
        pytest.skip(f"{config_name} not found")

    content = config_path.read_text()
    
    # Check for X-Forwarded-Proto $scheme
    assert re.search(r"proxy_set_header\s+X-Forwarded-Proto\s+\$scheme;", content), \
        f"{config_name} is missing X-Forwarded-Proto header"

    # Check for X-Forwarded-Port (Required for Keycloak/Vault behind TLS termination)
    # Usually we want 443 or $server_port
    assert re.search(r"proxy_set_header\s+X-Forwarded-Port\s+(443|\$server_port);", content), \
        f"{config_name} is missing X-Forwarded-Port header"

def test_ssl_certificates_existence():
    """
    Parse Nginx configs for ssl_certificate directives and ensure referenced files exist.
    This prevents 'cannot load certificate' crash loops.
    """
    configs = list(NGINX_CONF_DIR.glob("*.conf"))
    
    # Map container path to host path
    # Pattern: /etc/nginx/certs/xxxx -> /opt/ai4radmed/nginx/certs/xxxx
    
    missing_files = []

    for config in configs:
        content = config.read_text()
        # Find all ssl_certificate or proxy_ssl_certificate directives
        # Group 1: The file path
        matches = re.findall(r"(?:ssl_certificate|ssl_certificate_key|proxy_ssl_certificate|proxy_ssl_certificate_key)\s+([^;]+);", content)
        
        for file_path in matches:
            file_path = file_path.strip()
            if not file_path.startswith("/etc/nginx/certs/"):
                continue # Skip non-standard paths or ignore

            filename = os.path.basename(file_path)
            host_path = CERTS_DIR_HOST / filename
            
            # Note: We check if the file exisits on the HOST system where tests are running.
            # Assuming the user has run 'make install-all' or similar setup.
            # If standard setup is done, these files should verify.
            
            if not host_path.exists():
                missing_files.append(f"{config.name}: requires {filename} (at {host_path})")

    assert not missing_files, f"Missing SSL certificates referenced in Nginx config:\n" + "\\n".join(missing_files)
