# SparkDesk Local Agent (Python 3.13)

This is the Python-based local AI agent component of SparkDesk. It runs locally as a lightweight companion service to the AutoHotkey v2 desktop application.

---

## Directory Structure

```text
SparkDesk/
├── agent/
│   ├── .venv/                      # Python 3.13 Virtual Environment
│   ├── pyproject.toml              # Build & dependency declarations
│   ├── requirements.txt            # Pinned dependencies (FastAPI, Uvicorn, Pydantic, HTTPX, Pytest)
│   ├── README.md                   # This documentation file
│   ├── run_agent.py                # Server runner entrypoint
│   ├── tests/                      # Automated test suite
│   │   ├── test_server.py          # Pytest suite for FastAPI application
│   │   └── verify_live_server.py   # Live socket integration verification script
│   └── sparkdesk_agent/            # Core package
│       ├── __init__.py
│       ├── __main__.py             # Executable module entrypoint (`python -m sparkdesk_agent`)
│       ├── core/
│           ├── __init__.py
│           ├── config.py           # Centralized configuration & settings.ini loader
│           └── logging.py          # Centralized rotating logger (syncs to data/sparkdesk.log)
│       └── ipc/
│           ├── __init__.py
│           ├── protocol.py         # IPC and health check Pydantic schemas
│           └── server.py           # FastAPI application and Uvicorn server
├── config/
│   └── settings.ini                # Shared AutoHotkey + Agent configuration
├── data/
│   └── sparkdesk.log               # Shared runtime log file
├── modules/                        # Existing AutoHotkey modules (untouched)
└── main.ahk                        # AutoHotkey main entrypoint (untouched)
```

---

## Prerequisites

- **Python 3.13+** installed on Windows.
- **AutoHotkey v2** (for running the desktop GUI and hotkeys).

---

## Setup Instructions

### 1. Create and Activate Virtual Environment

Open a PowerShell terminal in the `agent` folder:

```powershell
cd C:\Users\91863\Downloads\SparkDesk_2.0_Final\SparkDesk\agent
python3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
pip install -e .
```

---

## Running the Server

Start the local agent server with:

```powershell
.\.venv\Scripts\python.exe run_agent.py
```
or
```powershell
.\.venv\Scripts\python.exe -m sparkdesk_agent
```

CLI Options:
- `--host`: Override binding host (default: `127.0.0.1` from `settings.ini`)
- `--port`: Override binding port (default: `8765` from `settings.ini`)
- `--debug`: Enable debug log level

---

## Endpoints (Phase 2, 3 & 4)

### `GET /health`
Returns the operational health, uptime, process ID, and Python runtime version (unauthenticated loopback probe).

### `GET /ipc/ping`
Authenticated IPC heartbeat endpoint used by AutoHotkey's `AgentBridge.ahk`. Requires `X-SparkDesk-Token` header.
Returns: `{"status": "pong", "agent": "...", "version": "...", "timestamp": "..."}`.

### `GET /ipc/tools`
Authenticated endpoint listing all explicitly registered, allow-listed tools and their parameter schemas.

### `POST /ipc/execute`
Authenticated tool execution endpoint. Requires `X-SparkDesk-Token` header.
Payload: `{"tool": "get_system_info", "parameters": {}}`.
Executes explicitly registered tools (e.g. `get_system_info`) and returns structured JSON metrics. Rejects unlisted tools (404) and invalid parameters (422).

### `POST /shutdown`
Protected graceful shutdown endpoint. Requires `X-SparkDesk-Token` header.
Terminates the Uvicorn server, executes lifespan shutdown hooks, and cleans up the ephemeral session token file.

---

## Authentication & Security

1. **Strict Loopback Binding**: The agent binds strictly to `127.0.0.1` and rejects any external host or wildcard IP at configuration, server startup, and CLI.
2. **Ephemeral Session Tokens**: On startup, the agent generates a cryptographically secure 256-bit token (`secrets.token_urlsafe(32)`) and writes it to `data/session.token` with strict local file permissions.
3. **Automatic Cleanup**: On shutdown, `data/session.token` is deleted immediately.
4. **Zero-Log Policy**: The secret token is never logged to `sparkdesk.log`, stdout, or error reports.

---

## Running Tests

Run the full pytest suite (including Python endpoints and the AutoHotkey bridge end-to-end):
```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

Run the live server loopback verification:
```powershell
.\.venv\Scripts\python.exe tests/verify_live_server.py
```

Run the AutoHotkey AgentBridge test suite directly:
```powershell
& "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe" scripts/TestAgentBridge.ahk
```
