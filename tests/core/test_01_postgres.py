import pytest
import subprocess
import shlex
import sys

# Container Name
POSTGRES_CONTAINER = "ai4radmed-postgres"

def run_inside_postgres(query):
    """
    Execute a SQL query inside the postgres container using docker exec.
    Returns the stdout as a string.
    """
    cmd = [
        "docker", "exec", POSTGRES_CONTAINER,
        "psql", "-U", "postgres", "-t", "-c", query
    ]
    try:
        # Check if container is running first
        subprocess.check_call(
            ["docker", "inspect", "--format", "{{.State.Running}}", POSTGRES_CONTAINER],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
            
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return result.decode("utf-8").strip()
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to execute query or container not running. Error: {e.output.decode('utf-8') if e.output else str(e)}")
def test_liveness():
    """
    [Core-01-A] Liveness Probe
    Verify that the container is running (Status=Up).
    """
    cmd = ["docker", "inspect", "--format", "{{.State.Running}}", POSTGRES_CONTAINER]
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        assert result == "true", f"Container {POSTGRES_CONTAINER} is not running"
    except subprocess.CalledProcessError:
        pytest.fail(f"Failed to inspect container {POSTGRES_CONTAINER}")

def test_readiness():
    """
    [Core-01-B] Readiness Probe
    Verify that the database is ready to accept connections (SELECT 1).
    """
    result = run_inside_postgres("SELECT 1")
    assert "1" in result, "Failed to connect to Postgres and execute SELECT 1"

def test_databases_required():
    """
    [Core-02] Required Databases Check
    Verify that the essential databases for other services exist.

    [Maintenance Note]
    The list of required databases (required_dbs) is HARDCODED based on project conventions.
    If new services are added or database names change in .env, this list MUST be updated manually.
    """
    # Query to get all database names
    result = run_inside_postgres("SELECT datname FROM pg_database")
    
    required_dbs = ["ai4radmed", "keycloak", "orthanc"]
    existing_dbs = [line.strip() for line in result.split("\n") if line.strip()]
    
    for db in required_dbs:
        assert db in existing_dbs, f"Required database '{db}' does not exist in Postgres"

def test_roles_required():
    """
    [Core-03] Required Roles Check
    Verify that the service users/roles exist.

    [Maintenance Note]
    The list of required roles (required_roles) is HARDCODED based on project conventions.
    If new services are added or user names change in .env, this list MUST be updated manually.
    """
    # Query to get all role names
    result = run_inside_postgres("SELECT rolname FROM pg_roles")
    
    required_roles = ["keycloak", "orthanc", "postgres"]
    existing_roles = [line.strip() for line in result.split("\n") if line.strip()]
    
    for role in required_roles:
        assert role in existing_roles, f"Required role '{role}' does not exist in Postgres"

def test_tls_config():
    """
    [Core-05] TLS Security Check
    Verify that TLS encryption is enabled (ssl=on).
    This ensures that the 2-step initialization (Plain -> TLS) has completed successfully.
    """
    result = run_inside_postgres("SHOW ssl")
    assert "on" in result.lower(), f"TLS is NOT enabled. Got: {result}"

if __name__ == "__main__":
    # If run directly, run pytest on this file
    sys.exit(pytest.main(["-v", __file__]))
