"""IPC and API server components for SparkDesk Local Agent."""

from sparkdesk_agent.ipc.auth import (
    TOKEN_HEADER_NAME,
    generate_ephemeral_token,
    get_active_token,
    verify_token,
)
from sparkdesk_agent.ipc.protocol import HealthResponse
from sparkdesk_agent.ipc.server import create_app, start_server

__all__ = [
    "create_app",
    "start_server",
    "HealthResponse",
    "TOKEN_HEADER_NAME",
    "generate_ephemeral_token",
    "get_active_token",
    "verify_token",
]
