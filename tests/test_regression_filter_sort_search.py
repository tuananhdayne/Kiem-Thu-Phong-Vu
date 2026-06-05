import os
import subprocess
import time

import pytest
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.catalog_page import (
    apply_sort_option,
    click_checkbox_by_text,
    extract_latest_prices,
    extract_product_names,
    resolve_available_text,
    search_with_keyword,
    wait_products_updated,
)
from utils.artifacts import capture_screenshot
from utils.parsers import is_sorted

pytestmark = pytest.mark.regression


def _capture_destructive_screenshot(name: str, driver) -> None:
    """Capture destructive screenshots only when explicitly enabled."""
    if os.getenv("SELENIUM_CAPTURE_DESTRUCTIVE_SCREENSHOT", "0") == "1":
        capture_screenshot(name, driver)


def _abort_destructive_browser(driver) -> None:
    """Stop the Selenium-owned browser immediately after a destructive hang is detected."""
    if os.name != "nt":
        return
    try:
        pid = driver.service.process.pid
    except Exception:
        pid = None
    if not pid:
        return
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        pass


def _destructive_fail(message: str, exc=None, driver=None) -> None:
    if driver is not None:
        _abort_destructive_browser(driver)
    detail = f": {exc}" if exc else ""
    pytest.fail(f"{message}{detail}", pytrace=False)


def _assert_destructive_liveness(driver, context: str) -> None:
    """Fail fast when Chrome/WebDriver stops responding after destructive input."""
    try:
        driver.set_script_timeout(float(os.getenv("DESTRUCTIVE_SCRIPT_TIMEOUT", "2")))
        state = driver.execute_script("return document.readyState")
        body_length = driver.execute_script("return document.body ? document.body.innerText.length : 0")
        driver.find_element(By.CSS_SELECTOR, "body").click()
    except (TimeoutException, WebDriverException, Exception) as exc:
        _capture_destructive_screenshot(f"defect_{context}_ui_unresponsive", driver)
        _destructive_fail(f"Page/WebDriver became unresponsive after {context}", exc, driver=driver)

    if state not in ("interactive", "complete") or body_length < 20:
        _destructive_fail(
            f"Page did not render a valid state after {context}: readyState={state}, body_length={body_length}",
            driver=driver,
        )


def _assert_destructive_response_time(driver, start_time: float, context: str) -> None:
    max_seconds = float(os.getenv("DESTRUCTIVE_MAX_RESPONSE_SECONDS", "8"))
    elapsed = time.time() - start_time
    if elapsed > max_seconds:
        _destructive_fail(
            f"Page response is too slow after {context}: {elapsed:.2f}s > threshold {max_seconds:.2f}s. "
            "This is treated as a freeze/hang for the destructive test.",
            driver=driver,
        )


def _visible_filter_label_texts(driver, timeout=8):
    """Return visible filter label texts with retry to avoid stale React nodes."""
    end_time = time.time() + timeout
    labels = []
    while time.time() < end_time:
        labels = []
        for element in driver.find_elements(By.CSS_SELECTOR, "label.check-box"):
            try:
                text = element.text.strip()
                if element.is_displayed() and text:
                    labels.append(text)
            except StaleElementReferenceException:
                continue
        if labels:
            return labels
        time.sleep(0.25)
    return labels


def test_filter_multiple_conditions(driver, test_config):
    """Hồi quy: Áp dụng đồng thời nhiều bộ lọc khác nhau và xác nhận kết quả cập nhật chính xác."""
    driver.get(test_config["pages"]["laptop"])
    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "label.check-box input[type='checkbox']")))

    old_names = extract_product_names(driver, test_config, limit=10)
    labels = _visible_filter_label_texts(driver)

    assert len(labels) >= 2, "Not enough visible filter labels to test multiple conditions"

    for label in labels[:2]:
        click_checkbox_by_text(driver, label)

    new_names = wait_products_updated(driver, test_config, old_names, timeout=10)

    assert new_names, f"No products after applying filters: {labels[:2]}"
    assert new_names != old_names, "Product list did not change after applying two filters"
    assert len(new_names) <= len(old_names), "Product count increased after filtering, which is not expected"


def test_preserve_sort_state_on_reload_and_navigation(driver, test_config):
    """Hồi quy: Giữ nguyên trạng thái sắp xếp giá tăng dần sau khi tải lại trang hoặc điều hướng quay lại."""
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
    assert prices_before, "Could not extract prices after sorting"

    driver.refresh()
    wait.until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Sắp xếp theo']")))
    time.sleep(1)

    prices_after_reload = extract_latest_prices(driver, test_config, limit=5)
    assert prices_after_reload, "Could not extract prices after reload"
    assert is_sorted(prices_after_reload, ascending=True), f"Prices are not sorted after reload: {prices_after_reload}"

    previous_url = driver.current_url
    driver.get(test_config["pages"]["monitor"])
    driver.get(previous_url)

    wait.until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Sắp xếp theo']")))
    time.sleep(1)

    prices_after_nav = extract_latest_prices(driver, test_config, limit=5)
    assert is_sorted(prices_after_nav, ascending=True), f"Prices are not sorted after navigation: {prices_after_nav}"


def test_sort_combined_with_filter_and_search(driver, test_config):
    """Hồi quy: Sắp xếp giá vẫn hoạt động chính xác sau khi đã áp dụng lọc hoặc trên trang kết quả tìm kiếm."""
    driver.get(test_config["pages"]["laptop"])
    wait = WebDriverWait(driver, 15)

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "label.check-box input[type='checkbox']")))
    visible_labels = _visible_filter_label_texts(driver)
    if not visible_labels:
        pytest.skip("No visible filter checkbox available")
    label_text = visible_labels[0]
    click_checkbox_by_text(driver, label_text)

    old_names = extract_product_names(driver, test_config, limit=10)
    new_names = wait_products_updated(driver, test_config, old_names, timeout=10)
    assert new_names, "No results after applying filter"

    sort_option = test_config.get("test_data", {}).get("sort_option") or test_config["test_data"].get("sort_option_candidates", [None])[0]
    try:
        resolved = resolve_available_text(driver, test_config["test_data"].get("sort_option_candidates", [sort_option]))
    except AssertionError:
        resolved = sort_option

    apply_sort_option(driver, resolved)
    time.sleep(1.5)

    prices = extract_latest_prices(driver, test_config, limit=5)
    assert prices, "Could not extract prices after filter + sort"
    assert is_sorted(prices, ascending=True), f"Prices are not sorted after filter + sort: {prices}"

    driver.get(test_config["base_url"])
    search_with_keyword(driver, test_config, "Logitech")

    try:
        resolved_search = resolve_available_text(driver, test_config["test_data"].get("sort_option_candidates", [sort_option]))
    except AssertionError:
        resolved_search = sort_option

    apply_sort_option(driver, resolved_search)
    time.sleep(1.5)

    prices_search = extract_latest_prices(driver, test_config, limit=5)
    assert prices_search, "Could not extract prices after search + sort"
    assert is_sorted(prices_search, ascending=True), f"Prices are not sorted after search + sort: {prices_search}"
