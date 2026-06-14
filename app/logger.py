"""Logging configuration using structlog."""

import logging
import sys
from pathlib import Path

import structlog

from app.config import get_settings

settings = get_settings()

LOG_DIR: Path = settings.logs_dir
LOG_FILE: Path = LOG_DIR / "app.log"


def setup_logging() -> None:
    """Configure structured logging for both console and file."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Standard logging config so library logs propagate
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(level)

    # Quiet noisy libraries
    for noisy in ("httpx", "httpcore", "multipart", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a configured logger."""
    return structlog.get_logger(name)
