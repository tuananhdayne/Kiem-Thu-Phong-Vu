import time

import pytest
from selenium.webdriver.support.ui import WebDriverWait

from pages.catalog_page import (
    apply_sort_option,
    extract_latest_prices,
    extract_product_names,
    resolve_available_text,
)
from utils.parsers import is_sorted

pytestmark = pytest.mark.slow


def test_sort_price_orders(driver, test_config):
    monitor_url = test_config["pages"]["monitor"]
    sort_opts = test_config["test_data"]["sort_options"]
    sort_candidates = test_config["test_data"].get("sort_option_candidates", [])

    driver.get(monitor_url)

    candidate = resolve_available_text(driver, [sort_opts.get("price_asc"), *sort_candidates])
    apply_sort_option(driver, candidate)
    WebDriverWait(driver, 8).until(lambda d: extract_latest_prices(d, test_config, limit=3))

    prices = extract_latest_prices(driver, test_config, limit=10)
    assert len(prices) >= 3, f"Not enough prices for ascending comparison: {prices}"
    assert is_sorted(prices, ascending=True), f"Prices are not ascending: {prices}"

    candidate_desc = resolve_available_text(
        driver,
        [sort_opts.get("price_desc"), str(sort_opts.get("price_desc", "")).lower(), "Gia giam dan"],
    )
    apply_sort_option(driver, candidate_desc)
    WebDriverWait(driver, 8).until(lambda d: extract_latest_prices(d, test_config, limit=3) != prices[:3])

    prices_desc = extract_latest_prices(driver, test_config, limit=10)
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
