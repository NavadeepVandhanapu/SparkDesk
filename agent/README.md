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

## Endpoints (Phase 2)

### `GET /health`
Returns the operational health, uptime, process ID, and Python runtime version.

**Response Example:**
```json
{
  "status": "ok",
  "agent_name": "SparkDesk Local Agent",
  "version": "0.1.0",
  "python_version": "3.13.14",
  "uptime_seconds": 12.34,
  "pid": 30644,
  "environment": "development",
  "timestamp": "2026-11-06T14:19:02.150567+00:00"
}
```

---

## Running Tests

Run the unit test suite:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_server.py -v
```

Run the live server loopback verification:
```powershell
.\.venv\Scripts\python.exe tests/verify_live_server.py
```
