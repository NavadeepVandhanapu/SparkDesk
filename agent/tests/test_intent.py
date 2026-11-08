"""Unit and integration tests for natural language command understanding and intent engine."""

import pytest
from fastapi.testclient import TestClient

from sparkdesk_agent.core.config import AgentSettings
from sparkdesk_agent.intent.engine import IntentEngine, intent_engine
from sparkdesk_agent.intent.models import IntentStatus
from sparkdesk_agent.ipc.auth import TOKEN_HEADER_NAME, get_active_token
from sparkdesk_agent.ipc.server import create_app


# ==============================================================================
# Engine-level Unit Tests
# ==============================================================================

@pytest.mark.parametrize(
    "prompt, expected_focus",
    [
        ("what is my system info", "all"),
        ("show specs", "all"),
        ("tell me my computer specs", "all"),
        ("check my system details", "all"),
        ("pc health", "all"),
        ("system status", "all"),
        ("how much ram is free", "memory"),
        ("check memory usage", "memory"),
        ("available ram", "memory"),
        ("how is my cpu doing", "cpu"),
        ("check processor load", "cpu"),
        ("what is my cpu usage", "cpu"),
        ("how much disk space is left", "disk"),
        ("check hard drive storage", "disk"),
        ("c drive free space", "disk"),
        ("how long has my pc been running", "uptime"),
        ("system uptime", "uptime"),
        ("when did my computer start", "uptime"),
    ],
)
def test_system_info_variations_recognized(prompt: str, expected_focus: str) -> None:
    """Verify multiple natural language variations map correctly to get_system_info."""
    result = intent_engine.classify(prompt)
    assert result.status == IntentStatus.RECOGNIZED
    assert result.intent == "get_system_info"
    assert result.tool == "get_system_info"
    assert result.parameters == {}
    assert result.confidence >= 0.8
    assert result.focus == expected_focus


@pytest.mark.parametrize(
    "unsupported_prompt",
    [
        "what is the weather today",
        "order a pepperoni pizza",
        "play jazz music",
        "search google for news",
        "who are you and what can you do",
        "write a python script for me",
        "tell me a funny joke",
    ],
)
def test_unsupported_queries_rejected_safely(unsupported_prompt: str) -> None:
    """Verify out-of-scope commands are safely rejected with helpful guidance."""
    result = intent_engine.classify(unsupported_prompt)
    assert result.status == IntentStatus.UNSUPPORTED
    assert result.tool is None
    assert result.message is not None
    assert "Currently supported" in result.message or "Try asking" in result.message


@pytest.mark.parametrize(
    "ambiguous_prompt",
    [
        "info",
        "check",
        "status",
        "details",
        "what",
        "stats",
    ],
)
def test_ambiguous_queries_detected(ambiguous_prompt: str) -> None:
    """Verify single vague tokens prompt clarification rather than executing blindly."""
    result = intent_engine.classify(ambiguous_prompt)
    assert result.status == IntentStatus.AMBIGUOUS
    assert result.tool is None
    assert result.message is not None
    assert "ambiguous" in result.message.lower()


def test_human_readable_response_formatting() -> None:
    """Verify response formatting generates clean, structured summaries."""
    dummy_data = {
        "os": {"platform": "Windows 11", "architecture": "64bit", "version": "10.0.26300"},
        "cpu": {"processor": "Intel Core i7", "logical_cores": 12, "usage_percent": 15.5},
        "memory": {"total_gb": 16.0, "available_gb": 8.0, "used_gb": 8.0, "usage_percent": 50.0},
        "disk": {"drive": "C:\\", "total_gb": 500.0, "free_gb": 200.0, "used_gb": 300.0, "usage_percent": 60.0},
        "uptime": {"uptime_seconds": 3600, "uptime_formatted": "1h 0m 0s", "boot_time": "2026-11-08T00:00:00Z"},
    }

    # 1. Comprehensive summary
    intent_all = intent_engine.classify("show my system info")
    text_all = intent_engine.format_response(intent_all, dummy_data)
    assert "Operating System" in text_all
    assert "CPU Utilization" in text_all
    assert "Memory (RAM)" in text_all
    assert "Storage" in text_all
    assert "System Uptime" in text_all

    # 2. Targeted memory summary
    intent_mem = intent_engine.classify("how much ram is free")
    text_mem = intent_engine.format_response(intent_mem, dummy_data)
    assert "Memory (RAM) Status" in text_mem
    assert "8.0 GB free" in text_mem


# ==============================================================================
# API Endpoint Integration Tests
# ==============================================================================

def test_authenticated_intent_endpoint() -> None:
    """Verify POST /ipc/intent analyzes prompt and returns IntentResult."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        token = get_active_token()
        assert token is not None

        # 1. Recognized query
        res = client.post(
            "/ipc/intent",
            headers={TOKEN_HEADER_NAME: token},
            json={"prompt": "check my ram usage"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "recognized"
        assert data["tool"] == "get_system_info"
        assert data["focus"] == "memory"

        # 2. Ambiguous query
        res_amb = client.post(
            "/ipc/intent",
            headers={TOKEN_HEADER_NAME: token},
            json={"prompt": "info"},
        )
        assert res_amb.status_code == 200
        assert res_amb.json()["status"] == "ambiguous"

        # 3. Unsupported query
        res_un = client.post(
            "/ipc/intent",
            headers={TOKEN_HEADER_NAME: token},
            json={"prompt": "what is the weather"},
        )
        assert res_un.status_code == 200
        assert res_un.json()["status"] == "unsupported"


def test_authenticated_command_pipeline_success() -> None:
    """Verify POST /ipc/command classifies intent, executes tool, and returns response."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        token = get_active_token()
        assert token is not None

        res = client.post(
            "/ipc/command",
            headers={TOKEN_HEADER_NAME: token},
            json={"prompt": "show my system specs"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "recognized"
        assert data["tool"] == "get_system_info"
        assert "System Overview" in data["message"] or "Operating System" in data["message"]
        assert data["tool_result"] is not None
        assert "memory" in data["tool_result"]


def test_command_pipeline_authentication_failure() -> None:
    """Verify POST /ipc/command requires valid authentication."""
    settings = AgentSettings()
    app = create_app(settings)

    with TestClient(app) as client:
        # Missing token
        res_missing = client.post(
            "/ipc/command",
            json={"prompt": "show system specs"},
        )
        assert res_missing.status_code == 401

        # Invalid token
        res_invalid = client.post(
            "/ipc/command",
            headers={TOKEN_HEADER_NAME: "wrong_token_xyz"},
            json={"prompt": "show system specs"},
        )
        assert res_invalid.status_code == 401
