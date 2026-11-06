"""Unit and integration tests for SparkDesk Local Agent FastAPI server."""

import os
import platform
import time
from fastapi.testclient import TestClient

from sparkdesk_agent.core.config import AgentSettings
from sparkdesk_agent.ipc.server import create_app


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


def test_lifespan_startup_and_shutdown() -> None:
    """Verify that lifespan startup and shutdown context executes cleanly without errors."""
    settings = AgentSettings()
    app = create_app(settings)

    # Entering and exiting TestClient triggers startup and shutdown lifespan events
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
