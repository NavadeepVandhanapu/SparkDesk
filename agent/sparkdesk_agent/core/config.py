"""Centralized configuration loader for SparkDesk Local Agent.

Reads shared configuration from the existing SparkDesk `config/settings.ini`,
respects environment variable overrides, and enforces security constraints (loopback-only binding).
"""

from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path
from typing import Optional, Set

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_LOOPBACK_HOSTS: Set[str] = {"127.0.0.1", "localhost"}


def get_project_root() -> Path:
    """Return the SparkDesk project root directory."""
    return Path(__file__).resolve().parents[3]


class AgentSettings(BaseSettings):
    """Central settings for the SparkDesk Local Agent."""

    model_config = SettingsConfigDict(
        env_prefix="SPARKDESK_AGENT_",
        env_file=".env",
        extra="ignore",
    )

    # Agent Identity
    agent_name: str = "SparkDesk Local Agent"
    agent_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    # Server / IPC Binding (Enforced loopback only)
    host: str = "127.0.0.1"
    port: int = 8765

    # Paths
    project_root: Path = Field(default_factory=get_project_root)
    shared_config_path: Optional[Path] = None
    log_path: Optional[Path] = None

    # Shared settings loaded from config/settings.ini
    show_startup_notification: bool = True
    log_level: str = "INFO"

    @field_validator("host")
    @classmethod
    def validate_loopback_host(cls, v: str) -> str:
        """Enforce strict loopback-only binding."""
        normalized = v.strip().lower()
        if normalized not in ALLOWED_LOOPBACK_HOSTS:
            raise ValueError(
                f"Security violation: SparkDesk Local Agent only permits loopback binding "
                f"('127.0.0.1' or 'localhost'). Rejected host: '{v}'"
            )
        return normalized

    @classmethod
    def load_from_ini(cls) -> "AgentSettings":
        """Load settings, enriching defaults with values from config/settings.ini."""
        root = get_project_root()
        ini_path = root / "config" / "settings.ini"
        default_log_path = root / "data" / "sparkdesk.log"

        show_notification = True
        host = "127.0.0.1"
        port = 8765
        debug = False
        log_level = "INFO"

        if ini_path.is_file():
            parser = ConfigParser()
            try:
                parser.read(ini_path, encoding="utf-8")
                if parser.has_section("General"):
                    show_notification = parser.getboolean(
                        "General", "ShowStartupNotification", fallback=True
                    )
                if parser.has_section("Agent"):
                    host = parser.get("Agent", "Host", fallback=host)
                    port = parser.getint("Agent", "Port", fallback=port)
                    debug = parser.getboolean("Agent", "Debug", fallback=debug)
                    log_level = parser.get("Agent", "LogLevel", fallback=log_level)
            except Exception:
                pass

        return cls(
            project_root=root,
            shared_config_path=ini_path,
            log_path=default_log_path,
            show_startup_notification=show_notification,
            host=host,
            port=port,
            debug=debug,
            log_level=log_level,
        )


@lru_cache()
def get_settings() -> AgentSettings:
    """Return a cached singleton instance of AgentSettings."""
    return AgentSettings.load_from_ini()
