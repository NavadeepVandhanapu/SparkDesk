"""Natural language intent understanding package for SparkDesk Local Agent."""

from sparkdesk_agent.intent.engine import IntentEngine, intent_engine
from sparkdesk_agent.intent.models import (
    CommandRequest,
    CommandResponse,
    IntentResult,
    IntentStatus,
)

__all__ = [
    "intent_engine",
    "IntentEngine",
    "IntentResult",
    "IntentStatus",
    "CommandRequest",
    "CommandResponse",
]

