"""Intent understanding engine for SparkDesk Local Agent.

Classifies natural-language user queries into registered tool invocations,
detects ambiguous and unsupported requests safely, and formats human-readable responses.
Designed with a modular architecture so future local AI/LLM models can be plugged in.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sparkdesk_agent.core.logging import get_logger
from sparkdesk_agent.intent.models import IntentResult, IntentStatus


class IntentEngine:
    """Natural Language Intent Classifier and Response Formatter."""

    def __init__(self) -> None:
        self._logger = get_logger("sparkdesk_agent.intent")

        # Keywords and patterns for system information variations
        self._memory_patterns = [
            r"\b(ram|memory)\b",
            r"\b(free|available|used)\s+(ram|memory)\b",
            r"\bhow\s+much\s+(ram|memory)\b",
        ]

        self._cpu_patterns = [
            r"\b(cpu|processor)\b",
            r"\b(cpu|processor)\s+(usage|load|utilization|status|info)\b",
            r"\bhow\s+is\s+my\s+(cpu|processor)\b",
        ]

        self._disk_patterns = [
            r"\b(disk|storage|hard\s*drive|drive\s*space|c\s*drive|c:)\b",
            r"\bhow\s+much\s+(storage|disk|space)\b",
            r"\b(free|used|available)\s+(disk|storage|space)\b",
        ]

        self._uptime_patterns = [
            r"\buptime\b",
            r"\bboot\s*time\b",
            r"\bhow\s+long\s+(has\s+)?(my|this|the)?\s*(pc|computer|system|machine)?\s*(been\s+)?(running|on|up)\b",
            r"\bwhen\s+did\s+(my|this|the)?\s*(pc|computer|system|machine)?\s*(start|boot)\b",
        ]

        self._broad_system_patterns = [
            r"\bsystem\s+(info|information|specs|details|status|diagnostic|health|overview)\b",
            r"\b(pc|computer|machine|device|hardware)\s+(specs|specifications|info|details|status|health)\b",
            r"\b(my\s+specs|show\s+specs|check\s+specs|system\s+specs)\b",
            r"\btell\s+me\s+(about\s+my\s+pc|my\s+specs|my\s+system)\b",
            r"\bwhat\s+(is|are)\s+my\s+(specs|system\s+info|hardware)\b",
        ]

        # Ambiguous tokens (too vague on their own)
        self._ambiguous_words = {
            "info", "check", "system", "status", "show", "what", "details",
            "stats", "specs", "diagnostics", "hardware", "device", "pc",
        }

        # Clear out-of-scope triggers for unsupported classification
        self._unsupported_triggers = [
            "weather", "music", "song", "video", "play", "order", "pizza", "food",
            "search", "google", "browse", "email", "mail", "calculate",
            "joke", "poem", "story", "who are you", "what is your name",
            "delete", "remove file", "format drive", "download",
        ]

        # Application control regex patterns
        self._close_confirmed_pattern = re.compile(
            r"^(?:confirm|yes|force)\s+(?:close|kill|exit|terminate|stop)\s+(?:the\s+)?(?:app|application|program)?\s*(?P<app>[a-zA-Z0-9_\- ]+)$",
            re.IGNORECASE,
        )
        self._close_app_pattern = re.compile(
            r"^(?:close|kill|exit|terminate|stop)\s+(?:the\s+)?(?:app|application|program)?\s*(?P<app>[a-zA-Z0-9_\- ]+)$",
            re.IGNORECASE,
        )
        self._open_app_pattern = re.compile(
            r"^(?:open|launch|start|run)\s+(?:the\s+)?(?:app|application|program)?\s*(?P<app>[a-zA-Z0-9_\- ]+)$",
            re.IGNORECASE,
        )
        self._is_running_pattern = re.compile(
            r"^(?:is|check\s+if)\s+(?:the\s+)?(?P<app1>[a-zA-Z0-9_\- ]+?)\s*(?:is\s+)?(?:running|open|active|alive)\??$|"
            r"^(?:status\s+of|process\s+status\s+of|check\s+process|check\s+app)\s+(?:the\s+)?(?:app|application|program)?\s*(?P<app2>[a-zA-Z0-9_\- ]+)$",
            re.IGNORECASE,
        )

    def _clean_text(self, text: str) -> str:
        """Normalize input text: lowercase, collapse whitespace, strip punctuation."""
        lowered = text.lower().strip()
        # Remove common punctuation while preserving colons in drive letters (C:)
        cleaned = re.sub(r"[?!.,;\"'()\[\]{}]", " ", lowered)
        return " ".join(cleaned.split())

    def _match_app_control(self, cleaned: str) -> Optional[IntentResult]:
        """Attempt to classify prompt as an application control action."""
        try:
            from sparkdesk_agent.tools.app_control import resolve_application, ToolValidationError
        except ImportError:
            return None

        # 1. Close application with explicit confirmation (e.g. "confirm close notepad", "force close chrome")
        match = self._close_confirmed_pattern.match(cleaned)
        if match:
            app_raw = match.group("app").strip()
            force = "force" in cleaned
            try:
                entry = resolve_application(app_raw)
                return IntentResult(
                    status=IntentStatus.RECOGNIZED,
                    intent="close_app",
                    tool="close_app",
                    parameters={"app_name": entry["canonical_name"], "force": force, "confirmed": True},
                    confidence=0.98,
                    focus=entry["canonical_name"],
                )
            except ToolValidationError as err:
                return IntentResult(
                    status=IntentStatus.UNSUPPORTED,
                    confidence=0.1,
                    message=str(err),
                )

        # 2. Standard close application (unconfirmed by default)
        match = self._close_app_pattern.match(cleaned)
        if match:
            app_raw = match.group("app").strip()
            try:
                entry = resolve_application(app_raw)
                return IntentResult(
                    status=IntentStatus.RECOGNIZED,
                    intent="close_app",
                    tool="close_app",
                    parameters={"app_name": entry["canonical_name"], "force": False, "confirmed": False},
                    confidence=0.95,
                    focus=entry["canonical_name"],
                )
            except ToolValidationError as err:
                return IntentResult(
                    status=IntentStatus.UNSUPPORTED,
                    confidence=0.1,
                    message=str(err),
                )

        # 3. Check if application is running
        match = self._is_running_pattern.match(cleaned)
        if match:
            app_raw = (match.group("app1") or match.group("app2") or "").strip()
            if app_raw:
                try:
                    entry = resolve_application(app_raw)
                    return IntentResult(
                        status=IntentStatus.RECOGNIZED,
                        intent="is_app_running",
                        tool="is_app_running",
                        parameters={"app_name": entry["canonical_name"]},
                        confidence=0.95,
                        focus=entry["canonical_name"],
                    )
                except ToolValidationError as err:
                    # If user asked "status of cpu" or "check system", let it fall through
                    if not any(token in app_raw for token in ("cpu", "ram", "memory", "disk", "uptime", "system", "pc")):
                        return IntentResult(
                            status=IntentStatus.UNSUPPORTED,
                            confidence=0.1,
                            message=str(err),
                        )

        # 4. Open application
        match = self._open_app_pattern.match(cleaned)
        if match:
            app_raw = match.group("app").strip()
            try:
                entry = resolve_application(app_raw)
                return IntentResult(
                    status=IntentStatus.RECOGNIZED,
                    intent="open_app",
                    tool="open_app",
                    parameters={"app_name": entry["canonical_name"]},
                    confidence=0.95,
                    focus=entry["canonical_name"],
                )
            except ToolValidationError as err:
                # If user asked "open system specs", fall through to system info patterns
                if not any(token in app_raw for token in ("system", "specs", "hardware", "diagnostic", "details")):
                    return IntentResult(
                        status=IntentStatus.UNSUPPORTED,
                        confidence=0.1,
                        message=str(err),
                    )

        return None

    def classify(self, raw_prompt: str) -> IntentResult:
        """Classify a natural language prompt into an IntentResult."""
        cleaned = self._clean_text(raw_prompt)

        if not cleaned:
            return IntentResult(
                status=IntentStatus.AMBIGUOUS,
                message="Please type a command or request.",
                confidence=0.0,
            )

        self._logger.debug("Classifying prompt: '%s'", cleaned)
        tokens = cleaned.split()

        # 1. Check for clearly unsupported queries
        for trigger in self._unsupported_triggers:
            if re.search(r"\b" + re.escape(trigger) + r"\b", cleaned):
                self._logger.info("Classified as unsupported (matched trigger '%s'): '%s'", trigger, cleaned)
                return IntentResult(
                    status=IntentStatus.UNSUPPORTED,
                    confidence=0.1,
                    message=(
                        f"I cannot process '{raw_prompt.strip()}' yet. "
                        "Currently supported capabilities:\n"
                        "• System specifications ('show system info', 'what are my specs')\n"
                        "• RAM & Memory metrics ('how much ram is free', 'check memory')\n"
                        "• CPU utilization ('cpu usage', 'processor load')\n"
                        "• Disk storage space ('how much disk space is left')\n"
                        "• System uptime ('how long has my pc been running')"
                    ),
                )

        # 2. Check for ambiguous single-word or vague queries
        if len(tokens) == 1 and tokens[0] in self._ambiguous_words:
            self._logger.info("Classified as ambiguous (single vague token '%s')", tokens[0])
            return IntentResult(
                status=IntentStatus.AMBIGUOUS,
                confidence=0.4,
                message=(
                    f"Your request '{raw_prompt.strip()}' is ambiguous. Did you mean:\n"
                    "• 'show system info' (complete system overview)\n"
                    "• 'check ram' (memory availability)\n"
                    "• 'cpu usage' (processor load)\n"
                    "• 'disk space' (storage capacity)\n"
                    "• 'uptime' (how long the PC has been on)?"
                ),
            )

        # 3. Check for Application Control actions (open, check running, close)
        app_result = self._match_app_control(cleaned)
        if app_result is not None:
            return app_result

        # 3. Check for specific metric patterns
        focus = "all"
        is_matched = False
        confidence = 0.0

        # Memory match
        for pat in self._memory_patterns:
            if re.search(pat, cleaned):
                focus = "memory"
                is_matched = True
                confidence = 0.95
                break

        # CPU match
        if not is_matched:
            for pat in self._cpu_patterns:
                if re.search(pat, cleaned):
                    focus = "cpu"
                    is_matched = True
                    confidence = 0.95
                    break

        # Disk match
        if not is_matched:
            for pat in self._disk_patterns:
                if re.search(pat, cleaned):
                    focus = "disk"
                    is_matched = True
                    confidence = 0.95
                    break

        # Uptime match
        if not is_matched:
            for pat in self._uptime_patterns:
                if re.search(pat, cleaned):
                    focus = "uptime"
                    is_matched = True
                    confidence = 0.95
                    break

        # Broad system info match
        if not is_matched:
            for pat in self._broad_system_patterns:
                if re.search(pat, cleaned):
                    focus = "all"
                    is_matched = True
                    confidence = 0.95
                    break

        # Check combination of general keywords (e.g., "specs", "system details")
        if not is_matched:
            system_keywords = {"system", "specs", "hardware", "computer", "pc", "specifications", "diagnostic"}
            overlap = set(tokens).intersection(system_keywords)
            if overlap:
                focus = "all"
                is_matched = True
                confidence = 0.85

        if is_matched:
            self._logger.info("Recognized intent 'get_system_info' (focus: %s, confidence: %0.2f)", focus, confidence)
            return IntentResult(
                status=IntentStatus.RECOGNIZED,
                intent="get_system_info",
                tool="get_system_info",
                parameters={},
                confidence=confidence,
                focus=focus,
            )

        # 4. Fallback: Query not recognized as any supported intent
        self._logger.info("Prompt not recognized: '%s'", cleaned)
        return IntentResult(
            status=IntentStatus.UNSUPPORTED,
            confidence=0.0,
            message=(
                f"I don't understand '{raw_prompt.strip()}'.\n"
                "Try asking:\n"
                "• 'Show system specs'\n"
                "• 'How much RAM is free?'\n"
                "• 'What is my CPU usage?'\n"
                "• 'How much disk space is left?'\n"
                "• 'What is the system uptime?'"
            ),
        )

    def format_response(self, intent: IntentResult, tool_result: Dict[str, Any]) -> str:
        """Format raw tool execution output into a clear, human-readable response."""
        if not tool_result:
            return "Unable to complete request at this time."

        # Application control tools provide structured human-readable messages
        if intent.tool in ("open_app", "is_app_running", "close_app"):
            if isinstance(tool_result, dict) and "message" in tool_result:
                return tool_result["message"]
            return "Application operation completed successfully."

        os_info = tool_result.get("os", {})
        cpu_info = tool_result.get("cpu", {})
        mem_info = tool_result.get("memory", {})
        disk_info = tool_result.get("disk", {})
        up_info = tool_result.get("uptime", {})

        focus = intent.focus or "all"

        if focus == "memory":
            return (
                "**Memory (RAM) Status:**\n"
                f"• Available: {mem_info.get('available_gb', 0)} GB free\n"
                f"• In Use: {mem_info.get('used_gb', 0)} GB ({mem_info.get('usage_percent', 0)}%)\n"
                f"• Total Installed: {mem_info.get('total_gb', 0)} GB\n\n"
                f"(Host: {os_info.get('platform', 'Windows')})"
            )

        if focus == "cpu":
            return (
                "**Processor (CPU) Status:**\n"
                f"• Current Utilization: {cpu_info.get('usage_percent', 0)}%\n"
                f"• Logical Cores: {cpu_info.get('logical_cores', 1)}\n"
                f"• Physical Cores: {cpu_info.get('physical_cores', 1)}\n"
                f"• Processor: {cpu_info.get('processor', 'CPU')}"
            )

        if focus == "disk":
            drive = disk_info.get("drive", "C:\\")
            return (
                f"**Primary Storage ({drive}) Status:**\n"
                f"• Free Space: {disk_info.get('free_gb', 0)} GB available\n"
                f"• Used Space: {disk_info.get('used_gb', 0)} GB ({disk_info.get('usage_percent', 0)}%)\n"
                f"• Total Capacity: {disk_info.get('total_gb', 0)} GB"
            )

        if focus == "uptime":
            return (
                "**System Uptime:**\n"
                f"• Uptime: {up_info.get('uptime_formatted', 'Unknown')}\n"
                f"• Boot Time (UTC): {up_info.get('boot_time', 'Unknown')}"
            )

        # Default comprehensive summary (focus == "all")
        return (
            "**SparkDesk System Overview:**\n"
            f"• **Operating System:** {os_info.get('platform', 'Windows')} ({os_info.get('architecture', '64bit')})\n"
            f"• **CPU Utilization:** {cpu_info.get('usage_percent', 0)}% ({cpu_info.get('logical_cores', 1)} cores)\n"
            f"• **Memory (RAM):** {mem_info.get('used_gb', 0)} GB / {mem_info.get('total_gb', 0)} GB "
            f"({mem_info.get('available_gb', 0)} GB free, {mem_info.get('usage_percent', 0)}% used)\n"
            f"• **Storage ({disk_info.get('drive', 'C:')}):** {disk_info.get('free_gb', 0)} GB free of {disk_info.get('total_gb', 0)} GB "
            f"({disk_info.get('usage_percent', 0)}% used)\n"
            f"• **System Uptime:** {up_info.get('uptime_formatted', 'Unknown')}"
        )


# Global singleton instance
intent_engine = IntentEngine()
