"""Unit and integration tests for SparkDesk Local Agent FastAPI server."""

import os
import platform
import subprocess
import sys
from pathlib import Path
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from sparkdesk_agent.core.config import AgentSettings
from sparkdesk_agent.ipc.server import create_app, start_server


def test_health_endpoint() -> None:
    """Verify that GET /health returns valid JSON with all required fields."""
    settings = AgentSettings(
        agent_name="Test SparkDesk Agent",
        agent_version="0.1.0",
        host="127.0.0.1",
        port=8765,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["agent_name"] == "Test SparkDesk Agent"
        assert data["version"] == "0.1.0"
        assert data["python_version"] == platform.python_version()
        assert data["pid"] == os.getpid()
        assert isinstance(data["uptime_seconds"], (int, float))
        assert "timestamp" in data
        assert data["environment"] == "development"


def test_root_probe_endpoint() -> None:
    """Verify that GET / returns service probe metadata."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["health_endpoint"] == "/health"


def test_shutdown_endpoint_contract() -> None:
    """Verify that POST /shutdown responds with 200 and expected contract."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post("/shutdown")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shutting_down"


def test_lifespan_startup_and_shutdown() -> None:
    """Verify that lifespan startup and shutdown context executes cleanly without errors."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200


# =========================================================================
# Security & Loopback Binding Hardening Tests
# =========================================================================

def test_accept_valid_loopback_hosts() -> None:
    """Verify that 127.0.0.1 and localhost are accepted."""
    s1 = AgentSettings(host="127.0.0.1")
    assert s1.host == "127.0.0.1"

    s2 = AgentSettings(host="localhost")
    assert s2.host == "localhost"

    s3 = AgentSettings(host="  127.0.0.1  ")
    assert s3.host == "127.0.0.1"


@pytest.mark.parametrize(
    "invalid_host",
    [
        "0.0.0.0",
        "192.168.1.1",
        "10.0.0.1",
        "8.8.8.8",
        "example.com",
        "external-domain.org",
        "",
    ],
)
def test_reject_non_loopback_hosts_in_settings(invalid_host: str) -> None:
    """Verify that non-loopback host values raise ValidationError at configuration creation."""
    with pytest.raises((ValidationError, ValueError)) as excinfo:
        AgentSettings(host=invalid_host)
    assert "Security violation" in str(excinfo.value) or "loopback" in str(excinfo.value)


def test_start_server_rejects_non_loopback() -> None:
    """Verify that start_server enforces loopback validation even if settings object is modified."""
    settings = AgentSettings()
    # Bypass pydantic validation by assigning directly to __dict__
    settings.__dict__["host"] = "0.0.0.0"

    with pytest.raises(ValueError, match="Security violation"):
        start_server(settings)


def test_cli_rejects_non_loopback_host() -> None:
    """Verify that the CLI rejects non-loopback host arguments and exits with non-zero code."""
    agent_dir = Path(__file__).resolve().parents[1]
    run_agent = str(agent_dir / "run_agent.py")

    result = subprocess.run(
        [sys.executable, run_agent, "--host", "0.0.0.0"],
        cwd=str(agent_dir),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Security violation" in result.stderr or "loopback" in result.stderr
