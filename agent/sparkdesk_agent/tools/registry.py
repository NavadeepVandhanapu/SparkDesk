"""Centralized Tool Registry for SparkDesk Local Agent.

Allows registering strictly defined, allow-listed tools with Pydantic validation.
Arbitrary shell execution or dynamic code execution is prohibited by design.
"""

import asyncio
import inspect
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError

from sparkdesk_agent.core.logging import get_logger


class ToolError(Exception):
    """Base exception for tool execution errors."""
    pass


class ToolNotFoundError(ToolError):
    """Raised when an unlisted or unknown tool is invoked."""
    pass


class ToolValidationError(ToolError):
    """Raised when provided parameters fail schema validation."""
    pass


@dataclass
class RegisteredTool:
    """Represents an explicitly registered tool."""
    name: str
    description: str
    handler: Callable[..., Any]
    param_model: Optional[Type[BaseModel]] = None


class ToolRegistry:
    """Registry managing allowed agent tools and dispatching execution safely."""

    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}
        self._logger = get_logger("sparkdesk_agent.tools")

    def register(
        self,
        name: str,
        description: str,
        param_model: Optional[Type[BaseModel]] = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a tool with metadata and parameter schema."""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            if name in self._tools:
                self._logger.warning("Overwriting existing tool registration: %s", name)
            self._tools[name] = RegisteredTool(
                name=name,
                description=description,
                handler=func,
                param_model=param_model,
            )
            self._logger.debug("Registered tool: '%s' - %s", name, description)
            return func
        return decorator

    def has_tool(self, name: str) -> bool:
        """Check if a tool exists in the registry."""
        return name in self._tools

    def get_tool(self, name: str) -> Optional[RegisteredTool]:
        """Retrieve registered tool definition."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List metadata and schema for all registered tools."""
        tools = []
        for tool in self._tools.values():
            schema = tool.param_model.model_json_schema() if tool.param_model else None
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "parameters_schema": schema,
            })
        return tools

    async def execute(self, name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Safely execute a registered tool with parameter validation.

        Rejects unknown tools and parameter mismatches.
        """
        tool = self.get_tool(name)
        if tool is None:
            self._logger.warning("Tool execution rejected: Unknown tool '%s'", name)
            raise ToolNotFoundError(f"Unknown tool '{name}'. Available tools: {list(self._tools.keys())}")

        params = params or {}

        # Validate parameters against Pydantic model if defined
        validated_kwargs: Dict[str, Any] = {}
        if tool.param_model is not None:
            try:
                validated_model = tool.param_model(**params)
                validated_kwargs = validated_model.model_dump()
            except ValidationError as err:
                self._logger.warning("Tool '%s' parameter validation failed: %s", name, err)
                raise ToolValidationError(f"Invalid parameters for tool '{name}': {err}")
        else:
            if params:
                # Tool expects no parameters but arguments were supplied
                self._logger.warning("Tool '%s' received unexpected parameters: %s", name, list(params.keys()))
                raise ToolValidationError(f"Tool '{name}' takes no parameters, but received: {list(params.keys())}")

        start_time = time.monotonic()
        self._logger.info("Executing tool: '%s'...", name)

        try:
            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(**validated_kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, lambda: tool.handler(**validated_kwargs))

            duration = round(time.monotonic() - start_time, 3)
            self._logger.info("Tool '%s' completed successfully in %0.3fs.", name, duration)
            return result
        except Exception as err:
            duration = round(time.monotonic() - start_time, 3)
            self._logger.error("Tool '%s' failed after %0.3fs: %s", name, duration, err)
            raise err


# Global registry singleton
registry = ToolRegistry()
