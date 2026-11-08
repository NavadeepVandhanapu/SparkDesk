"""Model-Independent Intelligence Provider Interface for SparkDesk.

Defines the core abstraction for natural language understanding and response formatting.
Decouples intent classification and response generation from specific AI backends,
enabling seamless swapping between rule-based engines and local LLMs (e.g., Ollama).
"""

from abc import ABC, abstractmethod
import re
from typing import Any, Dict, Optional, Type

from sparkdesk_agent.core.logging import get_logger
from sparkdesk_agent.intelligence.context import ConversationContext
from sparkdesk_agent.intent.engine import IntentEngine, intent_engine
from sparkdesk_agent.intent.models import IntentResult, IntentStatus


class BaseIntelligenceProvider(ABC):
    """Abstract interface defining required capabilities for any intelligence provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique provider name (e.g. 'rule_based', 'ollama', 'mock')."""
        pass

    @abstractmethod
    async def understand(
        self,
        prompt: str,
        context: Optional[ConversationContext] = None,
    ) -> IntentResult:
        """Analyze a natural-language prompt within optional conversation context.

        Returns an IntentResult specifying status (recognized, ambiguous, unsupported),
        identified intent, target tool, parameters, confidence score, and metric focus.
        """
        pass

    @abstractmethod
    async def format_response(
        self,
        intent: IntentResult,
        tool_result: Any,
        context: Optional[ConversationContext] = None,
    ) -> str:
        """Format raw tool execution results into a human-readable message."""
        pass


class RuleBasedIntelligenceProvider(BaseIntelligenceProvider):
    """Rule-based intelligence provider wrapping the Phase 5 IntentEngine.

    Serves as the default high-performance provider with zero model dependencies,
    augmented with conversational context support for follow-up queries.
    """

    def __init__(self, engine: Optional[IntentEngine] = None) -> None:
        self._engine = engine or intent_engine
        self._logger = get_logger("sparkdesk_agent.intelligence.provider.rule_based")

        # Conversational follow-up patterns (e.g. "what about CPU?", "and the RAM?", "how about uptime?")
        self._followup_patterns = [
            r"^(what|how)\s+about\s+(the\s+)?(?P<topic>cpu|processor|ram|memory|disk|storage|uptime|boot\s*time|specs)\b",
            r"^and\s+(the\s+)?(?P<topic>cpu|processor|ram|memory|disk|storage|uptime|boot\s*time|specs)\b",
            r"^(check|show|tell\s+me)\s+(again|more)\b",
            r"^(refresh|update|reload)\b",
        ]

    @property
    def name(self) -> str:
        return "rule_based"

    def _resolve_contextual_followup(
        self,
        prompt: str,
        context: Optional[ConversationContext],
    ) -> Optional[IntentResult]:
        """Attempt to resolve follow-up queries leveraging prior conversation state."""
        if not context or not context.last_turn():
            return None

        cleaned = prompt.strip().lower()

        # Check for contextual confirmation to close an application
        if context.last_tool() == "close_app" and context.last_focus():
            app_target = context.last_focus()
            # If the user explicitly specifies an action with an application target (e.g. "confirm close explorer"),
            # do not hijack it as a contextual confirmation for the prior app!
            if not re.search(r"\b(close|kill|exit|terminate|stop)\s+[a-zA-Z0-9_\-]+", cleaned):
                if re.match(r"^(yes|confirm|proceed|do\s+it|sure|close\s+it)(?:\s+(?:please|it))?$", cleaned):
                    self._logger.info("Contextual confirmation received: closing '%s'", app_target)
                    return IntentResult(
                        status=IntentStatus.RECOGNIZED,
                        intent="close_app",
                        tool="close_app",
                        parameters={"app_name": app_target, "force": False, "confirmed": True},
                        confidence=0.99,
                        focus=app_target,
                    )
                if re.match(r"^(no|cancel|abort|don't(?:\s+do\s+it)?|stop|nevermind|no\s+thanks)$", cleaned):
                    self._logger.info("Contextual cancellation received: close aborted for '%s'", app_target)
                    return IntentResult(
                        status=IntentStatus.UNSUPPORTED,
                        confidence=0.99,
                        message=f"Cancelled close request for {app_target}.",
                    )

        # Check for repetition / refresh commands: "refresh", "check again", etc.
        if re.search(r"\b(refresh|check\s+again|update|reload)\b", cleaned):
            last_tool = context.last_tool()
            last_focus = context.last_focus() or "all"
            if last_tool:
                self._logger.info("Contextual follow-up: repeating last tool '%s' (focus: %s)", last_tool, last_focus)
                return IntentResult(
                    status=IntentStatus.RECOGNIZED,
                    intent=last_tool,
                    tool=last_tool,
                    parameters={},
                    confidence=0.90,
                    focus=last_focus,
                )

        # Check for topic switch follow-ups: "what about cpu?", "and disk?"
        for pattern in self._followup_patterns:
            match = re.search(pattern, cleaned)
            if match:
                group_dict = match.groupdict()
                topic = group_dict.get("topic", "").strip()
                if not topic:
                    continue

                focus_map = {
                    "cpu": "cpu",
                    "processor": "cpu",
                    "ram": "memory",
                    "memory": "memory",
                    "disk": "disk",
                    "storage": "disk",
                    "uptime": "uptime",
                    "boot time": "uptime",
                    "specs": "all",
                }
                focus = focus_map.get(topic, "all")
                last_tool = context.last_tool() or "get_system_info"

                self._logger.info(
                    "Contextual follow-up resolved: topic '%s' -> focus '%s' for tool '%s'",
                    topic,
                    focus,
                    last_tool,
                )
                return IntentResult(
                    status=IntentStatus.RECOGNIZED,
                    intent=last_tool,
                    tool=last_tool,
                    parameters={},
                    confidence=0.92,
                    focus=focus,
                )

        return None

    async def understand(
        self,
        prompt: str,
        context: Optional[ConversationContext] = None,
    ) -> IntentResult:
        """Classify prompt, checking contextual follow-up rules before standard classification."""
        # 1. Check if this is a follow-up referencing active context
        contextual_match = self._resolve_contextual_followup(prompt, context)
        if contextual_match is not None:
            return contextual_match

        # 2. Standard classification via IntentEngine
        return self._engine.classify(prompt)

    async def format_response(
        self,
        intent: IntentResult,
        tool_result: Any,
        context: Optional[ConversationContext] = None,
    ) -> str:
        """Format tool result using the underlying engine."""
        return self._engine.format_response(intent, tool_result)


# Provider Registry
_PROVIDERS: Dict[str, BaseIntelligenceProvider] = {
    "rule_based": RuleBasedIntelligenceProvider(),
}
_DEFAULT_PROVIDER: str = "rule_based"


def register_provider(name: str, provider: BaseIntelligenceProvider) -> None:
    """Register a new intelligence provider instance."""
    _PROVIDERS[name] = provider


def get_provider(name: Optional[str] = None) -> BaseIntelligenceProvider:
    """Retrieve an intelligence provider by name, defaulting to rule_based."""
    key = name or _DEFAULT_PROVIDER
    if key not in _PROVIDERS:
        raise ValueError(f"Unknown intelligence provider: '{key}'. Registered: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[key]

