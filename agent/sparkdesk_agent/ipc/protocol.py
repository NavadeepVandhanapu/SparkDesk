"""Data models and schemas for SparkDesk Local Agent IPC."""

from datetime import datetime, timezone
import platform
import os
from typing import Any, Dict, List, Optional
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


class ExecuteRequest(BaseModel):
    """Authenticated tool execution request payload."""

    tool: str = Field(..., description="Name of the registered tool to invoke")
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Dictionary of parameters matching the tool schema",
    )


class ExecuteResponse(BaseModel):
    """Standardized tool execution response."""

    success: bool = Field(..., description="Whether the tool executed successfully")
    tool: str = Field(..., description="Invoked tool name")
    result: Optional[Any] = Field(default=None, description="Output payload from tool")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of execution completion",
    )


class ToolMetadata(BaseModel):
    """Metadata for an allow-listed tool."""

    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Description of tool behavior")
    parameters_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON schema of accepted parameters",
    )
