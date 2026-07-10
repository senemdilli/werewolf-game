import logging
import sys

from core.settings import get_settings

configured = False

def configure_logging() -> None:
    """
    Configure logging for the application.
    This function will set up the logging configuration based on the settings.
    """
    global configured
    if configured:
        return

    settings = get_settings()

    logging.basicConfig(
        level=settings.log_level,
        format=settings.log_format,
        datefmt=settings.date_format,
        stream=sys.stdout,
    )

    configured = True

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the given name.
    This function will configure logging if it has not been configured yet.
    """
    configure_logging()
    return logging.getLogger(name)