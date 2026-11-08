"""Plan Validator for SparkDesk Local Agent.

Enforces strict security boundaries before any task execution plan is executed.
Ensures that:
1. Every planned tool is explicitly registered in the secure ToolRegistry.
2. Parameters conform strictly to the tool's registered Pydantic schema.
3. No arbitrary shell commands, code execution payloads, or path traversal vectors exist.
4. The intelligence layer CANNOT bypass the ToolRegistry.
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import ValidationError

from sparkdesk_agent.core.logging import get_logger
from sparkdesk_agent.intelligence.planner import ExecutionPlan, PlanStatus, PlanStep
from sparkdesk_agent.tools.registry import ToolRegistry, registry as default_registry


class PlanValidationError(Exception):
    """Raised when an execution plan violates security constraints or schema rules."""
    pass


class PlanValidator:
    """Validates execution plans against the secure ToolRegistry and security policies."""

    # Shell and dynamic code execution patterns strictly prohibited in any parameter
    FORBIDDEN_PATTERNS = [
        r";\s*(rm|del|format|shutdown|curl|wget|powershell|cmd|bash|sh)\b",
        r"(&&|\|\|)\s*(rm|del|powershell|cmd|bash|sh)\b",
        r"\b(exec|eval|__import__|compile|globals|locals)\s*\(",
        r"\b(subprocess|os\.system|os\.popen|os\.exec)\b",
        r"(`|\$\()",  # Shell command substitution
    ]

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        max_steps: int = 5,
    ) -> None:
        self._registry = tool_registry or default_registry
        self._max_steps = max_steps
        self._logger = get_logger("sparkdesk_agent.intelligence.validator")

    def _inspect_value_for_injection(self, key: str, value: Any) -> None:
        """Recursively scan parameter values for dangerous execution payloads."""
        if isinstance(value, str):
            for pat in self.FORBIDDEN_PATTERNS:
                if re.search(pat, value, re.IGNORECASE):
                    self._logger.warning(
                        "Security alert: blocked dangerous parameter payload in '%s': %s",
                        key,
                        value[:50],
                    )
                    raise PlanValidationError(
                        f"Security violation: Parameter '{key}' contains forbidden code execution patterns."
                    )
        elif isinstance(value, dict):
            for k, v in value.items():
                self._inspect_value_for_injection(f"{key}.{k}", v)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                self._inspect_value_for_injection(f"{key}[{i}]", v)

    def validate(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Thoroughly validate every step of an ExecutionPlan.

        Raises:
            PlanValidationError: If any tool is unregistered, parameters invalid,
            or execution limits violated.
        """
        self._logger.debug("Validating ExecutionPlan '%s'...", plan.plan_id)

        # 1. State check
        if plan.status == PlanStatus.REJECTED:
            raise PlanValidationError(f"Cannot validate rejected plan: {plan.rationale}")

        if not plan.steps:
            raise PlanValidationError("Execution plan has no steps to execute.")

        # 2. Limit check
        if len(plan.steps) > self._max_steps:
            raise PlanValidationError(
                f"Plan step limit exceeded: {len(plan.steps)} steps provided, maximum allowed is {self._max_steps}."
            )

        # 3. Validate each step against the ToolRegistry
        for step in plan.steps:
            # 3a. Tool Allow-list enforcement
            if not self._registry.has_tool(step.tool):
                self._logger.warning("Rejected unlisted tool in plan: '%s'", step.tool)
                raise PlanValidationError(
                    f"Tool '{step.tool}' is not registered in ToolRegistry. Available tools: "
                    f"{[t['name'] for t in self._registry.list_tools()]}"
                )

            tool_def = self._registry.get_tool(step.tool)
            if tool_def is None:
                raise PlanValidationError(f"Tool definition for '{step.tool}' could not be resolved.")

            # 3b. Scan parameters for shell/code injection
            for param_key, param_val in step.parameters.items():
                self._inspect_value_for_injection(param_key, param_val)

            # 3c. Validate parameters against tool Pydantic schema
            if tool_def.param_model is not None:
                try:
                    # Instantiate model to verify parameter types and constraints
                    tool_def.param_model(**step.parameters)
                except ValidationError as err:
                    self._logger.warning(
                        "Parameter validation failed for tool '%s': %s",
                        step.tool,
                        err,
                    )
                    raise PlanValidationError(
                        f"Invalid parameters for tool '{step.tool}': {err}"
                    )
            else:
                if step.parameters:
                    raise PlanValidationError(
                        f"Tool '{step.tool}' accepts no parameters, but received: {list(step.parameters.keys())}"
                    )

        # 4. Mark plan as validated
        plan.status = PlanStatus.VALIDATED
        self._logger.info("ExecutionPlan '%s' successfully validated.", plan.plan_id)
        return plan


# Global plan validator singleton
plan_validator = PlanValidator()

