import pytest
import subprocess
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Use the CLI which implements the correct Unseal logic (via Docker Exec)
SCRIPT_PATH = os.path.join(PROJECT_ROOT, "scripts/ai4radmed/ai4radmed-cli.py")
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv/bin/python")

def test_auto_unseal_script_execution():
    """
    [SEC-06] Auto Unseal Execution via CLI
    Verify the 'unseal-vault' command works.
    """
    # Environment Setup for Test
    env = os.environ.copy()
    env["USB_MOUNT_PATH"] = os.path.join(PROJECT_ROOT, "mock_usb") # Point to local mock usb
    
    # We call "ai4radmed-cli.py unseal-vault"
    # This uses docker exec internally, so it bypasses Host port issues.

    try:
        result = subprocess.run(
            [VENV_PYTHON, SCRIPT_PATH, "unseal-vault"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30 # Give enough time for docker exec calls
        )
        
        stdout = result.stdout
        print("CLI Output:", stdout)
        
        # Success if it says "자동 언실 성공" or "이미 언실되어 있습니다"
        success_markers = ["자동 언실 성공", "이미 언실되어 있습니다", "Active"]
        assert any(marker in stdout for marker in success_markers), "Unseal command did not report success."
        
        assert result.returncode == 0, "CLI exited with error code"

    except subprocess.TimeoutExpired:
        pytest.fail("Unseal command timed out.")
    except Exception as e:
        pytest.fail(f"Execution failed: {e}")

if __name__ == "__main__":
    test_auto_unseal_script_execution()
    print("SEC-06 Auto-Unseal Verified [PASS]")
