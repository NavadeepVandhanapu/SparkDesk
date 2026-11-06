"""Top-level agent runner for SparkDesk Local Agent."""

import argparse
import sys
from pathlib import Path

# Ensure the agent directory is in the Python module search path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from sparkdesk_agent.core.config import ALLOWED_LOOPBACK_HOSTS, get_settings
from sparkdesk_agent.core.logging import setup_logging
from sparkdesk_agent.ipc.server import start_server


def main() -> None:
    parser = argparse.ArgumentParser(description="SparkDesk Local Agent Runner")
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind (Enforced: 127.0.0.1 or localhost)",
    )
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: 8765)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    settings = get_settings()

    if args.host is not None:
        normalized_host = args.host.strip().lower()
        if normalized_host not in ALLOWED_LOOPBACK_HOSTS:
            parser.error(
                f"Security violation: SparkDesk Local Agent only permits loopback binding "
                f"('127.0.0.1' or 'localhost'). Rejected host: '{args.host}'"
            )
        settings.host = normalized_host

    if args.port:
        settings.port = args.port
    if args.debug:
        settings.debug = True
        settings.log_level = "DEBUG"

    setup_logging(settings)
    start_server(settings)


if __name__ == "__main__":
    main()
