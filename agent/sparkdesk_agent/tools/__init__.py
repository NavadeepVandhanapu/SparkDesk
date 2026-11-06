"""Tools module for SparkDesk Local Agent."""

from sparkdesk_agent.tools.registry import (
    ToolError,
    ToolNotFoundError,
    ToolRegistry,
    ToolValidationError,
    registry,
)
# Ensure built-in tools are registered upon module import
import sparkdesk_agent.tools.system_info

__all__ = [
    "registry",
    "ToolRegistry",
    "ToolError",
    "ToolNotFoundError",
    "ToolValidationError",
]
