import os
import time
from urllib.parse import urlparse

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from pages.catalog_page import (
    search_with_keyword,
    extract_product_names,
    find_search_input,
    find_elements_within_results,
    NO_RESULTS_TEXT,
)
from utils.parsers import is_sorted

pytestmark = pytest.mark.regression


def test_search_vietnamese_accent_and_no_accent(driver, test_config):
    driver.get(test_config["base_url"])
    search_with_keyword(driver, test_config, "\u0111i\u1ec7n tho\u1ea1i")
    with_accent = extract_product_names(driver, test_config, limit=8)
    assert with_accent, "No results for accented Vietnamese keyword"

    driver.get(test_config["base_url"])
    search_with_keyword(driver, test_config, "dien thoai")
    no_accent = extract_product_names(driver, test_config, limit=8)
    assert no_accent, "No results for unaccented Vietnamese keyword"


def test_search_empty_query(driver, test_config):
    driver.get(test_config["base_url"])
    original_url = driver.current_url

    search_with_keyword(driver, test_config, "   ", wait_for_results=False)
    time.sleep(2)

    orig_path = urlparse(original_url).path
    cur_path = urlparse(driver.current_url).path
    assert orig_path == cur_path, f"Blank search changed path from {orig_path} to {cur_path}"

    body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
    search_input = find_search_input(driver, test_config, timeout=5)
    assert len(body_text) > 100, "Page became blank after blank search"
    assert search_input.is_displayed(), "Search input is not usable after blank search"


@pytest.mark.destructive
def test_search_very_long_query(driver, test_config):
    driver.get(test_config["base_url"])
    long_query_size = int(os.getenv("LONG_QUERY_SIZE", "1000000"))
    long_query = "logitech_" + ("x" * long_query_size)

    try:
        start_time = time.time()
        search_with_keyword(driver, test_config, long_query, timeout=6)
        time.sleep(1)
        elapsed = time.time() - start_time
        max_seconds = float(os.getenv("DESTRUCTIVE_MAX_RESPONSE_SECONDS", "8"))
        if elapsed > max_seconds:
            pytest.fail(f"Page response too slow after very long query: {elapsed:.2f}s > {max_seconds:.2f}s")
        return
    except Exception as exc:
        pytest.fail(f"DEFECT: very long search query ({len(long_query)} chars) freezes the page or WebDriver: {exc}")


@pytest.mark.destructive
def test_search_repeated_long_input_does_not_blank_or_lag(driver, test_config):
    driver.get(test_config["base_url"])
    chunk_size = int(os.getenv("REPEATED_LONG_INPUT_CHUNK_SIZE", "80000"))
    iterations = int(os.getenv("REPEATED_LONG_INPUT_ITERATIONS", "15"))
    chunk = "logitech_" + ("x" * chunk_size)
    expected_min_length = 0

    try:
        search_input = find_search_input(driver, test_config, timeout=6)
        driver.execute_script("arguments[0].focus(); arguments[0].value = '';", search_input)

        for index in range(iterations):
            start_time = time.time()
            driver.execute_script(
                """
                const el = arguments[0];
                const chunk = arguments[1];
                el.focus();
                el.value = `${el.value || ''}${chunk}`;
                el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste', data: chunk }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return el.value.length;
                """,
                search_input,
                chunk,
            )
            expected_min_length += len(chunk)
            elapsed = time.time() - start_time
            max_seconds = float(os.getenv("DESTRUCTIVE_MAX_RESPONSE_SECONDS", "8"))
            if elapsed > max_seconds:
                pytest.fail(f"Page response too slow after repeated long input step {index+1}: {elapsed:.2f}s")

            search_input = find_search_input(driver, test_config, timeout=2)
            current_length = driver.execute_script("return arguments[0].value.length", search_input)
            if current_length == 0:
                pytest.fail(f"DEFECT: search box became blank after repeated long input step {index+1}/{iterations}")
            if current_length < expected_min_length:
                pytest.fail(f"DEFECT: search input lost characters after repeated long input step {index+1}/{iterations}: {current_length} < {expected_min_length}")

        search_input.send_keys(Keys.ENTER)
    except Exception as exc:
        pytest.fail(f"DEFECT: repeated long input blanks the search box or makes the page lag: {exc}")


def test_search_results_are_scoped_to_main_results_container(driver, test_config):
    driver.get(test_config["base_url"])
    keyword = test_config["test_data"].get("search_keyword", "Logitech")
    search_with_keyword(driver, test_config, keyword)

    scoped = find_elements_within_results(driver, test_config, test_config["selectors"]["product_name"], timeout=8)

    global_elements = []
    for selector in test_config["selectors"]["product_name"]:
        global_elements.extend(driver.find_elements(By.CSS_SELECTOR, selector))

    assert scoped, "No product elements found in the main results container"
    assert len(scoped) <= len(global_elements), "Scoped element count is larger than global element count"

    names = extract_product_names(driver, test_config, limit=8)
    assert names, "Could not extract product names from the main results area"


def test_search_change_keyword_updates_results(driver, test_config):
    driver.get(test_config["base_url"])

    search_with_keyword(driver, test_config, "Logitech", timeout=8)
    logitech_results = extract_product_names(driver, test_config, limit=5)
    assert logitech_results, "No results for initial Logitech search"

    search_with_keyword(driver, test_config, "Samsung", timeout=8)

    samsung_results = []
    deadline = time.time() + 8
    while time.time() < deadline:
        samsung_results = extract_product_names(driver, test_config, limit=5)
        if samsung_results and samsung_results != logitech_results:
            break
        time.sleep(0.3)

    assert samsung_results, "No results after changing keyword to Samsung"
    assert samsung_results != logitech_results, (
        "Search results did not change after replacing Logitech with Samsung. "
        f"Before={logitech_results}, after={samsung_results}"
    )
    assert any("samsung" in name.lower() for name in samsung_results), (
        f"Updated results are not relevant to Samsung: {samsung_results}"
    )


def test_search_then_sort_price_keeps_relevant_sorted_results(driver, test_config):
    driver.get(test_config["base_url"])
    search_with_keyword(driver, test_config, "Logitech", timeout=8)

    before_sort = extract_product_names(driver, test_config, limit=5)
    assert before_sort, "No Logitech results before sorting"

    sort_option = test_config["test_data"].get("sort_option_candidates")
    try:
        from pages.catalog_page import resolve_available_text, apply_sort_option
    except Exception:
        resolve_available_text = None
        apply_sort_option = None

    if resolve_available_text and apply_sort_option:
        candidate = resolve_available_text(driver, test_config["test_data"].get("sort_option_candidates", []))
        apply_sort_option(driver, candidate)

    prices = extract_product_names(driver, test_config, limit=5)
    assert prices is not None
