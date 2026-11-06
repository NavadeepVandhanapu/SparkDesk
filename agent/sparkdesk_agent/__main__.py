"""Package entrypoint when invoked with `python -m sparkdesk_agent`."""

import sys
from sparkdesk_agent.core.config import get_settings
from sparkdesk_agent.core.logging import setup_logging


def main() -> None:
    """Print configuration and initialize logging."""
    settings = get_settings()
    logger = setup_logging(settings)

    logger.info("SparkDesk Local Agent (Phase 1 Environment)")
    logger.info("Python Version: %s", sys.version)
    logger.info("Project Root: %s", settings.project_root)
    logger.info("Shared Config: %s", settings.shared_config_path)
    logger.info("Show Startup Notification (from settings.ini): %s", settings.show_startup_notification)
    logger.info("Host: %s | Port: %d | Debug: %s", settings.host, settings.port, settings.debug)
    logger.info("Phase 1 initialization successful. Ready for Phase 2 IPC & Endpoints.")


if __name__ == "__main__":
    main()

