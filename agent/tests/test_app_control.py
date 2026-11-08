"""Comprehensive Unit and Integration Tests for Phase 7.1 Application Control.

Verifies:
1. Application name sanitization and path traversal / shell injection prevention.
2. Allow-list catalog resolution, canonical naming, and aliases.
3. Process inspection via is_app_running.
4. Safe application launching via open_app.
5. Mandatory user confirmation enforcement in close_app.
6. Safe process termination with confirmed=True in close_app.
7. Critical Windows system process protection (explorer, dwm, taskmgr, svchost, etc.).
8. ToolRegistry integration and parameter schema validation.
9. End-to-end IntelligencePipeline orchestration with natural language prompts and context confirmation.
10. Authenticated HTTP IPC endpoints (/ipc/execute and /ipc/command).
"""

import os
import time
from typing import Dict, Any
import psutil
import pytest
from fastapi.testclient import TestClient

from sparkdesk_agent.core.config import AgentSettings
from sparkdesk_agent.intelligence.pipeline import IntelligencePipeline
from sparkdesk_agent.intent.models import CommandRequest, IntentStatus
from sparkdesk_agent.ipc.auth import TOKEN_HEADER_NAME, get_active_token
from sparkdesk_agent.ipc.server import create_app
from sparkdesk_agent.tools.app_control import (
    APPLICATION_CATALOG,
    CRITICAL_PROCESSES,
    close_app,
    is_app_running,
    open_app,
    resolve_application,
    sanitize_app_name,
)
from sparkdesk_agent.tools.registry import ToolError, ToolValidationError, registry


# ==============================================================================
# 1. Sanitization & Resolution Unit Tests
# ==============================================================================

def test_sanitize_app_name_valid() -> None:
    """Verify clean normalization of valid app names."""
    assert sanitize_app_name("notepad") == "notepad"
    assert sanitize_app_name("  Notepad  ") == "notepad"
    assert sanitize_app_name("Google Chrome") == "google chrome"
    assert sanitize_app_name("calc.exe") == "calc"
    assert sanitize_app_name("Notepad.EXE") == "notepad"


@pytest.mark.parametrize(
    "malicious_input",
    [
        "notepad; calc",
        "C:\\Windows\\System32\\calc.exe",
        "/bin/sh",
        "../../hack",
        "notepad & powershell",
        "calc | dir",
        "notepad `whoami`",
        "calc $(whoami)",
        "a" * 65,  # Exceeds max length
        "",
        "   ",
    ],
)
def test_sanitize_app_name_blocks_injection_and_paths(malicious_input: str) -> None:
    """Security test: Ensure path separators, shell operators, and overlong inputs are rejected."""
    with pytest.raises(ToolValidationError):
        sanitize_app_name(malicious_input)


def test_resolve_application_canonical_and_aliases() -> None:
    """Verify application resolution maps aliases to canonical catalog entries."""
    # Canonical
    entry_np = resolve_application("notepad")
    assert entry_np["canonical_name"] == "notepad"
    assert entry_np["display_name"] == "Notepad"

    # Aliases
    assert resolve_application("text editor")["canonical_name"] == "notepad"
    assert resolve_application("calc")["canonical_name"] == "calculator"
    assert resolve_application("google chrome")["canonical_name"] == "chrome"
    assert resolve_application("code")["canonical_name"] == "vscode"
    assert resolve_application("visual studio code")["canonical_name"] == "vscode"
    assert resolve_application("task manager")["canonical_name"] == "taskmanager"


def test_resolve_application_unsupported_rejection() -> None:
    """Verify unsupported applications raise ToolValidationError listing allowed apps."""
    with pytest.raises(ToolValidationError, match="not in the allow-list"):
        resolve_application("unsupported_custom_game_999")


# ==============================================================================
# 2. Process Inspection & Execution Unit Tests
# ==============================================================================

