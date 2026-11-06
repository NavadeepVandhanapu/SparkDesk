"""Top-level agent runner for SparkDesk Local Agent."""

import sys
from pathlib import Path

# Ensure the agent directory is in the Python module search path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from sparkdesk_agent.core.config import get_settings
from sparkdesk_agent.core.logging import setup_logging


def main() -> None:
    settings = get_settings()
    logger = setup_logging(settings)
    logger.info("Starting %s v%s...", settings.agent_name, settings.agent_version)
    logger.info("Config source: %s", settings.shared_config_path)
    logger.info("Log destination: %s", settings.log_path)
    logger.info("Phase 1 scaffolding verified successfully.")


if __name__ == "__main__":
    main()

