"""Live server integration test:
1. Starts the real Uvicorn server on http://127.0.0.1:8765
2. Queries GET http://127.0.0.1:8765/health
3. Validates the JSON payload
4. Shuts down the server cleanly
"""

import json
import subprocess
import sys
import time
from pathlib import Path
import httpx

AGENT_DIR = Path(__file__).resolve().parents[1]
PYTHON_EXE = sys.executable
RUN_AGENT = str(AGENT_DIR / "run_agent.py")


def test_live_server() -> None:
    print(f"[TEST] Starting live agent process using {PYTHON_EXE}...")
    proc = subprocess.Popen(
        [PYTHON_EXE, RUN_AGENT],
        cwd=str(AGENT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    url = "http://127.0.0.1:8765/health"
    max_retries = 20
    health_data = None

    try:
        print("[TEST] Polling for server readiness at", url)
        for i in range(max_retries):
            time.sleep(0.5)
            try:
                with httpx.Client(timeout=2.0) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        health_data = resp.json()
                        print(f"[TEST] Received 200 OK after {round((i + 1) * 0.5, 1)}s")
                        break
            except (httpx.ConnectError, httpx.ReadTimeout):
                continue

        assert health_data is not None, "Server failed to respond within timeout!"
        print("[TEST] Validating JSON response payload:")
        print(json.dumps(health_data, indent=2))

        assert health_data["status"] == "ok"
        assert health_data["agent_name"] == "SparkDesk Local Agent"
        assert health_data["python_version"].startswith("3.13")
        assert isinstance(health_data["uptime_seconds"], (int, float))
        assert "timestamp" in health_data
        print("[TEST] All payload assertions passed successfully!")

    finally:
        print("[TEST] Initiating clean server shutdown...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
            print(f"[TEST] Server process terminated cleanly with returncode: {proc.returncode}")
        except subprocess.TimeoutExpired:
            proc.kill()
            print("[TEST] Server required force kill after timeout.")


if __name__ == "__main__":
    test_live_server()
