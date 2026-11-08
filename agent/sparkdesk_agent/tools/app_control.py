"""Application Control Tools for SparkDesk Local Agent (Phase 7.1).

Provides tools to:
1. open_app: Safely launch allow-listed desktop applications by friendly name.
2. is_app_running: Check process status, instance count, and PIDs.
3. close_app: Safely terminate application processes with mandatory user confirmation
   and critical Windows process protection.

Security Guarantees:
- Never executes arbitrary shell commands or user-supplied executable paths.
- Enforces strict allow-listing of permitted application targets.
- Protects critical Windows system processes (explorer, dwm, svchost, etc.).
- Requires explicit user confirmation (confirmed=True) before any process termination.
"""

import os
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Set

import psutil
from pydantic import BaseModel, ConfigDict, Field

from sparkdesk_agent.core.logging import get_logger
from sparkdesk_agent.tools.registry import ToolError, ToolValidationError, registry

logger = get_logger("sparkdesk_agent.tools.app_control")

# ==============================================================================
# 1. Allow-listed Application Catalog
# ==============================================================================

APPLICATION_CATALOG: Dict[str, Dict[str, Any]] = {
    "notepad": {
        "canonical_name": "notepad",
        "display_name": "Notepad",
        "executables": ["notepad.exe"],
        "aliases": ["notepad", "text editor", "notes", "editor", "txt editor"],
        "process_names": ["notepad.exe", "Notepad.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
    "calculator": {
        "canonical_name": "calculator",
        "display_name": "Calculator",
        "executables": ["calc.exe"],
        "aliases": ["calculator", "calc", "windows calculator"],
        "process_names": ["CalculatorApp.exe", "Calculator.exe", "calc.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
    "paint": {
        "canonical_name": "paint",
        "display_name": "Paint",
        "executables": ["mspaint.exe"],
        "aliases": ["paint", "mspaint", "ms paint"],
        "process_names": ["mspaint.exe", "PaintApp.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
    "cmd": {
        "canonical_name": "cmd",
        "display_name": "Command Prompt",
        "executables": ["cmd.exe"],
        "aliases": ["cmd", "command prompt", "terminal cmd"],
        "process_names": ["cmd.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
    "powershell": {
        "canonical_name": "powershell",
        "display_name": "PowerShell",
        "executables": ["powershell.exe", "pwsh.exe"],
        "aliases": ["powershell", "posh", "pwsh", "windows powershell"],
        "process_names": ["powershell.exe", "pwsh.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
    "taskmanager": {
        "canonical_name": "taskmanager",
        "display_name": "Task Manager",
        "executables": ["taskmgr.exe"],
        "aliases": ["task manager", "taskmgr", "task man"],
        "process_names": ["Taskmgr.exe", "taskmgr.exe"],
        "allow_launch": True,
        "allow_close": False,  # Security: protect task manager from shutdown
    },
    "explorer": {
        "canonical_name": "explorer",
        "display_name": "File Explorer",
        "executables": ["explorer.exe"],
        "aliases": ["explorer", "file explorer", "files", "windows explorer", "my computer"],
        "process_names": ["explorer.exe"],
        "allow_launch": True,
        "allow_close": False,  # Critical process: never allow close
    },
    "chrome": {
        "canonical_name": "chrome",
        "display_name": "Google Chrome",
        "executables": ["chrome.exe"],
        "aliases": ["chrome", "google chrome", "browser chrome"],
        "process_names": ["chrome.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
    "edge": {
        "canonical_name": "edge",
        "display_name": "Microsoft Edge",
        "executables": ["msedge.exe"],
        "aliases": ["edge", "msedge", "microsoft edge"],
        "process_names": ["msedge.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
    "firefox": {
        "canonical_name": "firefox",
        "display_name": "Mozilla Firefox",
        "executables": ["firefox.exe"],
        "aliases": ["firefox", "mozilla", "mozilla firefox"],
        "process_names": ["firefox.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
    "vscode": {
        "canonical_name": "vscode",
        "display_name": "Visual Studio Code",
        "executables": ["code.cmd", "code.exe"],
        "aliases": ["vscode", "code", "visual studio code", "vs code"],
        "process_names": ["Code.exe", "code.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
    "snippingtool": {
        "canonical_name": "snippingtool",
        "display_name": "Snipping Tool",
        "executables": ["snippingtool.exe"],
        "aliases": ["snipping tool", "snip", "screen snip", "snippingtool"],
        "process_names": ["SnippingTool.exe", "ScreenClippingHost.exe"],
        "allow_launch": True,
        "allow_close": True,
    },
}

# ==============================================================================
# 2. Critical Windows Process Protection Blacklist
# ==============================================================================

CRITICAL_PROCESSES: Set[str] = {
    "explorer.exe",
    "dwm.exe",
    "csrss.exe",
    "lsass.exe",
    "services.exe",
    "smss.exe",
    "wininit.exe",
    "winlogon.exe",
    "svchost.exe",
    "spoolsv.exe",
    "system",
    "registry",
    "idle",
    "taskhostw.exe",
    "sihost.exe",
    "fontdrvhost.exe",
    "runtimebroker.exe",
    "taskmgr.exe",
    "autohotkey64.exe",
    "autohotkey.exe",
    "python.exe",
    "python3.13.exe",
}


# ==============================================================================
# 3. Sanitization & Safe Resolution Helpers
# ==============================================================================

def sanitize_app_name(raw_name: str) -> str:
    """Sanitize and validate an application name provided by the user.

    Rejects directory traversals, absolute/relative paths, and shell metacharacters.
    """
    if not raw_name or not isinstance(raw_name, str):
        raise ToolValidationError("Application name must be a non-empty string.")

    trimmed = raw_name.strip()
    if not trimmed:
        raise ToolValidationError("Application name cannot be empty.")

    if len(trimmed) > 64:
        raise ToolValidationError("Application name exceeds maximum length of 64 characters.")

    # Strictly reject path separators and shell metacharacters
    forbidden = ["/", "\\", ";", "&", "|", "`", "$", "(", ")", "<", ">", '"', "'", "\n", "\r"]
    for char in forbidden:
        if char in trimmed:
            logger.warning("Rejected malicious app_name input: '%s'", trimmed)
            raise ToolValidationError(
                f"Security violation: Executable paths, directory traversals, and shell characters are not permitted. "
                f"Input '{trimmed}' was rejected."
            )

    normalized = " ".join(trimmed.lower().split())
    if normalized.endswith(".exe"):
        normalized = normalized[:-4].strip()
    return normalized


def resolve_application(raw_name: str) -> Dict[str, Any]:
    """Safely resolve an application name to an entry in the allow-list catalog."""
    normalized = sanitize_app_name(raw_name)

    # 1. Direct canonical name match
    if normalized in APPLICATION_CATALOG:
        return APPLICATION_CATALOG[normalized]

    # 2. Exact alias match
    for entry in APPLICATION_CATALOG.values():
        if normalized in entry["aliases"]:
            return entry

    # 3. Partial alias match (e.g. "google chrome browser" or "vs code editor")
    for entry in APPLICATION_CATALOG.values():
        for alias in entry["aliases"]:
            if alias in normalized or (len(normalized) >= 4 and normalized in alias):
                return entry

    supported = sorted(list({entry["display_name"] for entry in APPLICATION_CATALOG.values()}))
    logger.info("Application '%s' not found in allow-list catalog", raw_name)
    raise ToolValidationError(
        f"Application '{raw_name}' is not in the allow-list. "
        f"Supported applications: {', '.join(supported)}"
    )


def find_executable_path(entry: Dict[str, Any]) -> str:
    """Safely locate the executable on disk using allow-listed filenames."""
    # 1. Check system PATH via shutil.which
    for exe in entry["executables"]:
        found = shutil.which(exe)
        if found:
            return found

    # 2. Check standard Windows application install locations
    win_dir = os.environ.get("SystemRoot", r"C:\Windows")
    sys32 = os.path.join(win_dir, "System32")
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LocalAppData", "")

    search_dirs = [
        sys32,
        win_dir,
        os.path.join(prog_files, "Google", "Chrome", "Application"),
        os.path.join(prog_files_x86, "Google", "Chrome", "Application"),
        os.path.join(prog_files_x86, "Microsoft", "Edge", "Application"),
        os.path.join(prog_files, "Microsoft", "Edge", "Application"),
        os.path.join(local_app_data, "Programs", "Microsoft VS Code"),
        os.path.join(prog_files, "Microsoft VS Code"),
        os.path.join(prog_files, "Mozilla Firefox"),
        os.path.join(prog_files_x86, "Mozilla Firefox"),
    ]

    for exe in entry["executables"]:
        for d in search_dirs:
            if d and os.path.isdir(d):
                p = os.path.join(d, exe)
                if os.path.isfile(p):
                    return p

    # Fallback to the first allow-listed binary name
    return entry["executables"][0]


# ==============================================================================
# 4. Pydantic Parameter Models
# ==============================================================================

class OpenAppParams(BaseModel):
    """Parameters for opening an allow-listed application."""
    model_config = ConfigDict(extra="forbid")
    app_name: str = Field(..., min_length=1, max_length=64, description="Name or alias of the allow-listed application to open")


class IsAppRunningParams(BaseModel):
    """Parameters for checking application running status."""
    model_config = ConfigDict(extra="forbid")
    app_name: str = Field(..., min_length=1, max_length=64, description="Name or alias of the application to check")


class CloseAppParams(BaseModel):
    """Parameters for closing an application safely."""
    model_config = ConfigDict(extra="forbid")
    app_name: str = Field(..., min_length=1, max_length=64, description="Name or alias of the application to close")
    force: bool = Field(default=False, description="Whether to force termination if graceful close fails")
    confirmed: bool = Field(default=False, description="Mandatory confirmation flag required before terminating processes")


# ==============================================================================
# 5. Tool Implementations Registered in ToolRegistry
# ==============================================================================

@registry.register(
    name="open_app",
    description="Opens an allow-listed application by friendly name (e.g. notepad, calculator, chrome, edge, code).",
    param_model=OpenAppParams,
)
def open_app(app_name: str) -> Dict[str, Any]:
    """Launch an allow-listed application safely without shell execution."""
    entry = resolve_application(app_name)
    if not entry.get("allow_launch", True):
        raise ToolError(f"Launching '{entry['display_name']}' is prohibited by security policy.")

    exe_path = find_executable_path(entry)
    logger.info("Opening application '%s' using binary '%s'...", entry["display_name"], exe_path)

    try:
        proc = subprocess.Popen([exe_path], shell=False, close_fds=True)
        return {
            "app_name": entry["display_name"],
            "canonical_name": entry["canonical_name"],
            "launched": True,
            "pid": proc.pid,
            "executable": exe_path,
            "message": f"Successfully opened {entry['display_name']} (PID: {proc.pid}).",
        }
    except Exception as err:
        logger.error("Failed to launch application '%s': %s", entry["display_name"], err)
        raise ToolError(f"Failed to open '{entry['display_name']}': {err}")


@registry.register(
    name="is_app_running",
    description="Checks whether an application is currently running, returning instance count and PIDs.",
    param_model=IsAppRunningParams,
)
def is_app_running(app_name: str) -> Dict[str, Any]:
    """Inspect active processes to check if an allow-listed application is running."""
    entry = resolve_application(app_name)
    target_procs = {p.lower() for p in entry["process_names"]}

    instances: List[Dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "create_time", "memory_info"]):
        try:
            name = proc.info["name"]
            if name and name.lower() in target_procs:
                mem_mb = 0.0
                if proc.info["memory_info"]:
                    mem_mb = round(proc.info["memory_info"].rss / (1024 * 1024), 1)
                instances.append({
                    "pid": proc.info["pid"],
                    "name": name,
                    "memory_mb": mem_mb,
                    "created": proc.info["create_time"],
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    running = len(instances) > 0
    pids = [inst["pid"] for inst in instances]
    logger.info("Checked status for '%s': running=%s (%d instances)", entry["display_name"], running, len(instances))

    return {
        "app_name": entry["display_name"],
        "canonical_name": entry["canonical_name"],
        "is_running": running,
        "instance_count": len(instances),
        "instances": instances,
        "pids": pids,
        "message": (
            f"• {entry['display_name']} is currently running ({len(instances)} instance(s), PIDs: {pids})."
            if running else
            f"• {entry['display_name']} is not running."
        ),
    }


@registry.register(
    name="close_app",
    description="Safely closes a running application. Requires confirmed=True before terminating any processes.",
    param_model=CloseAppParams,
)
def close_app(app_name: str, force: bool = False, confirmed: bool = False) -> Dict[str, Any]:
    """Safely terminate application processes with mandatory confirmation and critical process protection."""
    entry = resolve_application(app_name)

    # 1. Critical Windows process protection
    if not entry.get("allow_close", True):
        logger.warning("Attempted close on protected application '%s'", entry["display_name"])
        raise ToolError(f"Security restriction: Closing '{entry['display_name']}' is prohibited as it is a core system component.")

    for p_name in entry["process_names"]:
        if p_name.lower() in CRITICAL_PROCESSES:
            logger.warning("Security alert: Attempted close on critical process '%s'", p_name)
            raise ToolError(f"Security violation: Process '{p_name}' is a protected Windows system process.")

    # 2. Discover running instances
    target_procs = {p.lower() for p in entry["process_names"]}
    current_pid = os.getpid()
    parent_pid = os.getppid()

    matching_procs: List[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info["name"]
            pid = proc.info["pid"]
            if pid in (current_pid, parent_pid):
                continue
            if name and name.lower() in target_procs:
                matching_procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not matching_procs:
        return {
            "app_name": entry["display_name"],
            "canonical_name": entry["canonical_name"],
            "closed": False,
            "instances_terminated": 0,
            "pids": [],
            "requires_confirmation": False,
            "message": f"{entry['display_name']} is not currently running.",
        }

    # 3. Mandatory User Confirmation Check
    if not confirmed:
        pids = [p.pid for p in matching_procs]
        logger.info(
            "Close requested for '%s' without confirmation. Prompting user (%d instances, PIDs: %s).",
            entry["display_name"],
            len(matching_procs),
            pids,
        )
        return {
            "app_name": entry["display_name"],
            "canonical_name": entry["canonical_name"],
            "closed": False,
            "requires_confirmation": True,
            "instances_found": len(matching_procs),
            "pids": pids,
            "confirmation_prompt": (
                f"Closing {entry['display_name']} will terminate {len(matching_procs)} running process(es) (PIDs: {pids}). "
                f"Please confirm to proceed."
            ),
            "message": (
                f"⚠️ **Confirmation Required:** Are you sure you want to close {entry['display_name']}? "
                f"({len(matching_procs)} running instance(s): PIDs {pids}). "
                f"Say 'confirm close {entry['canonical_name']}' to proceed."
            ),
        }

    # 4. User has confirmed: proceed with safe, graceful termination
    closed_count = 0
    terminated_pids = []
    for proc in matching_procs:
        try:
            pid = proc.pid
            proc.terminate()
            terminated_pids.append(pid)
            closed_count += 1
            logger.info("Sent terminate signal to '%s' (PID: %d)", entry["display_name"], pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as err:
            logger.warning("Could not terminate PID %d: %s", proc.pid, err)

    # Wait briefly for graceful exit
    gone, alive = psutil.wait_procs(matching_procs, timeout=1.5)
    if alive and force:
        for proc in alive:
            try:
                proc.kill()
                logger.warning("Force-killed stubborn process (PID: %d)", proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    return {
        "app_name": entry["display_name"],
        "canonical_name": entry["canonical_name"],
        "closed": True,
        "instances_terminated": closed_count,
        "pids": terminated_pids,
        "requires_confirmation": False,
        "message": f"✓ Successfully closed {entry['display_name']} ({closed_count} instance(s) terminated).",
    }