def test_is_app_running_structure() -> None:
    """Verify is_app_running returns expected schema and accurate status."""
    res = is_app_running("notepad")
    assert res["app_name"] == "Notepad"
    assert res["canonical_name"] == "notepad"
    assert isinstance(res["is_running"], bool)
    assert isinstance(res["instance_count"], int)
    assert isinstance(res["instances"], list)
    assert isinstance(res["pids"], list)
    assert "message" in res


def test_open_and_close_app_lifecycle() -> None:
    """Test launching an allow-listed app, inspecting it, and closing it with confirmation."""
    # 1. Open Notepad
    open_res = open_app("notepad")
    assert open_res["launched"] is True
    assert open_res["pid"] > 0
    test_pid = open_res["pid"]

    try:
        # Give OS a moment to register process
        time.sleep(0.5)

        # 2. Check is_app_running
        status_res = is_app_running("notepad")
        assert status_res["is_running"] is True
        assert status_res["instance_count"] >= 1
        assert len(status_res["pids"]) >= 1

        # 3. Close without confirmation: MUST NOT terminate
        unconfirmed_res = close_app("notepad", confirmed=False)
        assert unconfirmed_res["closed"] is False
        assert unconfirmed_res["requires_confirmation"] is True
        assert len(unconfirmed_res["pids"]) >= 1
        assert "Confirmation Required" in unconfirmed_res["message"]

        # Verify process is still alive!
        assert is_app_running("notepad")["is_running"] is True

        # 4. Close WITH confirmation: MUST terminate
        confirmed_res = close_app("notepad", confirmed=True)
        assert confirmed_res["closed"] is True
        assert confirmed_res["requires_confirmation"] is False
        assert confirmed_res["instances_terminated"] >= 1

        time.sleep(0.5)
        # Verify process has exited
        assert is_app_running("notepad")["is_running"] is False

    finally:
        # Cleanup in case of assertion failure
        if psutil.pid_exists(test_pid):
            try:
                psutil.Process(test_pid).kill()
            except Exception:
                pass


# ==============================================================================
# 3. Critical Process Protection Security Tests
# ==============================================================================

@pytest.mark.parametrize(
    "critical_app",
    [
        "explorer",
        "taskmanager",
    ],
)
def test_critical_processes_cannot_be_closed(critical_app: str) -> None:
    """Security test: Ensure critical Windows processes cannot be closed even with confirmed=True."""
    with pytest.raises(ToolError, match="prohibited|protected"):
        close_app(critical_app, confirmed=True)


def test_critical_process_set_membership() -> None:
    """Security test: Ensure vital system binaries are present in CRITICAL_PROCESSES."""
    vital = {"explorer.exe", "dwm.exe", "csrss.exe", "lsass.exe", "services.exe", "svchost.exe"}
    assert vital.issubset(CRITICAL_PROCESSES)


# ==============================================================================
# 4. Tool Registry Registration Tests
# ==============================================================================

def test_app_control_tools_registered_in_registry() -> None:
    """Verify open_app, is_app_running, and close_app are in ToolRegistry."""
    assert registry.has_tool("open_app")
    assert registry.has_tool("is_app_running")
    assert registry.has_tool("close_app")

    tools_list = {t["name"]: t for t in registry.list_tools()}
    assert "open_app" in tools_list
    assert "is_app_running" in tools_list
    assert "close_app" in tools_list
    assert tools_list["close_app"]["parameters_schema"] is not None


@pytest.mark.anyio
async def test_registry_execute_app_control() -> None:
    """Verify tools execute through registry.execute with parameter schema validation."""
    # Test is_app_running
    res = await registry.execute("is_app_running", {"app_name": "calculator"})
    assert res["canonical_name"] == "calculator"
    assert "is_running" in res

    # Test parameter validation failure on missing required parameter
    with pytest.raises(ToolValidationError):
        await registry.execute("open_app", {})

    # Test parameter validation failure on unexpected parameter
    with pytest.raises(ToolValidationError):
        await registry.execute("open_app", {"app_name": "notepad", "bogus_param": 123})


