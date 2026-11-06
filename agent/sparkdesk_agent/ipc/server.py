"""FastAPI Application and Uvicorn Server for SparkDesk Local Agent."""

import os
import platform
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI
import uvicorn

from sparkdesk_agent.core.config import AgentSettings, get_settings
from sparkdesk_agent.core.logging import get_logger, setup_logging
from sparkdesk_agent.ipc.protocol import HealthResponse

_START_TIME: float = time.monotonic()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle graceful startup and shutdown lifecycle events."""
    global _START_TIME
    _START_TIME = time.monotonic()

    settings: AgentSettings = getattr(app.state, "settings", get_settings())
    logger = get_logger("sparkdesk_agent.server")

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

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Agent Health Check",
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
    """Start the Uvicorn ASGI server with SparkDesk configuration."""
    if settings is None:
        settings = get_settings()

    # Ensure centralized logging is initialized
    setup_logging(settings)
    logger = get_logger("sparkdesk_agent.server")

    # Safety check: bind strictly to localhost by default
    if settings.host not in ("127.0.0.1", "localhost"):
        logger.warning(
            "Security notice: Host is set to '%s'. Local agent is recommended to bind to 127.0.0.1.",
            settings.host,
        )

    app = create_app(settings)

    # Convert settings log level to lowercase string for Uvicorn
    uvicorn_log_level = settings.log_level.lower()
    if uvicorn_log_level not in ("critical", "error", "warning", "info", "debug", "trace"):
        uvicorn_log_level = "info"

    logger.info(
        "Launching Uvicorn on http://%s:%d [Log Level: %s]",
        settings.host,
        settings.port,
        uvicorn_log_level,
    )

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=uvicorn_log_level,
        access_log=settings.debug,
    )
