"""Centralized logging configuration for SparkDesk Local Agent.

Outputs structured, formatted logs to the console and to the shared SparkDesk
log file located in `data/sparkdesk.log`, preserving UTF-8 encoding.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from sparkdesk_agent.core.config import AgentSettings, get_settings

_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(settings: Optional[AgentSettings] = None) -> logging.Logger:
    """Configure centralized logging for the SparkDesk Local Agent."""
    if settings is None:
        settings = get_settings()

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers if setup_logging is called multiple times
    if root_logger.handlers:
        root_logger.handlers.clear()

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # 1. Console / Stream Handler (sys.stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. Rotating File Handler (shared data/sparkdesk.log)
    log_file_path = settings.log_path or (settings.project_root / "data" / "sparkdesk.log")
    try:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as err:
        root_logger.warning("Failed to initialize file logging handler: %s", err)

    # Suppress overly chatty third-party loggers unless debug is enabled
    if not settings.debug:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    agent_logger = logging.getLogger("sparkdesk_agent")
    agent_logger.info(
        "Logging initialized. Log file: %s | Level: %s",
        log_file_path,
        settings.log_level,
    )
    return agent_logger


def get_logger(name: str = "sparkdesk_agent") -> logging.Logger:
    """Return a logger configured under the sparkdesk hierarchy."""
    return logging.getLogger(name)

