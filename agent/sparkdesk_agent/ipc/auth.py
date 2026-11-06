"""Authentication and security module for SparkDesk Local Agent IPC.

Provides ephemeral token generation, constant-time validation, and token file management.
Tokens are NEVER logged to loggers, stdout, or diagnostics.
"""

from pathlib import Path
import os
import secrets
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from sparkdesk_agent.core.logging import get_logger

TOKEN_HEADER_NAME = "X-SparkDesk-Token"
api_key_header = APIKeyHeader(name=TOKEN_HEADER_NAME, auto_error=False)

_ACTIVE_TOKEN: Optional[str] = None


def generate_ephemeral_token() -> str:
    """Generate a high-entropy, cryptographically secure URL-safe token."""
    global _ACTIVE_TOKEN
    _ACTIVE_TOKEN = secrets.token_urlsafe(32)
    return _ACTIVE_TOKEN


def get_active_token() -> Optional[str]:
    """Return the active in-memory session token (never log the return value)."""
    return _ACTIVE_TOKEN


def write_token_file(file_path: Path, token: str) -> None:
    """Write the session token to disk for AutoHotkey handoff with restricted permissions."""
    logger = get_logger("sparkdesk_agent.auth")
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Write token exclusively to the session token file
        file_path.write_text(token, encoding="utf-8")
        logger.info("Session token written securely to %s", file_path.name)
    except Exception as err:
        logger.error("Failed to write session token file: %s", err)
        raise err


def remove_token_file(file_path: Path) -> None:
    """Cleanly delete the session token file upon shutdown."""
    global _ACTIVE_TOKEN
    _ACTIVE_TOKEN = None
    logger = get_logger("sparkdesk_agent.auth")
    try:
        if file_path.is_file():
            file_path.unlink()
            logger.info("Session token file removed cleanly.")
    except Exception as err:
        logger.warning("Could not remove token file during shutdown: %s", err)


async def verify_token(
    header_token: Optional[str] = Security(api_key_header),
) -> str:
    """FastAPI security dependency to validate requests against the active ephemeral token.

    Uses constant-time comparison to protect against timing attacks.
    """
    active = get_active_token()
    if active is None or not header_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or uninitialized authentication token",
            headers={"WWW-Authenticate": TOKEN_HEADER_NAME},
        )

    # Constant-time comparison
    if not secrets.compare_digest(header_token, active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": TOKEN_HEADER_NAME},
        )

    return header_token
