import logging
import time

from selenium.webdriver.common.by import By

logger = logging.getLogger("phongvu-tests-selenium")


class BasePage:
    """Small Selenium page-object base used by higher-level pages."""

    def __init__(self, driver, config):
        self.driver = driver
        self.config = config

    def first_visible(self, selectors, timeout=3):
        return first_visible(self.driver, selectors, timeout=timeout)

    def all_visible(self, selectors, timeout=3):
        return all_visible(self.driver, selectors, timeout=timeout)


def first_visible(driver, selectors, timeout=3):
    """Return the first displayed element matching any CSS selector."""
    start_time = time.time()
    last_exc = None
    while time.time() - start_time < timeout:
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        logger.debug("Found visible element with selector: %s", selector)
                        return element
            except Exception as exc:
                last_exc = exc
        time.sleep(0.2)

    logger.warning("No visible element found for selectors: %s", selectors)
    if last_exc:
        raise last_exc
    raise Exception(f"No visible element found for selectors: {selectors}")


def all_visible(driver, selectors, timeout=3):
    """Return displayed elements matching the first selector that has results."""
    start_time = time.time()
    last_exc = None
    while time.time() - start_time < timeout:
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                visible_elements = [element for element in elements if element.is_displayed()]
                if visible_elements:
                    return visible_elements
            except Exception as exc:
                last_exc = exc
        time.sleep(0.2)

    logger.warning("No visible elements found for selectors: %s", selectors)
    if last_exc:
        raise last_exc
    raise Exception(f"No visible elements found for selectors: {selectors}")

