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
│   │   ├── test_tools.py           # ToolRegistry unit and integration tests
│   │   ├── test_intent.py          # Intent classification unit tests
│   │   ├── test_app_control.py     # Phase 7.1 Application Control tests
│   │   ├── test_intelligence.py    # Phase 6 Intelligence Architecture tests
│   │   ├── test_ahk_bridge.py      # End-to-end AutoHotkey bridge verification
│   │   └── verify_live_server.py   # Live socket integration verification script
│   └── sparkdesk_agent/            # Core package
│       ├── __init__.py
│       ├── __main__.py             # Executable module entrypoint (`python -m sparkdesk_agent`)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py           # Centralized configuration & settings.ini loader
│       │   └── logging.py          # Centralized rotating logger (syncs to data/sparkdesk.log)
│       ├── intelligence/           # Phase 6 Intelligence Architecture
│       │   ├── __init__.py
│       │   ├── provider.py         # Model-independent BaseIntelligenceProvider & RuleBasedProvider
│       │   ├── planner.py          # TaskPlanner & structured ExecutionPlan / PlanStep
│       │   ├── validator.py        # PlanValidator against ToolRegistry schemas & security
│       │   ├── context.py          # ConversationContext, ConversationTurn & ContextManager
│       │   └── pipeline.py         # Central IntelligencePipeline orchestrator
│       ├── intent/
│       │   ├── __init__.py
│       │   ├── engine.py           # Pattern classifier & metric formatting
│       │   └── models.py           # CommandRequest, CommandResponse, IntentResult
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── registry.py         # Central Tool Registry with Pydantic validation
│       │   ├── system_info.py      # System diagnostic tool (`get_system_info`)
│       │   └── app_control.py      # Phase 7.1 Application Control tools
│       └── ipc/
│           ├── __init__.py
│           ├── auth.py             # Ephemeral token generation & verification
│           ├── protocol.py         # IPC and health check Pydantic schemas
│           └── server.py           # FastAPI application and Uvicorn server
├── config/
│   └── settings.ini                # Shared AutoHotkey + Agent configuration
├── data/
│   └── sparkdesk.log               # Shared runtime log file
├── modules/                        # AutoHotkey modules (including AgentBridge.ahk)
└── main.ahk                        # AutoHotkey main entrypoint
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
```

### 3. Run the Agent

You can start the agent directly:

```powershell
python run_agent.py
```

Or run it as a Python module:

```powershell
python -m sparkdesk_agent
```

---

## Phase 6: Intelligence Architecture

Phase 6 introduces a modular, model-independent **Intelligence Architecture** separating intent understanding, planning, validation, and execution:

1. **Model-Independent Intelligence Interface (`BaseIntelligenceProvider`)**:
   - An abstract interface allowing seamless swapping between the default zero-dependency `RuleBasedIntelligenceProvider` and future local LLM backends (such as Ollama).
   - Dynamic provider registration via `register_provider()` and `get_provider()`.

2. **Task Planner (`TaskPlanner`)**:
   - Translates classified user requests into structured, deterministic `ExecutionPlan` objects consisting of discrete `PlanStep`s.
   - Ambiguous or unsupported requests are safely rejected without creating executable steps.

3. **Plan Validator (`PlanValidator`)**:
   - Strictly enforces that planned tools are allow-listed in the secure `ToolRegistry`.
   - Validates parameters against tool Pydantic schemas.
   - Deep-scans parameters to prevent shell command injection or dynamic Python code execution.
   - Prevents the intelligence layer from bypassing the ToolRegistry.

4. **Conversation Context Support (`ContextManager`, `ConversationContext`)**:
   - Tracks multi-turn conversational history (`ConversationTurn`), topic focus, and executed tool state.
   - Enables contextual follow-up requests (e.g. "what about CPU?", "how about disk space?", "refresh").
   - Thread-safe in-memory session isolation with automatic history pruning.

5. **Central Pipeline (`IntelligencePipeline`)**:
   - Coordinates the request lifecycle: Context -> Intent Understanding -> Planning -> Validation -> Tool Execution -> Response Formatting -> Context Turn Update.

---

## Phase 7.1: Application Control

Phase 7.1 expands SparkDesk's automation capabilities with secure, allow-listed Windows application management:

1. **Registered Application Control Tools**:
   - `open_app(app_name: str)`: Resolves an allow-listed application and safely launches its Windows executable via `subprocess.Popen` without invoking the system command shell (`shell=False`).
   - `is_app_running(app_name: str)`: Inspects active processes via `psutil` against the target application's known process binaries and reports execution state, PID list, and instance count.
   - `close_app(app_name: str, force: bool = False, confirmed: bool = False)`: Safely terminates running application processes. Requires explicit user confirmation (`confirmed=True`) before termination.

2. **Supported Application Catalog (Allow-list)**:
   - **Notepad** (`notepad`, `text editor`, `notes`) $\to$ `notepad.exe`
   - **Calculator** (`calc`, `calculator`, `math`) $\to$ `calc.exe`
   - **Paint** (`mspaint`, `paint`, `draw`) $\to$ `mspaint.exe`
   - **Command Prompt** (`cmd`, `terminal`, `command prompt`, `console`) $\to$ `cmd.exe`
   - **PowerShell** (`powershell`, `pwsh`, `posh`) $\to$ `powershell.exe`
   - **Google Chrome** (`chrome`, `google chrome`, `browser`) $\to$ `chrome.exe`
   - **Mozilla Firefox** (`firefox`, `mozilla firefox`) $\to$ `firefox.exe`
   - **Microsoft Edge** (`edge`, `msedge`, `microsoft edge`) $\to$ `msedge.exe`
   - **Spotify** (`spotify`, `music player`) $\to$ `Spotify.exe`
   - **Visual Studio Code** (`code`, `vscode`, `vs code`, `visual studio code`) $\to$ `Code.exe`

3. **Critical Process Blacklist Protection**:
   - Termination is strictly prohibited for core Windows components and system processes, including `explorer.exe`, `dwm.exe`, `taskmgr.exe`, `csrss.exe`, `winlogon.exe`, `lsass.exe`, `services.exe`, `svchost.exe`, `smss.exe`, `system`, and SparkDesk runtime processes.

4. **Strict Input Sanitization & Anti-Injection**:
   - Application names undergo strict regex validation (`^[a-zA-Z0-9_\-\s]+$`) and path delimiter / command-chaining character rejection (e.g. `;`, `&`, `|`, `` ` ``, `$()`, `\`, `/`).
   - Direct execution of arbitrary filesystem paths or unrecognized binaries is forbidden.
   - Pydantic models forbid unexpected parameters (`extra="forbid"`).

5. **Natural Language Integration & Conversational Confirmation**:
   - Natural language requests such as "open notepad", "is chrome running", "close calculator" map directly into the Intelligence Pipeline.
   - Unconfirmed close requests return a clear prompt requiring user confirmation; follow-up conversational confirmations (e.g. "yes", "confirm", "proceed", "cancel") resolve via the Conversation Context.

---

## Available IPC Endpoints

### `GET /health`
Loopback health check probe returning agent name, version, Python version, uptime, and process PID.

### `GET /ipc/ping`
Authenticated connectivity test for AutoHotkey AgentBridge. Requires `X-SparkDesk-Token` header.

### `GET /ipc/tools`
Authenticated listing of all allow-listed tools, descriptions, and JSON parameter schemas.

### `POST /ipc/execute`
Authenticated tool execution endpoint. Requires `X-SparkDesk-Token` header.
Payload: `{"tool": "get_system_info", "parameters": {}}`.
Executes explicitly registered tools (e.g. `get_system_info`) and returns structured JSON metrics. Rejects unlisted tools (404) and invalid parameters (422).

### `POST /ipc/intent`
Authenticated natural language intent classification endpoint. Requires `X-SparkDesk-Token` header.
Payload: `{"prompt": "how much ram is free", "session_id": "optional_id"}`.
Classifies prompt within session context into `recognized`, `ambiguous`, or `unsupported`.

### `POST /ipc/command`
Authenticated end-to-end natural language command pipeline. Requires `X-SparkDesk-Token` header.
Payload: `{"prompt": "show my system specs", "session_id": "optional_id"}`.
Orchestrates context retrieval, planning, schema validation, tool execution, and human-readable response formatting.

### `GET /ipc/context` & `DELETE /ipc/context`
Authenticated context inspection and reset endpoints for conversation sessions.

### `POST /shutdown`
Protected graceful shutdown endpoint. Requires `X-SparkDesk-Token` header.
Terminates the Uvicorn server, executes lifespan shutdown hooks, and cleans up the ephemeral session token file.

---

## Authentication & Security

1. **Strict Loopback Binding**: The agent binds strictly to `127.0.0.1` and rejects any external host or wildcard IP at configuration, server startup, and CLI.
2. **Ephemeral Session Tokens**: On startup, the agent generates a cryptographically secure 256-bit token (`secrets.token_urlsafe(32)`) and writes it to `data/session.token` with strict local file permissions.
3. **Automatic Cleanup**: On shutdown, `data/session.token` is deleted immediately.
4. **Zero-Log Policy**: The secret token is never logged to `sparkdesk.log`, stdout, or error reports.
5. **ToolRegistry Isolation**: Tools can only be executed if explicitly registered in `ToolRegistry`. Arbitrary commands and dynamic code execution are forbidden.
6. **Plan Deep-Scanning**: All execution plans are validated against parameter schemas and inspected for command injection patterns prior to invocation.

---

## Running Tests

Run the full pytest suite (including unit tests, intelligence tests, and AutoHotkey bridge):
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
