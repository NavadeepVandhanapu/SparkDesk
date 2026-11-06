"""Package entrypoint when invoked with `python -m sparkdesk_agent`."""

import argparse
import sys

from sparkdesk_agent.core.config import get_settings
from sparkdesk_agent.core.logging import setup_logging
from sparkdesk_agent.ipc.server import start_server


def main() -> None:
    parser = argparse.ArgumentParser(description="SparkDesk Local Agent Server")
    parser.add_argument("--host", type=str, default=None, help="Host to bind (default: from config)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: from config)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    settings = get_settings()
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    if args.debug:
        settings.debug = True
        settings.log_level = "DEBUG"

    setup_logging(settings)
    start_server(settings)


if __name__ == "__main__":
    main()
