"""End-to-end verification of AutoHotkey AgentBridge with Python Local Agent."""

import subprocess
from pathlib import Path
import pytest

AHK_EXE = r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"
AHK_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "TestAgentBridge.ahk"


def test_autohotkey_agent_bridge_scenarios() -> None:
    """Run the AutoHotkey AgentBridge test suite verifying:
    1. Unavailable server handling
    2. Authenticated communication (200 pong)
    3. Invalid token rejection (401 Unauthorized)
    4. Timeout handling
    5. Tool execution (get_system_info -> 200 OK + metrics)
    6. Unknown tool rejection (404 Not Found)
    7. Invalid parameter rejection (422 Unprocessable Content)
    8. Clean authenticated shutdown
    """
    if not Path(AHK_EXE).is_file():
        pytest.skip(f"AutoHotkey v2 executable not found at {AHK_EXE}")

    result = subprocess.run(
        [AHK_EXE, str(AHK_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=35,
    )
    assert result.returncode == 0, f"AutoHotkey test suite failed!\nOutput:\n{result.stdout}\nStderr:\n{result.stderr}"
    assert "SUMMARY: 9 Passed, 0 Failed" in result.stdout or "SUMMARY: 8 Passed, 0 Failed" in result.stdout
