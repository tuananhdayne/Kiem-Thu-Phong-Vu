import time

import pytest
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

pytestmark = pytest.mark.smoke


def test_filter_apple_brand(driver, test_config):
    driver.get(test_config["pages"]["laptop"])
    wait = WebDriverWait(driver, 10)

    old_names = extract_product_names(driver, test_config, limit=5)
    click_checkbox_by_text(driver, test_config["test_data"]["brand_to_filter"])
    wait.until(lambda d: "brands=apple" in d.current_url.lower())

    new_names = wait_products_updated(driver, test_config, old_names, target_brand="Apple", timeout=10)
    brand_mapping = test_config.get("test_data", {}).get("brand_match_keywords", {})
    match_keywords = [keyword.lower() for keyword in brand_mapping.get("Apple", ["apple", "macbook"])]
    mismatches = [name for name in new_names if not any(keyword in name.lower() for keyword in match_keywords)]

    assert "brands=apple" in driver.current_url.lower()
    assert len(new_names) >= 3, f"Not enough product data after Apple filter: {new_names}"
    assert not mismatches, f"Products do not match Apple filter: {mismatches}. All results: {new_names}"


def test_sort_price_low_to_high(driver, test_config):
    driver.get(test_config["pages"]["laptop"])
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: extract_product_names(d, test_config, limit=1))

    sort_option = resolve_available_text(driver, test_config["test_data"]["sort_option_candidates"])
    apply_sort_option(driver, sort_option)

    wait.until(lambda d: "sort=SORT_BY_PRICE" in d.current_url and "order=ASC" in d.current_url)

    prices = []
    deadline = time.time() + 5
    while time.time() < deadline:
        prices = extract_latest_prices(driver, test_config, limit=5)
        if len(prices) >= 3 and prices == sorted(prices):
            break
        time.sleep(0.4)

    assert "sort=SORT_BY_PRICE" in driver.current_url and "order=ASC" in driver.current_url
    assert len(prices) >= 3, f"Not enough prices after sort: {prices}"
    assert prices == sorted(prices), f"Prices are not ascending: {prices}"


def test_search_logitech(driver, test_config):
    driver.get(test_config["base_url"])

    keyword = test_config["test_data"]["search_keyword"]
    search_with_keyword(driver, test_config, keyword)

    top_results = extract_product_names(driver, test_config, limit=5)
    mismatches = [name for name in top_results if keyword.lower() not in name.lower()]

    assert len(top_results) >= 3, f"Not enough search results for {keyword}: {top_results}"
    assert not mismatches, f"Top results are not scoped to {keyword}: {mismatches}. All results: {top_results}"
