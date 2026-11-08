"""Data models for natural language command understanding and intent classification."""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class IntentStatus(str, Enum):
    """Classification resolution status."""
    RECOGNIZED = "recognized"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class IntentResult(BaseModel):
    """Result of classifying a natural-language prompt."""

    status: IntentStatus = Field(..., description="Classification outcome status")
    intent: Optional[str] = Field(default=None, description="Identified intent name")
    tool: Optional[str] = Field(default=None, description="Mapped tool identifier in ToolRegistry")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the tool")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    focus: Optional[str] = Field(default="all", description="Specific metric focus, e.g. memory, cpu, disk, uptime")
    message: Optional[str] = Field(default=None, description="Human-readable clarification or rejection message")


class CommandRequest(BaseModel):
    """Payload for natural-language command submission."""

    prompt: str = Field(..., min_length=1, description="Natural-language prompt submitted by user")
    session_id: Optional[str] = Field(default=None, description="Optional conversation session identifier")


class CommandResponse(BaseModel):
    """Outcome of natural-language command processing."""

    success: bool = Field(..., description="Whether command was recognized and executed successfully")
    status: str = Field(..., description="Status string: recognized, ambiguous, or unsupported")
    intent: Optional[str] = Field(default=None, description="Recognized intent name")
    tool: Optional[str] = Field(default=None, description="Executed tool name")
    message: str = Field(..., description="Human-readable response message")
    tool_result: Optional[Any] = Field(default=None, description="Raw tool execution output if successful")
    timestamp: str = Field(..., description="UTC timestamp of response generation")
    session_id: Optional[str] = Field(default=None, description="Associated conversation session ID")
    plan_id: Optional[str] = Field(default=None, description="Identifier of the generated task execution plan, if any")
