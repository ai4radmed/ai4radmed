import pytest
import subprocess
import json

def test_vault_status():
    """
    [SEC-05] Vault Status Check
    Verify Vault is reachable via Docker Exec (Internal) as Host Port is closed [SEC-08].
    """
    # Use docker exec to check status inside the container
    cmd = [
        "docker", "exec", "ai4radmed-vault",
        "vault", "status",
        "-address=https://127.0.0.1:8200",
        "-tls-skip-verify", # Internal check checks functionality, not cert validity from localhost
        "-format=json"
    ]
    
    try:
        # Check return code. 
        # 0 = Unsealed
        # 2 = Sealed
        # 1 = Error
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        stdout = result.stdout
        print(f"Vault Status Output: {stdout}")
        
        # If sealed, it returns exit code 2. If active, 0.
        if result.returncode == 0:
            print("Vault is Unsealed and Active.")
        elif result.returncode == 2:
            print("Vault is Sealed.")
        else:
             pytest.fail(f"Vault Error (Code {result.returncode}): {result.stderr}")
             
        # Parse JSON if possible
        try:
            status = json.loads(stdout)
            assert "sealed" in status
        except json.JSONDecodeError:
            pass
            
    except FileNotFoundError:
        pytest.fail("Docker command not found.")
    except Exception as e:
        pytest.fail(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_vault_status()
    print("SEC-05 Vault Verified [PASS]")
