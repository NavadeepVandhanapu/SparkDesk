# SparkDesk Local Agent (Python 3.13)

This is the Python-based local AI agent component of SparkDesk. It runs locally as a lightweight companion service to the AutoHotkey v2 desktop application.

---

## Directory Structure

```text
SparkDesk/
├── agent/
│   ├── .venv/                      # Python 3.13 Virtual Environment
│   ├── pyproject.toml              # Build & dependency declarations
│   ├── requirements.txt            # Pinned / direct dependencies (FastAPI, Uvicorn, Pydantic)
│   ├── README.md                   # This documentation file
│   ├── run_agent.py                # Agent runner entrypoint
│   └── sparkdesk_agent/            # Core package
│       ├── __init__.py
│       ├── __main__.py             # Executable module entrypoint
│       └── core/
│           ├── __init__.py
│           ├── config.py           # Centralized configuration & settings.ini loader
│           └── logging.py          # Centralized rotating logger (syncs to data/sparkdesk.log)
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

*(If script execution is restricted in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

Installed packages include:
- `fastapi`: Modern, high-performance web framework for the IPC API.
- `uvicorn[standard]`: ASGI server for hosting the local agent service.
- `pydantic`: Data validation and settings management.
- `pydantic-settings`: Strongly-typed configuration with environment variable support.

---

## Shared Configuration

The agent reads configuration from the existing `config/settings.ini` without modifying it:

```ini
[General]
ShowStartupNotification=true

; Optional agent overrides can be placed here:
[Agent]
Host=127.0.0.1
Port=8765
Debug=false
LogLevel=INFO
```

You can also override any setting using environment variables with the `SPARKDESK_AGENT_` prefix (e.g., `SPARKDESK_AGENT_PORT=8800`).

---

## Logging

Logs are formatted consistently with SparkDesk's AutoHotkey logger:
`YYYY-MM-DD HH:MM:SS [LEVEL] [LOGGER] Message`

Logs are output to:
1. Console (`stdout`)
2. Rotating file handler at `data/sparkdesk.log` (5 MB per file, 3 backups, UTF-8 encoded).

---

## Verification

To verify that the configuration and logging are working properly:

```powershell
.\.venv\Scripts\python.exe run_agent.py
```
or
```powershell
.\.venv\Scripts\python.exe -m sparkdesk_agent
```

