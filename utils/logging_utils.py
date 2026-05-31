import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils.paths import REPORTS_DIR, SCREENSHOT_DIR

LOGGER_NAME = "phongvu-tests-selenium"


def ensure_report_directories():
    """Create report directories used by CLI runs and the dashboard."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def configure_logging(log_file_path=None):
    """Configure file and console logging for pytest/Selenium runs."""
    ensure_report_directories()
    log_path = Path(log_file_path) if log_file_path else REPORTS_DIR / "test.log"

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    return logging.getLogger(LOGGER_NAME)

