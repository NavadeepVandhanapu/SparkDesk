"""Data models and schemas for SparkDesk Local Agent IPC."""

from datetime import datetime, timezone
import platform
import os
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check status response."""

    status: str = Field(default="ok", description="Server operational status")
    agent_name: str = Field(..., description="Name of the agent")
    version: str = Field(..., description="Agent software version")
    python_version: str = Field(
        default_factory=platform.python_version,
        description="Active Python interpreter version",
    )
    uptime_seconds: float = Field(..., description="Total uptime in seconds")
    pid: int = Field(default_factory=os.getpid, description="Process ID of the agent")
    environment: str = Field(..., description="Runtime environment")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of the health check",
    )
