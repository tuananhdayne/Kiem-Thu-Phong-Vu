import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from pages.catalog_page import (
    apply_sort_option,
    click_checkbox_by_text,
    extract_latest_prices,
    extract_product_names,
    resolve_available_text,
    wait_products_updated,
)
from utils.parsers import is_sorted

pytestmark = pytest.mark.slow


def test_filter_state_persists_after_reload(driver, test_config):
    """Regression: selected brand filter must persist after page reload."""
    brand = test_config["test_data"]["brand_to_filter"]
    brand_keywords = test_config.get("test_data", {}).get("brand_match_keywords", {}).get(brand, [brand.lower()])
    brand_keywords = [keyword.lower() for keyword in brand_keywords]

    driver.get(test_config["pages"]["laptop"])
    old_names = extract_product_names(driver, test_config, limit=10)

    click_checkbox_by_text(driver, brand)
    WebDriverWait(driver, 12).until(lambda d: "brands=apple" in d.current_url.lower())
    filtered_names = wait_products_updated(driver, test_config, old_names, target_brand=brand, timeout=12)
    assert filtered_names, "No products after applying brand filter"

    driver.refresh()
    WebDriverWait(driver, 12).until(lambda d: "brands=apple" in d.current_url.lower())
    reloaded_names = extract_product_names(driver, test_config, limit=10)
    mismatches = [
        name for name in reloaded_names
        if not any(keyword in name.lower() for keyword in brand_keywords)
    ]

    assert reloaded_names, "No products after reloading filtered page"
    assert not mismatches, f"Filter state was not preserved after reload: {mismatches}"


def test_filter_then_sort_price_keeps_filtered_sorted_results(driver, test_config):
    """Regression: filtered listing must remain filtered after applying ascending price sort."""
    brand = test_config["test_data"]["brand_to_filter"]
    brand_keywords = test_config.get("test_data", {}).get("brand_match_keywords", {}).get(brand, [brand.lower()])
    brand_keywords = [keyword.lower() for keyword in brand_keywords]

    driver.get(test_config["pages"]["laptop"])
    old_names = extract_product_names(driver, test_config, limit=10)
    click_checkbox_by_text(driver, brand)
    WebDriverWait(driver, 12).until(lambda d: "brands=apple" in d.current_url.lower())
    filtered_names = wait_products_updated(driver, test_config, old_names, target_brand=brand, timeout=12)
    assert filtered_names, "No products after applying brand filter"

    sort_option = resolve_available_text(driver, test_config["test_data"]["sort_option_candidates"])
    apply_sort_option(driver, sort_option)

    prices = []
    deadline = time.time() + 8
    while time.time() < deadline:
        prices = extract_latest_prices(driver, test_config, limit=5)
        if len(prices) >= 3 and is_sorted(prices, ascending=True):
            break
        time.sleep(0.3)

    names_after_sort = extract_product_names(driver, test_config, limit=10)
    mismatches = [
        name for name in names_after_sort
        if not any(keyword in name.lower() for keyword in brand_keywords)
    ]

    assert names_after_sort, "No products after filter + sort"
    assert not mismatches, f"Sort lost the selected brand filter: {mismatches}"
    assert len(prices) >= 3, f"Not enough prices after filter + sort: {prices}"
    assert is_sorted(prices, ascending=True), f"Filtered products are not sorted ascending by price: {prices}"
