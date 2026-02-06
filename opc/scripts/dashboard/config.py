"""Dashboard server configuration.

Provides environment-based configuration using pydantic-settings.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Dashboard server settings.

    Attributes:
        HOST: Server host address
        PORT: Server port number
        DATABASE_URL: PostgreSQL connection URL
    """

    HOST: str = "127.0.0.1"
    PORT: int = 3434
    DATABASE_URL: str = ""

    def __init__(self, **kwargs):
        """Initialize settings with DATABASE_URL fallback logic."""
        super().__init__(**kwargs)

        # If DATABASE_URL not set via env/kwargs, apply fallback logic
        if not self.DATABASE_URL:
            self.DATABASE_URL = self._get_database_url()

    def _get_database_url(self) -> str:
        """Get database URL from environment or use defaults.

        Priority:
            1. OPC_POSTGRES_URL
            2. AGENTICA_POSTGRES_URL
            3. DATABASE_URL
            4. Development default (if not production)

        Returns:
            PostgreSQL connection URL

        Raises:
            ValueError: If no URL is set in production mode
        """
        url = (
            os.environ.get("OPC_POSTGRES_URL")
            or os.environ.get("AGENTICA_POSTGRES_URL")
            or os.environ.get("DATABASE_URL")
        )

        if url:
            return url

        # Check if production mode
        if os.environ.get("AGENTICA_ENV") == "production":
            raise ValueError(
                "OPC_POSTGRES_URL, AGENTICA_POSTGRES_URL, or DATABASE_URL must be set in production mode. "
                "Set AGENTICA_ENV=development for local defaults."
            )

        # Development default - matches docker-compose.yml (port 5434 on Windows)
        return "postgresql://claude:claude_dev@localhost:5434/continuous_claude"

    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()


def setup_logging():
    """Configure logging with console and rotating file handlers.

    Creates logs directory and adds RotatingFileHandler with:
    - Max size: 5MB per file
    - Backup count: 3 files
    - Same format as console handler
    """
    # Create logs directory
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        logs_dir / "dashboard.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
