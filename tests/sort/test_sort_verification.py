import time
import unicodedata

import pytest
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from pages.catalog_page import (
    apply_sort_option,
    extract_latest_prices,
    extract_product_names,
    resolve_available_text,
)
from utils.parsers import is_sorted
import logging

LOGGER = logging.getLogger("phongvu-tests-selenium")

pytestmark = pytest.mark.slow


def _safe_str(text: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', str(text or ""))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace("đ", "d").replace("Đ", "D")


# hàm này sẽ kiểm tra xem khi chọn sắp xếp theo giá tăng dần thì giá có được sắp xếp đúng không, và khi chọn sắp xếp theo giá giảm dần thì giá có được sắp xếp đúng không
def test_sort_price_orders(driver, test_config):
    monitor_url = test_config["pages"]["monitor"]
    sort_opts = test_config["test_data"]["sort_options"]
    sort_candidates = test_config["test_data"].get("sort_option_candidates", [])

    driver.get(monitor_url)
    candidate = resolve_available_text(driver, [sort_opts.get("price_asc"), *sort_candidates])
    apply_sort_option(driver, candidate)
    # Ensure we are looking at the listing area (scroll to sort bar) to avoid featured carousels above
    try:
        sort_label = driver.find_element(By.XPATH, "//*[normalize-space()='S\u1eaft x\u1ebfp theo' ]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sort_label)
        time.sleep(0.4)
    except Exception:
        try:
            # fallback: try common Vietnamese label without escaping
            sort_label = driver.find_element(By.XPATH, "//*[normalize-space()='Sắp xếp theo']")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sort_label)
            time.sleep(0.4)
        except Exception:
            pass
    WebDriverWait(driver, 8).until(lambda d: extract_latest_prices(d, test_config, limit=3))

    prices = extract_latest_prices(driver, test_config, limit=10)
    names_asc = extract_product_names(driver, test_config, limit=10)
    print("\n--- [SORT ADVANCED TEST: ASCENDING PRICES] ---")
    for name, price in zip(names_asc, prices):
        print(f"Product: {_safe_str(name)} | Price: {price:,} VND")
    LOGGER.info("DEBUG: prices_asc=%s", prices)
    assert len(prices) >= 3, f"Not enough prices for ascending comparison: {prices}"
    assert is_sorted(prices, ascending=True), f"Prices are not ascending: {prices}"

    candidate_desc = resolve_available_text(
        driver,
        [sort_opts.get("price_desc"), str(sort_opts.get("price_desc", "")).lower(), "Gia giam dan"],
    )
    apply_sort_option(driver, candidate_desc)
    WebDriverWait(driver, 8).until(lambda d: extract_latest_prices(d, test_config, limit=3) != prices[:3])

    prices_desc = extract_latest_prices(driver, test_config, limit=10)
    names_desc = extract_product_names(driver, test_config, limit=10)
    print("\n--- [SORT ADVANCED TEST: DESCENDING PRICES] ---")
    for name, price in zip(names_desc, prices_desc):
        print(f"Product: {_safe_str(name)} | Price: {price:,} VND")
    LOGGER.info("DEBUG: prices_desc=%s", prices_desc)
    assert len(prices_desc) >= 3, f"Not enough prices for descending comparison: {prices_desc}"
    assert is_sorted(prices_desc, ascending=False), f"Prices are not descending: {prices_desc}"


def test_sort_changes_order_for_non_price_options(driver, test_config):
    monitor_url = test_config["pages"]["monitor"]
    sort_opts = test_config["test_data"]["sort_options"]

    driver.get(monitor_url)
    current_names = extract_product_names(driver, test_config, limit=8)
    assert len(current_names) >= 3, f"Not enough baseline products before sort: {current_names}"

    applied_count = 0
    unchanged_options = []
    for key in ("promo_best", "best_selling", "newest"):
        opt_label = sort_opts.get(key)
        if not opt_label:
            continue

        try:
            candidate = resolve_available_text(driver, [opt_label])
            apply_sort_option(driver, candidate)
            applied_count += 1
        except Exception:
            continue

        try:
            WebDriverWait(driver, 8).until(lambda d: extract_product_names(d, test_config, limit=8) != current_names)
        except Exception:
            time.sleep(1)

        after = extract_product_names(driver, test_config, limit=8)
        assert len(after) >= 3, f"Not enough products after applying sort '{opt_label}': {after}"
        if after == current_names:
            unchanged_options.append(opt_label)

        current_names = after

    assert applied_count > 0, (
        "No non-price sort option could be applied: "
        f"{[sort_opts.get(k) for k in ('promo_best', 'best_selling', 'newest')]}"
    )
    assert not unchanged_options, f"Sort options did not change visible order: {unchanged_options}"


def test_sort_switching_between_sort_types_keeps_results_visible(driver, test_config):
    """Switch from a non-price sort to price ascending/descending and verify results remain valid."""
    monitor_url = test_config["pages"]["monitor"]
    sort_opts = test_config["test_data"]["sort_options"]
    sort_candidates = test_config["test_data"].get("sort_option_candidates", [])

    driver.get(monitor_url)

    non_price_candidates = [sort_opts.get("promo_best"), sort_opts.get("best_selling"), sort_opts.get("newest")]
    non_price_candidates = [candidate for candidate in non_price_candidates if candidate]
    if not non_price_candidates:
        pytest.skip("No non-price sort option configured")

    non_price_label = resolve_available_text(driver, non_price_candidates)
    apply_sort_option(driver, non_price_label)
    names_after_non_price = extract_product_names(driver, test_config, limit=8)
    assert names_after_non_price, "No products after applying non-price sort"

    candidate_asc = resolve_available_text(driver, [sort_opts.get("price_asc"), *sort_candidates])
    apply_sort_option(driver, candidate_asc)
    WebDriverWait(driver, 8).until(lambda d: extract_latest_prices(d, test_config, limit=3))
    prices_asc = extract_latest_prices(driver, test_config, limit=10)
    assert len(prices_asc) >= 3, f"Not enough prices after switching to ascending sort: {prices_asc}"
    assert is_sorted(prices_asc, ascending=True), f"Prices are not ascending after switching to ascending sort: {prices_asc}"

    candidate_desc = resolve_available_text(
        driver,
        [sort_opts.get("price_desc"), str(sort_opts.get("price_desc", "")).lower(), "Gia giam dan"],
    )
    apply_sort_option(driver, candidate_desc)
    WebDriverWait(driver, 8).until(lambda d: extract_latest_prices(d, test_config, limit=3) != prices_asc[:3])
    prices_desc = extract_latest_prices(driver, test_config, limit=10)
    assert len(prices_desc) >= 3, f"Not enough prices after switching to descending sort: {prices_desc}"
    assert is_sorted(prices_desc, ascending=False), f"Prices are not descending after switching to descending sort: {prices_desc}"
