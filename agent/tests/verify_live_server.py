"""Live server integration test:
1. Starts the real Uvicorn server on http://127.0.0.1:8765
2. Polls GET http://127.0.0.1:8765/health
3. Verifies that data/session.token was created
4. Tests authenticated GET /ipc/ping with valid token -> 200 OK
5. Tests authenticated GET /ipc/ping with invalid token -> 401 Unauthorized
6. Tests authenticated GET /ipc/ping with missing token -> 401 Unauthorized
7. Triggers authenticated graceful shutdown via POST http://127.0.0.1:8765/shutdown
8. Verifies that the process exits cleanly with return code 0
9. Verifies that data/session.token was cleaned up
"""

import json
import subprocess
import sys
import time
from pathlib import Path
import httpx

AGENT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = AGENT_DIR.parent
TOKEN_FILE = ROOT_DIR / "data" / "session.token"
PYTHON_EXE = sys.executable
RUN_AGENT = str(AGENT_DIR / "run_agent.py")


def test_live_server_authenticated_lifecycle() -> None:
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
    ping_url = f"{base_url}/ipc/ping"
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
                        print(f"[TEST] Server ready after {round((i + 1) * 0.5, 1)}s")
                        break
            except (httpx.ConnectError, httpx.ReadTimeout):
                continue

        assert health_data is not None, "Server failed to respond within timeout!"
        assert health_data["status"] == "ok"

        # Verify token file exists on disk
        print(f"[TEST] Checking session token file at {TOKEN_FILE}...")
        assert TOKEN_FILE.is_file(), f"Token file {TOKEN_FILE} was not created!"
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        assert len(token) >= 32, "Token is too short or empty!"
        print("[TEST] Ephemeral token file successfully verified on disk (length:", len(token), "chars)")

        with httpx.Client(timeout=2.0) as client:
            # Test 1: Authenticated GET /ipc/ping with valid token
            print("[TEST] Testing GET /ipc/ping with valid token...")
            ping_resp = client.get(ping_url, headers={"X-SparkDesk-Token": token})
            assert ping_resp.status_code == 200, f"Expected 200, got {ping_resp.status_code}: {ping_resp.text}"
            ping_json = ping_resp.json()
            assert ping_json["status"] == "pong"
            print("[TEST] Valid token accepted: pong received.")

            # Test 2: Authenticated GET /ipc/ping with invalid token
            print("[TEST] Testing GET /ipc/ping with invalid token...")
            bad_resp = client.get(ping_url, headers={"X-SparkDesk-Token": "invalid_bogus_token"})
            assert bad_resp.status_code == 401, f"Expected 401, got {bad_resp.status_code}"
            print("[TEST] Invalid token properly rejected with 401 Unauthorized.")

            # Test 3: Authenticated GET /ipc/ping with missing token
            print("[TEST] Testing GET /ipc/ping with missing token header...")
            no_token_resp = client.get(ping_url)
            assert no_token_resp.status_code == 401, f"Expected 401, got {no_token_resp.status_code}"
            print("[TEST] Missing token properly rejected with 401 Unauthorized.")

            # Test 4: Protected POST /shutdown with invalid token
            print("[TEST] Testing POST /shutdown with invalid token...")
            bad_shutdown = client.post(shutdown_url, headers={"X-SparkDesk-Token": "wrong_token"})
            assert bad_shutdown.status_code == 401, f"Expected 401, got {bad_shutdown.status_code}"
            print("[TEST] Unauthorized shutdown attempt rejected with 401.")

            # Test 5: Protected POST /shutdown with valid token
            print("[TEST] Sending authorized shutdown request...")
            shutdown_resp = client.post(shutdown_url, headers={"X-SparkDesk-Token": token})
            assert shutdown_resp.status_code == 200, f"Shutdown request failed: {shutdown_resp.text}"
            print("[TEST] Authorized shutdown acknowledged.")

        # Wait for clean process termination
        print("[TEST] Awaiting process exit...")
        proc.wait(timeout=10)
        print(f"[TEST] Process exited with returncode: {proc.returncode}")
        assert proc.returncode == 0, f"Process did not exit cleanly! Return code: {proc.returncode}"

        # Test 6: Verify token file cleanup
        time.sleep(0.2)
        assert not TOKEN_FILE.exists(), f"Token file {TOKEN_FILE} was not removed after shutdown!"
        print("[TEST] Session token file removed cleanly from disk.")
        print("[TEST] ALL AUTHENTICATED TESTS PASSED.")

    except Exception as err:
        if proc.poll() is None:
            proc.kill()
        raise err


if __name__ == "__main__":
    test_live_server_authenticated_lifecycle()
