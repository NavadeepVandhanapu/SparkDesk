"""FastAPI Application and Uvicorn Server for SparkDesk Local Agent."""

import asyncio
from datetime import datetime, timezone
import os
import platform
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import Depends, FastAPI
import uvicorn

from sparkdesk_agent.core.config import ALLOWED_LOOPBACK_HOSTS, AgentSettings, get_settings
from sparkdesk_agent.core.logging import get_logger, setup_logging
from sparkdesk_agent.ipc.auth import (
    generate_ephemeral_token,
    remove_token_file,
    verify_token,
    write_token_file,
)
from sparkdesk_agent.ipc.protocol import HealthResponse

_START_TIME: float = time.monotonic()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle graceful startup, token provisioning, and clean shutdown."""
    global _START_TIME
    _START_TIME = time.monotonic()

    settings: AgentSettings = getattr(app.state, "settings", get_settings())
    logger = get_logger("sparkdesk_agent.server")

    # 1. Generate and write ephemeral auth token (never log the token value)
    token = generate_ephemeral_token()
    token_file = settings.token_path or (settings.project_root / "data" / "session.token")
    write_token_file(token_file, token)

    logger.info(
        "SparkDesk Agent Server starting up on %s:%d (PID: %d)...",
        settings.host,
        settings.port,
        os.getpid(),
    )
    logger.info("Host platform: %s | Python: %s", platform.platform(), platform.python_version())

    try:
        yield
    finally:
        logger.info("SparkDesk Agent Server shutting down cleanly...")
        # 2. Invalidate and remove the ephemeral token file on shutdown
        remove_token_file(token_file)


def create_app(settings: Optional[AgentSettings] = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.agent_name,
        version=settings.agent_version,
        description="Local AI-powered PC Assistant Agent for SparkDesk",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.server = None

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Agent Health Check (Unauthenticated loopback probe)",
        tags=["System"],
    )
    async def health_check() -> HealthResponse:
        """Return agent operational status, Python version, uptime, and PID."""
        uptime = round(time.monotonic() - _START_TIME, 2)
        return HealthResponse(
            status="ok",
            agent_name=settings.agent_name,
            version=settings.agent_version,
            python_version=platform.python_version(),
            uptime_seconds=uptime,
            pid=os.getpid(),
            environment=settings.environment,
        )

    @app.get(
        "/ipc/ping",
        summary="Authenticated IPC Ping",
        tags=["IPC"],
    )
    async def ipc_ping(_: str = Depends(verify_token)) -> dict:
        """Authenticated connectivity test for AutoHotkey AgentBridge."""
        return {
            "status": "pong",
            "agent": settings.agent_name,
            "version": settings.agent_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.post(
        "/shutdown",
        summary="Protected Graceful Shutdown",
        tags=["System"],
    )
    async def trigger_shutdown(_: str = Depends(verify_token)) -> dict:
        """Gracefully request the local agent server to shut down (Authenticated)."""
        logger = get_logger("sparkdesk_agent.server")
        logger.info("Graceful shutdown requested via authenticated /shutdown endpoint.")

        async def _initiate_shutdown() -> None:
            # Yield control briefly so the HTTP 200 response is dispatched to the client
            await asyncio.sleep(0.15)
            server_inst = getattr(app.state, "server", None)
            if server_inst is not None:
                server_inst.should_exit = True
            else:
                logger.warning("No active uvicorn server reference registered on app.state.")

        asyncio.create_task(_initiate_shutdown())
        return {
            "status": "shutting_down",
            "message": "SparkDesk Local Agent is shutting down cleanly.",
        }

    @app.get("/", include_in_schema=False)
    async def root_redirect() -> dict:
        """Simple root probe indicating service is ready."""
        return {
            "name": settings.agent_name,
            "version": settings.agent_version,
            "status": "ready",
            "health_endpoint": "/health",
        }

    return app


def start_server(settings: Optional[AgentSettings] = None) -> None:
    """Start the Uvicorn ASGI server with SparkDesk configuration.

    Enforces loopback-only binding ('127.0.0.1' or 'localhost').
    Rejects any external or wildcard host.
    """
    if settings is None:
        settings = get_settings()

    # Hard security check: enforce loopback only
    normalized_host = settings.host.strip().lower()
    if normalized_host not in ALLOWED_LOOPBACK_HOSTS:
        raise ValueError(
            f"Security violation: SparkDesk Local Agent rejects non-loopback host '{settings.host}'. "
            f"Allowed hosts: {sorted(ALLOWED_LOOPBACK_HOSTS)}"
        )

    # Ensure centralized logging is initialized
    setup_logging(settings)
    logger = get_logger("sparkdesk_agent.server")

    app = create_app(settings)

    uvicorn_log_level = settings.log_level.lower()
    if uvicorn_log_level not in ("critical", "error", "warning", "info", "debug", "trace"):
        uvicorn_log_level = "info"

    logger.info(
        "Launching Uvicorn on http://%s:%d [Log Level: %s]",
        settings.host,
        settings.port,
        uvicorn_log_level,
    )

    config = uvicorn.Config(
        app=app,
        host=normalized_host,
        port=settings.port,
        log_level=uvicorn_log_level,
        access_log=settings.debug,
    )
    server = uvicorn.Server(config)
    app.state.server = server
    server.run()
