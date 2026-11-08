"""Conversation Context Management for SparkDesk Local Agent.

Maintains multi-turn conversational history, topic focus, and executed tool
state across interactions. Designed for thread-safety and easy integration
with both rule-based providers and future local LLMs (such as Ollama).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """Represents a single interaction turn within a conversation."""

    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_prompt: str = Field(..., description="The user's input prompt")
    intent: Optional[str] = Field(default=None, description="Recognized intent name")
    tool: Optional[str] = Field(default=None, description="Tool invoked for this turn, if any")
    focus: Optional[str] = Field(default="all", description="Metric focus (memory, cpu, disk, uptime, all)")
    tool_result: Optional[Dict[str, Any]] = Field(default=None, description="Raw execution result summary")
    response_message: str = Field(..., description="Assistant response delivered to the user")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp",
    )


class ConversationContext(BaseModel):
    """Stores the conversational state and history for a session."""

    session_id: str = Field(..., description="Unique session identifier")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    turns: List[ConversationTurn] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def add_turn(
        self,
        user_prompt: str,
        response_message: str,
        intent: Optional[str] = None,
        tool: Optional[str] = None,
        focus: Optional[str] = "all",
        tool_result: Optional[Dict[str, Any]] = None,
    ) -> ConversationTurn:
        """Record a completed interaction turn and update session state."""
        turn = ConversationTurn(
            user_prompt=user_prompt,
            intent=intent,
            tool=tool,
            focus=focus,
            tool_result=tool_result,
            response_message=response_message,
        )
        self.turns.append(turn)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return turn

    def last_turn(self) -> Optional[ConversationTurn]:
        """Return the most recent conversation turn, or None if empty."""
        return self.turns[-1] if self.turns else None

    def last_tool(self) -> Optional[str]:
        """Return the tool executed in the most recent turn."""
        turn = self.last_turn()
        return turn.tool if turn else None

    def last_focus(self) -> Optional[str]:
        """Return the metric focus of the most recent turn."""
        turn = self.last_turn()
        return turn.focus if turn else None

    def last_tool_result(self) -> Optional[Dict[str, Any]]:
        """Return the tool result from the most recent turn."""
        turn = self.last_turn()
        return turn.tool_result if turn else None

    def get_history(self, max_turns: int = 5) -> List[Dict[str, Any]]:
        """Return recent interaction history formatted for provider consumption."""
        recent = self.turns[-max_turns:] if max_turns > 0 else self.turns
        return [
            {
                "user": turn.user_prompt,
                "intent": turn.intent,
                "tool": turn.tool,
                "focus": turn.focus,
                "assistant": turn.response_message,
                "timestamp": turn.timestamp,
            }
            for turn in recent
        ]

    def clear(self) -> None:
        """Clear all conversation turns for this session."""
        self.turns.clear()
        self.updated_at = datetime.now(timezone.utc).isoformat()


class ContextManager:
    """Manages active conversation sessions in memory."""

    DEFAULT_SESSION_ID = "default"

    def __init__(self, max_turns_per_session: int = 50) -> None:
        self._sessions: Dict[str, ConversationContext] = {}
        self._max_turns = max_turns_per_session

    def get_or_create(self, session_id: Optional[str] = None) -> ConversationContext:
        """Retrieve an existing session context or create a new one."""
        sid = (session_id or self.DEFAULT_SESSION_ID).strip()
        if not sid:
            sid = self.DEFAULT_SESSION_ID

        if sid not in self._sessions:
            self._sessions[sid] = ConversationContext(session_id=sid)

        # Enforce turn limit per session to avoid unbounded memory growth
        context = self._sessions[sid]
        if len(context.turns) > self._max_turns:
            context.turns = context.turns[-self._max_turns:]

        return context

    def get(self, session_id: str) -> Optional[ConversationContext]:
        """Get context for a session if it exists."""
        return self._sessions.get(session_id)

    def clear(self, session_id: str) -> bool:
        """Clear the context for a specific session."""
        if session_id in self._sessions:
            self._sessions[session_id].clear()
            return True
        return False

    def remove(self, session_id: str) -> bool:
        """Remove a session entirely from memory."""
        return bool(self._sessions.pop(session_id, None))

    def list_sessions(self) -> List[str]:
        """Return identifiers of all active sessions."""
        return list(self._sessions.keys())

    def reset_all(self) -> None:
        """Clear all active sessions."""
        self._sessions.clear()


# Default singleton instance
context_manager = ContextManager()

