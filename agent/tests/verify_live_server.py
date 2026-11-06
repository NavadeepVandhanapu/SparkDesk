"""Live server integration test:
1. Starts the real Uvicorn server on http://127.0.0.1:8765
2. Queries GET http://127.0.0.1:8765/health
3. Validates the JSON payload
4. Triggers graceful shutdown via POST http://127.0.0.1:8765/shutdown
5. Verifies that the process exits cleanly with return code 0 (not killed or forced)
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


def test_live_server_graceful_lifecycle() -> None:
    print(f"[TEST] Starting live agent process using {PYTHON_EXE}...")
    proc = subprocess.Popen(
        [PYTHON_EXE, RUN_AGENT],
        cwd=str(AGENT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    base_url = "http://127.0.0.1:8765"
    health_url = f"{base_url}/health"
    shutdown_url = f"{base_url}/shutdown"
    max_retries = 20
    health_data = None

    try:
        print("[TEST] Polling for server readiness at", health_url)
        for i in range(max_retries):
            time.sleep(0.5)
            try:
                with httpx.Client(timeout=2.0) as client:
                    resp = client.get(health_url)
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
        print("[TEST] Health payload validated successfully!")

        # Requirement 2: Graceful shutdown request via endpoint
        print("[TEST] Sending graceful shutdown request to", shutdown_url)
        with httpx.Client(timeout=2.0) as client:
            shutdown_resp = client.post(shutdown_url)
            assert shutdown_resp.status_code == 200, f"Shutdown request failed: {shutdown_resp.text}"
            shutdown_json = shutdown_resp.json()
            assert shutdown_json["status"] == "shutting_down"
            print(f"[TEST] Shutdown endpoint acknowledged: {shutdown_json['message']}")

        # Wait for clean process termination
        print("[TEST] Awaiting process exit...")
        proc.wait(timeout=10)

        stdout, stderr = proc.communicate()
        print(f"[TEST] Process exited with returncode: {proc.returncode}")
        if stdout:
            print(f"[TEST STDOUT]\n{stdout}")
        if stderr:
            print(f"[TEST STDERR]\n{stderr}")

        assert proc.returncode == 0, (
            f"Process did not exit cleanly! Expected returncode 0, got {proc.returncode}."
        )
        print("[TEST] PASS: Server shut down gracefully with exit code 0.")

    except Exception as err:
        if proc.poll() is None:
            print("[TEST] An assertion failed. Force killing leftover process...")
            proc.kill()
        raise err


if __name__ == "__main__":
    test_live_server_graceful_lifecycle()
