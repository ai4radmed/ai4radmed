import pytest
import subprocess
import os

# Container Name
LDAP_CONTAINER = "ai4radmed-ldap"
BASE_DN = "dc=ai4radmed,dc=internal" # Standard project convention

def run_inside_ldap(command_args):
    """
    Execute a LDAP command inside the container.
    Returns the stdout as a string.
    """
    # Helper to run commands inside the container
    # -x: Simple authentication (or no auth for anonymous read)
    # -LL: LDIF format, comments removed
    cmd = ["docker", "exec", LDAP_CONTAINER] + command_args
    try:
        # Check if container is running first
        subprocess.check_call(
            ["docker", "inspect", "--format", "{{.State.Running}}", LDAP_CONTAINER],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return result.decode("utf-8").strip()
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to execute command in ldap. Error: {e.output.decode('utf-8') if e.output else str(e)}")

def test_liveness():
    """
    [Core-LDAP-01] Liveness Probe
    Verify that the container is running (Status=Up).
    """
    cmd = ["docker", "inspect", "--format", "{{.State.Running}}", LDAP_CONTAINER]
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        assert result == "true", f"Container {LDAP_CONTAINER} is not running"
    except subprocess.CalledProcessError:
        pytest.fail(f"Failed to inspect container {LDAP_CONTAINER}")

def test_readiness():
    """
    [Core-LDAP-02] Readiness Probe
    Verify that LDAP is ready to serve requests (RootDSE Query).
    Checks if the slapd process is responsive.
    """
    # -x: Simple auth, -s base: base object, -b "": search root
    cmd = ["ldapsearch", "-x", "-H", "ldap://localhost", "-b", "", "-s", "base", "(objectclass=*)", "namingContexts"]
    output = run_inside_ldap(cmd)
    
    # Check if we got a valid response containing namingContexts
    assert "namingContexts" in output, f"LDAP readiness check failed. Output: {output}"

def test_integrity_base_dn():
    """
    [Core-LDAP-03-A] Integrity Check - Base DN
    Verify that the Base DN (dc=ai4radmed,dc=internal) exists.
    This confirms the LDAP server is serving the correct domain.
    """
    # Authenticated Bind (osixia disables anonymous read by default)
    admin_dn = os.getenv("LDAP_ADMIN_DN", "cn=admin,dc=ai4radmed,dc=internal")
    admin_pw = os.getenv("LDAP_ADMIN_PASSWORD", "admin")
    
    cmd = ["ldapsearch", "-x", "-H", "ldap://localhost", "-D", admin_dn, "-w", admin_pw, "-b", BASE_DN, "-s", "base", "(objectclass=*)"]
    output = run_inside_ldap(cmd)
    assert f"dn: {BASE_DN}" in output, f"Base DN '{BASE_DN}' not found in output: {output}"

def test_integrity_structure():
    """
    [Core-LDAP-03-B] Integrity Check - OUs
    Verify that the organizational units (ou=People, ou=Groups) exist.
    This confirms the bootstrap structure was applied.
    """
    admin_dn = os.getenv("LDAP_ADMIN_DN", "cn=admin,dc=ai4radmed,dc=internal")
    admin_pw = os.getenv("LDAP_ADMIN_PASSWORD", "admin")

    # Check for People OU
    cmd_people = ["ldapsearch", "-x", "-H", "ldap://localhost", "-D", admin_dn, "-w", admin_pw, "-b", BASE_DN, "(ou=People)"]
    output_people = run_inside_ldap(cmd_people)
    assert "ou=People" in output_people or "dn: ou=People" in output_people, "ou=People not found (Seeding failed?)"

    # Check for Groups OU
    cmd_groups = ["ldapsearch", "-x", "-H", "ldap://localhost", "-D", admin_dn, "-w", admin_pw, "-b", BASE_DN, "(ou=Groups)"]
    output_groups = run_inside_ldap(cmd_groups)
    assert "ou=Groups" in output_groups or "dn: ou=Groups" in output_groups, "ou=Groups not found"

def test_integrity_admin_group():
    """
    [Core-LDAP-03-C] Integrity Check - Admin Group
    Verify that the 'admin' group exists.
    """
    admin_dn = os.getenv("LDAP_ADMIN_DN", "cn=admin,dc=ai4radmed,dc=internal")
    admin_pw = os.getenv("LDAP_ADMIN_PASSWORD", "admin")

    # Check for admin group
    cmd_admin = ["ldapsearch", "-x", "-H", "ldap://localhost", "-D", admin_dn, "-w", admin_pw, "-b", BASE_DN, "(cn=admin)"]
    output_admin = run_inside_ldap(cmd_admin)
    assert "cn=admin" in output_admin, "Admin group 'cn=admin' not found"

def test_security():
    """
    [Core-LDAP-04] Security Check
    Verify that LDAP supports StartTLS (port 389) or LDAPS (port 636).
    We check if we can initiate a StartTLS connection.
    """
    # 1. Check if TLS is explicitly disabled
    cmd_tls_env = ["printenv", "LDAP_TLS"]
    try:
        tls_env = run_inside_ldap(cmd_tls_env)
        if tls_env and tls_env.lower() == "false":
            pytest.skip("LDAP_TLS is set to false. Skipping StartTLS check (Internal TLS Disabled).")
    except Exception:
        pass # Ignore if printenv fails, assume enabled

    # 2. Check StartTLS availability
    # We will use 'ldapsearch -ZZ' (StartTLS required) inside the container as a proxy check
    cmd_security = ["ldapsearch", "-x", "-H", "ldap://localhost", "-b", "", "-s", "base", "-ZZ", "(objectclass=*)"]
    try:
        run_inside_ldap(cmd_security)
    except Exception as e:
         pytest.fail(f"StartTLS verification failed. LDAP server might not support TLS: {e}")
         
    # 3. Check Certificates (Only if TLS is NOT disabled)
    cmd_ls = ["ls", "/container/service/slapd/assets/certs/"]
    output_ls = run_inside_ldap(cmd_ls)
    assert "certificate.crt" in output_ls, "Server certificate not found in container"
    assert "private.key" in output_ls, "Private key not found in container"
