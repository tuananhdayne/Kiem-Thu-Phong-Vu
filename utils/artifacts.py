import logging
import re
import time

from utils.logging_utils import ensure_report_directories
from utils.paths import SCREENSHOT_DIR

logger = logging.getLogger("phongvu-tests-selenium")


def capture_screenshot(name, driver=None):
    """Capture a Selenium screenshot into reports/screenshots."""
    if driver is None:
        raise ValueError("capture_screenshot requires a Selenium webdriver instance")

    ensure_report_directories()
    try:
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "screenshot"
    screenshot_path = SCREENSHOT_DIR / f"{safe_name}_{timestamp}.png"

    logger.info("Saving screenshot to: %s", screenshot_path)
    try:
        driver.save_screenshot(str(screenshot_path))
    except Exception as exc:
        logger.error("Could not capture screenshot: %s", exc)
    return screenshot_path

