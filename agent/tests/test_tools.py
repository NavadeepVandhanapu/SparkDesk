"""Unit and integration tests for SparkDesk Local Agent Tool Registry and execution."""

import os
import pytest
from pydantic import BaseModel, Field
from fastapi.testclient import TestClient

from sparkdesk_agent.core.config import AgentSettings
from sparkdesk_agent.ipc.auth import TOKEN_HEADER_NAME, get_active_token
from sparkdesk_agent.ipc.server import create_app
from sparkdesk_agent.tools.registry import (
    ToolNotFoundError,
    ToolValidationError,
    registry,
)
from sparkdesk_agent.tools.system_info import get_system_info


def test_system_info_tool_structure() -> None:
    """Verify that get_system_info collects all required operating metrics."""
    data = get_system_info()

    # 1. OS Info
    assert "os" in data
    assert data["os"]["system"] == "Windows" or os.name == "nt"
    assert "version" in data["os"]
    assert "platform" in data["os"]

    # 2. CPU Info
    assert "cpu" in data
    assert "processor" in data["cpu"]
    assert data["cpu"]["logical_cores"] >= 1
    assert isinstance(data["cpu"]["usage_percent"], (int, float))

    # 3. RAM Info
    assert "memory" in data
    assert data["memory"]["total_gb"] > 0
    assert data["memory"]["available_gb"] >= 0
    assert isinstance(data["memory"]["usage_percent"], (int, float))

    # 4. Disk Info
    assert "disk" in data
    assert data["disk"]["total_gb"] > 0
    assert data["disk"]["free_gb"] >= 0
    assert "drive" in data["disk"]

    # 5. Uptime Info
    assert "uptime" in data
    assert data["uptime"]["uptime_seconds"] > 0
    assert isinstance(data["uptime"]["uptime_formatted"], str)
    assert "boot_time" in data["uptime"]


def test_authenticated_execute_endpoint_success() -> None:
    """Verify that POST /ipc/execute with valid authentication executes get_system_info."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        token = get_active_token()
        assert token is not None

        response = client.post(
            "/ipc/execute",
            headers={TOKEN_HEADER_NAME: token},
            json={"tool": "get_system_info", "parameters": {}},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["tool"] == "get_system_info"
        assert payload["result"] is not None
        assert "memory" in payload["result"]
        assert "cpu" in payload["result"]


def test_execute_endpoint_missing_and_invalid_auth() -> None:
    """Verify that POST /ipc/execute rejects missing and invalid authentication tokens."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        # 1. Missing token
        res_no_auth = client.post(
            "/ipc/execute",
            json={"tool": "get_system_info", "parameters": {}},
        )
        assert res_no_auth.status_code == 401

        # 2. Invalid token
        res_bad_auth = client.post(
            "/ipc/execute",
            headers={TOKEN_HEADER_NAME: "wrong_token_123"},
            json={"tool": "get_system_info", "parameters": {}},
        )
        assert res_bad_auth.status_code == 401


def test_execute_endpoint_unknown_tool_rejection() -> None:
    """Verify that invoking an unlisted/arbitrary tool returns 404."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        token = get_active_token()
        assert token is not None

        response = client.post(
            "/ipc/execute",
            headers={TOKEN_HEADER_NAME: token},
            json={"tool": "arbitrary_shell_cmd", "parameters": {}},
        )
        assert response.status_code == 404
        assert "Unknown tool" in response.json()["detail"]


def test_execute_endpoint_invalid_parameters_rejection() -> None:
    """Verify that passing unexpected parameters to a parameterless tool returns 422."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        token = get_active_token()
        assert token is not None

        response = client.post(
            "/ipc/execute",
            headers={TOKEN_HEADER_NAME: token},
            json={
                "tool": "get_system_info",
                "parameters": {"unexpected_param": "foo"},
            },
        )
        assert response.status_code == 422
        assert "takes no parameters" in response.json()["detail"]


class DummyParamModel(BaseModel):
    name: str = Field(..., min_length=2)
    count: int = Field(..., gt=0)


def test_parameterized_tool_validation() -> None:
    """Register and test a tool with typed Pydantic parameters."""
    @registry.register(
        name="test_echo_tool",
        description="Test echo tool",
        param_model=DummyParamModel,
    )
    def test_echo_tool(name: str, count: int) -> dict:
        return {"echo": name * count}

    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        token = get_active_token()
        assert token is not None

        # 1. Valid parameters
        res_ok = client.post(
            "/ipc/execute",
            headers={TOKEN_HEADER_NAME: token},
            json={"tool": "test_echo_tool", "parameters": {"name": "Hi", "count": 3}},
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["result"] == {"echo": "HiHiHi"}

        # 2. Invalid parameter type / constraint
        res_bad = client.post(
            "/ipc/execute",
            headers={TOKEN_HEADER_NAME: token},
            json={"tool": "test_echo_tool", "parameters": {"name": "H", "count": -1}},
        )
        assert res_bad.status_code == 422


def test_list_tools_endpoint() -> None:
    """Verify GET /ipc/tools returns registered tool definitions."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        token = get_active_token()
        assert token is not None

        response = client.get("/ipc/tools", headers={TOKEN_HEADER_NAME: token})
        assert response.status_code == 200
        tools = response.json()
        tool_names = [t["name"] for t in tools]
        assert "get_system_info" in tool_names

