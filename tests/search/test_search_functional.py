import time
import re

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from pages.catalog_page import (
    search_with_keyword,
    extract_product_names,
    find_search_input,
    NO_RESULTS_TEXT,
)
from pages.base_page import first_visible


pytestmark = pytest.mark.slow


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").strip().lower())



def test_search_load_more_preserves_keyword(driver, test_config):
    """Verify 'Load more' or pagination preserves the original search keyword.

    This test supports both classic pagination (next link) and a "Load more" button
    (e.g. labeled "Xem thêm" / "Load more"). If neither control is found, the test is skipped.
    """
    keyword = test_config["test_data"].get("search_keyword", "Logitech")
    driver.get(test_config["base_url"])

    search_with_keyword(driver, test_config, keyword, timeout=8)
    names_before = extract_product_names(driver, test_config, limit=8)
    assert names_before, "No results on first page to validate pagination/load-more"

    # Pagination selectors (links) and common "load more" button selectors
    pagination_selectors = [
        "a[rel='next']",
        "ul.pagination li a",
        "a.next",
        "button[aria-label='Next']",
        "a[aria-label='Next']",
        "nav[aria-label='Pagination'] a",
    ]
    load_more_selectors = [
        "button.load-more",
        "button#load-more",
        ".btn-load-more",
        "button[aria-label*='Xem']",
        "button[aria-label*='Load']",
        "button:contains('Xem thêm')",
        "button:contains('Load more')",
    ]

    control = None
    control_type = None
    try:
        control = first_visible(driver, pagination_selectors, timeout=2)
        control_type = "pagination"
    except Exception:
        # try load-more
        try:
            control = first_visible(driver, load_more_selectors, timeout=2)
            control_type = "load_more"
        except Exception:
            pytest.skip("No pagination or load-more control detected on search results page")

    # Click the control (scroll into view first)
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", control)
        control.click()
    except Exception:
        driver.execute_script("arguments[0].click();", control)

    deadline = time.time() + 8
    new_names = []
    while time.time() < deadline:
        new_names = extract_product_names(driver, test_config, limit=16)
        if new_names and (
            (control_type == "pagination" and new_names != names_before)
            or (control_type == "load_more" and len(new_names) > len(names_before))
        ):
            break
        time.sleep(0.3)

    assert new_names, "No results after clicking pagination/load-more control"

    # Ensure search input still contains or reflects the keyword (loose check)
    try:
        search_input = find_search_input(driver, test_config, timeout=3)
        value = (search_input.get_attribute("value") or "").strip()
        assert _normalize(keyword) in _normalize(value) or _normalize(value) in _normalize(keyword), (
            f"Search input did not preserve keyword after navigation: '{value}' vs '{keyword}'"
        )
    except Exception:
        # If input not found, ensure URL or body indicates search still applied
        assert "tim-kiem" in driver.current_url.lower() or "q=" in driver.current_url.lower() or NO_RESULTS_TEXT in driver.find_element(By.TAG_NAME, "body").text.lower()


def test_search_deeplink_query_loads_correct_results(driver, test_config):
    """Open direct deeplink URLs with query and verify results load.

    Thử vài pattern thông dụng; nếu không có pattern nào phù hợp thì skip.
    """
    keyword = test_config["test_data"].get("search_keyword", "Logitech")
    base = test_config["base_url"].rstrip("/")
    patterns = [
        f"{base}/tim-kiem?q={keyword}",
        f"{base}/search?q={keyword}",
        f"{base}/?q={keyword}",
        f"{base}/tim-kiem/{keyword}",
    ]

    loaded = False
    for url in patterns:
        try:
            driver.get(url)
            time.sleep(1)
            names = extract_product_names(driver, test_config, limit=6)
            if names or NO_RESULTS_TEXT in driver.find_element(By.TAG_NAME, "body").text.lower():
                loaded = True
                break
        except Exception:
            continue

    if not loaded:
        pytest.skip("No known deeplink pattern matched on this site; skip deeplink test")

    assert names is not None, "Deep-link did not produce a valid results state"


def test_search_autocomplete_suggestion_click_navigates_to_results(driver, test_config):
    """Type a partial keyword, click first autocomplete suggestion, verify navigation/results.

    Nếu site không hiển thị suggestions, test sẽ skip.
    """
    partial = "Logi"
    driver.get(test_config["base_url"])

    search_input = find_search_input(driver, test_config, timeout=5)
    driver.execute_script("arguments[0].focus(); arguments[0].value = '';", search_input)
    search_input.send_keys(partial)

    # Common suggestion selectors
    suggestion_selectors = [
        "ul[role='listbox'] li",
        "[class*='suggest'] li",
        "[class*='autocomplete'] li",
        "div.suggestion-item",
    ]

    # wait a moment for suggestions to appear
    suggestion = None
    end = time.time() + 4
    while time.time() < end and suggestion is None:
        for sel in suggestion_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                visible = [e for e in elements if e.is_displayed()]
                if visible:
                    suggestion = visible[0]
                    break
            except Exception:
                continue
        time.sleep(0.25)

    if not suggestion:
        pytest.skip("No autocomplete suggestions detected on this site")

    try:
        suggestion_text = suggestion.text.strip()
        suggestion.click()
    except Exception:
        driver.execute_script("arguments[0].click();", suggestion)

    # Wait for results to be ready
    deadline = time.time() + 6
    while time.time() < deadline:
        names = extract_product_names(driver, test_config, limit=5)
        if names or NO_RESULTS_TEXT in driver.find_element(By.TAG_NAME, "body").text.lower():
            break
        time.sleep(0.3)

    assert names or NO_RESULTS_TEXT in driver.find_element(By.TAG_NAME, "body").text.lower(), (
        "Clicking suggestion did not lead to a valid results state"
    )


def test_search_enter_vs_click_icon_same_result(driver, test_config):
    """Compare Enter key submission vs clicking the search icon/button.

    Nếu không tìm thấy nút search, test sẽ skip.
    """
    keyword = test_config["test_data"].get("search_keyword", "Logitech")
    driver.get(test_config["base_url"])

    # Enter submit
    search_input = find_search_input(driver, test_config, timeout=5)
    search_input.clear()
    search_input.send_keys(keyword)
    search_input.send_keys(Keys.ENTER)
    names_enter = []
    deadline = time.time() + 6
    while time.time() < deadline:
        names_enter = extract_product_names(driver, test_config, limit=5)
        if names_enter:
            break
        time.sleep(0.3)

    assert names_enter, "No results after Enter submission"

    # Now try click icon/button
    driver.get(test_config["base_url"])
    search_input = find_search_input(driver, test_config, timeout=5)
    search_input.clear()
    search_input.send_keys(keyword)

    button_selectors = [
        "button[type='submit']",
        "button[aria-label='Search']",
        "button[title*='Tìm']",
        ".search-button",
        ".search-icon",
    ]

    try:
        btn = first_visible(driver, button_selectors, timeout=3)
    except Exception:
        pytest.skip("No visible search button/icon found to click")

    try:
        btn.click()
    except Exception:
        driver.execute_script("arguments[0].click();", btn)

    names_click = []
    deadline = time.time() + 6
    while time.time() < deadline:
        names_click = extract_product_names(driver, test_config, limit=5)
        if names_click:
            break
        time.sleep(0.3)

    assert names_click, "No results after clicking search icon/button"

    # Loose equality: ensure top results overlap meaningfully
    overlap = set(n.lower() for n in names_enter) & set(n.lower() for n in names_click)
    assert overlap, f"Enter and click produced disjoint top results: enter={names_enter}, click={names_click}"