# ==============================================================================
# 5. Intelligence Pipeline & Natural Language Tests
# ==============================================================================

@pytest.mark.anyio
async def test_pipeline_natural_language_open_and_close() -> None:
    """Test full pipeline natural language orchestration for app control."""
    pipe = IntelligencePipeline()
    session_id = "test_app_ctrl_session"

    # 1. Natural Language: "open notepad"
    open_req = CommandRequest(prompt="open notepad", session_id=session_id)
    open_resp = await pipe.process(open_req)
    assert open_resp.success is True
    assert open_resp.status == "recognized"
    assert open_resp.tool == "open_app"
    assert "Opened Notepad" in open_resp.message or "Successfully opened" in open_resp.message
    test_pid = open_resp.tool_result.get("pid")
    assert test_pid is not None and test_pid > 0

    try:
        time.sleep(0.5)

        # 2. Natural Language: "is notepad running"
        check_req = CommandRequest(prompt="is notepad running", session_id=session_id)
        check_resp = await pipe.process(check_req)
        assert check_resp.success is True
        assert check_resp.status == "recognized"
        assert check_resp.tool == "is_app_running"
        assert "currently running" in check_resp.message

        # 3. Natural Language: "close notepad" (Unconfirmed -> prompts for confirmation)
        close_req = CommandRequest(prompt="close notepad", session_id=session_id)
        close_resp = await pipe.process(close_req)
        assert close_resp.success is True
        assert close_resp.status == "recognized"
        assert close_resp.tool == "close_app"
        assert "Confirmation Required" in close_resp.message
        assert close_resp.tool_result["requires_confirmation"] is True
        assert is_app_running("notepad")["is_running"] is True  # Still running!

        # 4. Contextual Natural Language Follow-up: "yes" confirms the close!
        confirm_req = CommandRequest(prompt="yes", session_id=session_id)
        confirm_resp = await pipe.process(confirm_req)
        assert confirm_resp.success is True
        assert confirm_resp.status == "recognized"
        assert confirm_resp.tool == "close_app"
        assert "Successfully closed" in confirm_resp.message
        assert confirm_resp.tool_result["closed"] is True

        time.sleep(0.5)
        assert is_app_running("notepad")["is_running"] is False  # Process terminated!

    finally:
        if test_pid and psutil.pid_exists(test_pid):
            try:
                psutil.Process(test_pid).kill()
            except Exception:
                pass


@pytest.mark.anyio
async def test_pipeline_unsupported_app_query() -> None:
    """Verify natural language requests for unlisted apps are safely rejected."""
    pipe = IntelligencePipeline()
    req = CommandRequest(prompt="open unknown_software_xyz")
    resp = await pipe.process(req)
    assert resp.success is False
    assert resp.status == "unsupported"
    assert "not in the allow-list" in resp.message


# ==============================================================================
# 6. HTTP API Endpoint Tests
# ==============================================================================

def test_http_api_app_control_endpoints() -> None:
    """Verify /ipc/execute and /ipc/command endpoints with app control actions."""
    app = create_app(AgentSettings(debug=True))
    with TestClient(app) as client:
        token = get_active_token()
        headers = {TOKEN_HEADER_NAME: token}

        # 1. Execute is_app_running via /ipc/execute
        exec_res = client.post(
            "/ipc/execute",
            headers=headers,
            json={"tool": "is_app_running", "parameters": {"app_name": "notepad"}},
        )
        assert exec_res.status_code == 200
        data = exec_res.json()
        assert data["success"] is True
        assert data["tool"] == "is_app_running"
        assert "is_running" in data["result"]

        # 2. Command pipeline via /ipc/command
        cmd_res = client.post(
            "/ipc/command",
            headers=headers,
            json={"prompt": "check if calculator is open"},
        )
        assert cmd_res.status_code == 200
        cmd_data = cmd_res.json()
        assert cmd_data["success"] is True
        assert cmd_data["tool"] == "is_app_running"
