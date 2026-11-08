"""End-to-end verification of AutoHotkey AgentBridge with Python Local Agent."""

import subprocess
from pathlib import Path
import pytest

AHK_EXE = r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"
AHK_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "TestAgentBridge.ahk"


def test_autohotkey_agent_bridge_scenarios() -> None:
    """Run the complete AutoHotkey AgentBridge test suite verifying:
    1. Unavailable server handling
    2. Authenticated communication (200 pong)
    3. Invalid token rejection (401 Unauthorized)
    4. Timeout handling
    5. Tool execution (get_system_info -> 200 OK + metrics)
    6. Unknown tool rejection (404 Not Found)
    7. Invalid parameter rejection (422 Unprocessable Content)
    8. Phase 5: Natural Language general system info ("show my system specs")
    9. Phase 5: Natural Language RAM-specific ("how much ram is free")
    10. Phase 5: Natural Language CPU-specific ("what is my cpu usage")
    11. Phase 5: Natural Language unsupported command rejection ("order a pizza")
    12. Phase 5: Natural Language ambiguous request detection ("info")
    13. Phase 5: Natural Language authentication failure
    14. Clean authenticated shutdown
    """
    if not Path(AHK_EXE).is_file():
        pytest.skip(f"AutoHotkey v2 executable not found at {AHK_EXE}")

    result = subprocess.run(
        [AHK_EXE, str(AHK_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, f"AutoHotkey test suite failed!\nOutput:\n{result.stdout}\nStderr:\n{result.stderr}"
    assert "0 Failed" in result.stdout
    assert "Passed" in result.stdout
