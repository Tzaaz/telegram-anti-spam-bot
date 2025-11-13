# FILE: config.py
"""
Environment configuration using pydantic.
All secrets are loaded from environment variables.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Config(BaseSettings):
    """Application configuration from environment variables."""

    # Telegram
    BOT_TOKEN: str
    PUBLIC_BASE_URL: str  # e.g., https://mybot.onrender.com (no trailing slash)
    ADMIN_LOG_CHAT_ID: int = -1003399150838

    # Redis
    REDIS_URL: str  # redis://... or rediss://... (TLS)

    # Feature flags
    STRICT_MODE: bool = False

    # Server
    PORT: int = 8080
    HOST: str = "0.0.0.0"

    # Runtime
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global config instance
config: Optional[Config] = None


def get_config() -> Config:
    """Get or initialize the global config instance."""
    global config
    if config is None:
        config = Config()
    return config
