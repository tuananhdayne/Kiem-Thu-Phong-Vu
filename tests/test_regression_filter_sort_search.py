import time

import pytest

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.catalog_page import apply_sort_option, extract_latest_prices, log_test_evidence, resolve_available_text
from utils.parsers import is_sorted

pytestmark = pytest.mark.regression


def test_preserve_sort_state_on_reload_and_navigation(driver, test_config):
    """Regression: price ascending sort state is preserved after reload and navigation back."""
    driver.get(test_config["pages"]["laptop"])
    wait = WebDriverWait(driver, 20)

    sort_option = test_config.get("test_data", {}).get("sort_option") or test_config["test_data"].get("sort_option_candidates", [None])[0]
    assert sort_option, "Missing sort_option in config"

    try:
        resolved = resolve_available_text(driver, test_config["test_data"].get("sort_option_candidates", [sort_option]))
    except AssertionError:
        resolved = sort_option

    apply_sort_option(driver, resolved)
    wait.until(lambda d: "sort=" in d.current_url.lower() or "order=" in d.current_url.lower())

    prices_before = extract_latest_prices(driver, test_config, limit=5)
    log_test_evidence(
        "SORT STATE BEFORE RELOAD",
        option=resolved,
        url=driver.current_url,
        prices=[f"{price:,} VND" for price in prices_before],
    )
    assert prices_before, "Could not extract prices after sorting"

    driver.refresh()
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Sắp xếp theo']")))
    time.sleep(1)

    prices_after_reload = extract_latest_prices(driver, test_config, limit=5)
    log_test_evidence(
        "SORT STATE AFTER RELOAD",
        option=resolved,
        url=driver.current_url,
        prices=[f"{price:,} VND" for price in prices_after_reload],
    )
    assert prices_after_reload, "Could not extract prices after reload"
    assert is_sorted(prices_after_reload, ascending=True), f"Prices are not sorted after reload: {prices_after_reload}"

    previous_url = driver.current_url
    driver.get(test_config["pages"]["monitor"])
    driver.get(previous_url)

    wait.until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Sắp xếp theo']")))
    time.sleep(1)

    prices_after_nav = extract_latest_prices(driver, test_config, limit=5)
    log_test_evidence(
        "SORT STATE AFTER NAVIGATION BACK",
        option=resolved,
        url=driver.current_url,
        prices=[f"{price:,} VND" for price in prices_after_nav],
    )
    assert is_sorted(prices_after_nav, ascending=True), f"Prices are not sorted after navigation: {prices_after_nav}"
