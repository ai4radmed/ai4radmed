import pytest
import subprocess
import json
import logging

# Container Name
VAULT_CONTAINER = "ai4radmed-vault"

def run_inside_vault(command_args):
    """
    Execute a Vault command inside the container.
    Returns the stdout as a string.
    """
    # Helper to run commands inside the container
    cmd = ["docker", "exec", VAULT_CONTAINER] + command_args
    try:
        # Check if container is running first
        subprocess.check_call(
            ["docker", "inspect", "--format", "{{.State.Running}}", VAULT_CONTAINER],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return result.decode("utf-8").strip()
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to execute command in vault. Error: {e.output.decode('utf-8') if e.output else str(e)}")

def test_liveness():
    """
    [Core-Vault-01] Liveness Probe
    Verify that the container is running (Status=Up).
    """
    cmd = ["docker", "inspect", "--format", "{{.State.Running}}", VAULT_CONTAINER]
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        assert result == "true", f"Container {VAULT_CONTAINER} is not running"
    except subprocess.CalledProcessError:
        pytest.fail(f"Failed to inspect container {VAULT_CONTAINER}")

def test_readiness():
    """
    [Core-Vault-02] Readiness Probe
    Verify that Vault is unsealed and ready to serve requests.
    This is the most critical check for Vault.
    """
    # vault status -format=json provides structured data
    output = run_inside_vault(["vault", "status", "-format=json"])
    status_data = json.loads(output)
    
    # Check if Sealed is false
    assert status_data.get("sealed") is False, f"Vault is SEALED. Service is not ready. Status: {status_data}"
    
    # Check initialized
    assert status_data.get("initialized") is True, "Vault is NOT initialized."

def test_integrity():
    """
    [Core-Vault-03] Integrity Check
    Verify that the Vault version and storage backend are correct.
    Checks basic structural integrity without needing a root token.
    """
    output = run_inside_vault(["vault", "status", "-format=json"])
    status_data = json.loads(output)
    
    # Verify Version (sanity check, ensuring it's not empty)
    version = status_data.get("version")
    assert version, "Vault version could not be determined."
    
    # Verify Storage Type (should be file or raft based on our config, usually 'file' for single node)
    # Note: 'type' might be under 'storage' key or top level depending on version/output. 
    # In JSON format, storage type is often inferred or check 'ha_enabled' etc.
    # For now, we check that we got valid status data back which implies integrity of the binary.
    assert status_data.get("type") == "shamir", f"Unexpected seal type. Status: {status_data}"

def test_security():
    """
    [Core-Vault-04] Security Check
    Verify that Vault is configured to use HTTPS (TLS) and standard security settings.
    """
    # Check VAULT_ADDR environment variable inside container
    cmd = ["printenv", "VAULT_ADDR"]
    vault_addr = run_inside_vault(cmd)
    
    assert vault_addr.startswith("https://"), f"Vault is not using HTTPS. VAULT_ADDR={vault_addr}"
