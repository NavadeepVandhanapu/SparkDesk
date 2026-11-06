"""System information collection tool for SparkDesk Local Agent."""

from datetime import datetime, timezone
import os
import platform
import shutil
import time
from typing import Any, Dict

import psutil

from sparkdesk_agent.tools.registry import registry


def format_uptime(seconds: int) -> str:
    """Format total seconds into a readable string (e.g., '1d 4h 12m 30s')."""
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


@registry.register(
    name="get_system_info",
    description="Collects Windows OS version, CPU details, RAM availability, Disk usage, and Uptime.",
    param_model=None,  # No input parameters required
)
def get_system_info() -> Dict[str, Any]:
    """Gather comprehensive Windows system metrics."""
    # 1. Operating System
    os_info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "machine": platform.machine(),
    }

    # 2. CPU Metrics
    cpu_usage = psutil.cpu_percent(interval=0.1)
    cpu_info = {
        "processor": platform.processor() or "Unknown",
        "logical_cores": os.cpu_count() or 1,
        "physical_cores": psutil.cpu_count(logical=False) or 1,
        "usage_percent": cpu_usage,
    }

    # 3. RAM Metrics
    vm = psutil.virtual_memory()
    memory_info = {
        "total_gb": round(vm.total / (1024**3), 2),
        "available_gb": round(vm.available / (1024**3), 2),
        "used_gb": round(vm.used / (1024**3), 2),
        "usage_percent": vm.percent,
    }

    # 4. Primary System Disk (C:\)
    root_drive = os.environ.get("SystemDrive", "C:") + "\\"
    try:
        du = psutil.disk_usage(root_drive)
        disk_info = {
            "drive": root_drive,
            "total_gb": round(du.total / (1024**3), 2),
            "free_gb": round(du.free / (1024**3), 2),
            "used_gb": round(du.used / (1024**3), 2),
            "usage_percent": du.percent,
        }
    except Exception:
        total, used, free = shutil.disk_usage(root_drive)
        disk_info = {
            "drive": root_drive,
            "total_gb": round(total / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "usage_percent": round((used / total) * 100, 1),
        }

    # 5. System Uptime
    boot_timestamp = psutil.boot_time()
    uptime_sec = int(time.time() - boot_timestamp)
    uptime_info = {
        "uptime_seconds": uptime_sec,
        "uptime_formatted": format_uptime(uptime_sec),
        "boot_time": datetime.fromtimestamp(boot_timestamp, timezone.utc).isoformat(),
    }

    return {
        "os": os_info,
        "cpu": cpu_info,
        "memory": memory_info,
        "disk": disk_info,
        "uptime": uptime_info,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
