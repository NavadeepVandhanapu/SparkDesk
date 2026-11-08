"""Intelligence Execution Pipeline for SparkDesk Local Agent.

Orchestrates the entire request lifecycle:
  Context Retrieval -> Intent Understanding -> Task Planning ->
  Plan Validation -> Tool Execution -> Response Formatting -> Context Update.

Ensures strict separation of concerns and guarantees that no execution occurs
without schema validation and ToolRegistry allow-listing.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sparkdesk_agent.core.logging import get_logger
from sparkdesk_agent.intelligence.context import ContextManager, ConversationContext, context_manager as default_context_manager
from sparkdesk_agent.intelligence.planner import ExecutionPlan, PlanStatus, TaskPlanner, task_planner as default_task_planner
from sparkdesk_agent.intelligence.provider import BaseIntelligenceProvider, get_provider
from sparkdesk_agent.intelligence.validator import PlanValidationError, PlanValidator, plan_validator as default_plan_validator
from sparkdesk_agent.intent.models import CommandRequest, CommandResponse, IntentResult, IntentStatus
from sparkdesk_agent.tools.registry import ToolRegistry, registry as default_registry


class IntelligencePipeline:
    """Central orchestrator for natural-language understanding, planning, validation, and tool execution."""

    def __init__(
        self,
        provider: Optional[BaseIntelligenceProvider] = None,
        planner: Optional[TaskPlanner] = None,
        validator: Optional[PlanValidator] = None,
        tool_registry: Optional[ToolRegistry] = None,
        context_mgr: Optional[ContextManager] = None,
    ) -> None:
        if provider is None:
            try:
                from sparkdesk_agent.core.config import get_settings
                provider = get_provider(get_settings().intelligence_provider)
            except Exception:
                provider = get_provider("rule_based")
        self.provider = provider
        self.planner = planner or default_task_planner
        self.validator = validator or default_plan_validator
        self.registry = tool_registry or default_registry
        self.context_manager = context_mgr or default_context_manager
        self._logger = get_logger("sparkdesk_agent.intelligence.pipeline")

    async def classify(
        self,
        prompt: str,
        session_id: Optional[str] = None,
    ) -> IntentResult:
        """Classify a prompt within the conversational context of a session."""
        context = self.context_manager.get_or_create(session_id)
        self._logger.info("Classifying prompt for session '%s': '%s'", context.session_id, prompt[:60])
        return await self.provider.understand(prompt, context)

    async def process(self, request: CommandRequest) -> CommandResponse:
        """Process a natural-language user command through the full intelligence pipeline."""
        now_ts = datetime.now(timezone.utc).isoformat()
        context = self.context_manager.get_or_create(request.session_id)

        self._logger.info(
            "Processing command in session '%s' using provider '%s': '%s'",
            context.session_id,
            self.provider.name,
            request.prompt[:60],
        )

        # 1. Intent Understanding
        intent = await self.provider.understand(request.prompt, context)

        # 2. Handle non-executable outcomes (Ambiguous or Unsupported)
        if intent.status != IntentStatus.RECOGNIZED:
            self._logger.info("Command outcome '%s' for prompt '%s'", intent.status.value, request.prompt[:60])
            msg = intent.message or f"Request was marked as {intent.status.value}."

            # Record turn in context
            context.add_turn(
                user_prompt=request.prompt,
                response_message=msg,
                intent=intent.intent,
                tool=None,
                focus=intent.focus,
                tool_result=None,
            )

            return CommandResponse(
                success=False,
                status=intent.status.value,
                intent=intent.intent,
                tool=None,
                message=msg,
                tool_result=None,
                timestamp=now_ts,
                session_id=context.session_id,
                plan_id=None,
            )

        # 3. Task Planning
        plan = self.planner.create_plan(intent, context)

        # 4. Plan Validation against ToolRegistry
        try:
            self.validator.validate(plan)
        except PlanValidationError as err:
            self._logger.error("Plan validation rejected: %s", err)
            error_msg = f"Security validation rejected execution plan: {err}"
            context.add_turn(
                user_prompt=request.prompt,
                response_message=error_msg,
                intent=intent.intent,
                tool=intent.tool,
                focus=intent.focus,
                tool_result=None,
            )
            return CommandResponse(
                success=False,
                status="validation_error",
                intent=intent.intent,
                tool=intent.tool,
                message=error_msg,
                tool_result=None,
                timestamp=now_ts,
                session_id=context.session_id,
                plan_id=plan.plan_id,
            )

        # 5. Plan Execution through secure ToolRegistry
        plan.status = PlanStatus.EXECUTING
        last_tool_result: Any = None
        executed_tool: Optional[str] = None

        try:
            for step in plan.steps:
                self._logger.info(
                    "Executing plan step %d/%d: tool '%s'",
                    step.step_id,
                    len(plan.steps),
                    step.tool,
                )
                last_tool_result = await self.registry.execute(step.tool, step.parameters)
                executed_tool = step.tool

            plan.status = PlanStatus.COMPLETED
        except Exception as err:
            plan.status = PlanStatus.FAILED
            plan.error = str(err)
            self._logger.error("Execution error on plan '%s': %s", plan.plan_id, err)
            error_msg = f"Error executing tool '{executed_tool or intent.tool}': {err}"
            context.add_turn(
                user_prompt=request.prompt,
                response_message=error_msg,
                intent=intent.intent,
                tool=executed_tool or intent.tool,
                focus=intent.focus,
                tool_result=None,
            )
            return CommandResponse(
                success=False,
                status="execution_error",
                intent=intent.intent,
                tool=executed_tool or intent.tool,
                message=error_msg,
                tool_result=None,
                timestamp=now_ts,
                session_id=context.session_id,
                plan_id=plan.plan_id,
            )

        # 6. Response Formatting via Provider
        formatted_message = await self.provider.format_response(intent, last_tool_result, context)

        # 7. Update Context Turn
        context.add_turn(
            user_prompt=request.prompt,
            response_message=formatted_message,
            intent=intent.intent,
            tool=executed_tool,
            focus=intent.focus,
            tool_result=last_tool_result if isinstance(last_tool_result, dict) else None,
        )

        return CommandResponse(
            success=True,
            status=intent.status.value,
            intent=intent.intent,
            tool=executed_tool,
            message=formatted_message,
            tool_result=last_tool_result,
            timestamp=now_ts,
            session_id=context.session_id,
            plan_id=plan.plan_id,
        )


# Global pipeline instance
pipeline = IntelligencePipeline()
