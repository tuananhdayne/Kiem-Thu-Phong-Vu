import pytest
import time
import unicodedata
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


def _safe_str(text: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', str(text or ""))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace("đ", "d").replace("Đ", "D")


def test_filter_state_persists_after_reload(driver, test_config):
    """Hồi quy: Bộ lọc thương hiệu đã chọn phải được giữ nguyên sau khi người dùng tải lại trang (reload)."""
    brand = test_config["test_data"]["brand_to_filter"]
    brand_keywords = test_config.get("test_data", {}).get("brand_match_keywords", {}).get(brand, [brand.lower()])
    brand_keywords = [keyword.lower() for keyword in brand_keywords]

    driver.get(test_config["pages"]["laptop"])
    old_names = extract_product_names(driver, test_config, limit=10)

    click_checkbox_by_text(driver, brand)
    WebDriverWait(driver, 12).until(lambda d: "brands=apple" in d.current_url.lower())
    filtered_names = wait_products_updated(driver, test_config, old_names, target_brand=brand, timeout=12)
    print("\n--- [FILTER EXTENDED TEST: FILTERED PRODUCTS] ---")
    for i, name in enumerate(filtered_names[:5], 1):
        print(f"{i}. {_safe_str(name)}")
    assert filtered_names, "No products after applying brand filter"

    driver.refresh()
    WebDriverWait(driver, 12).until(lambda d: "brands=apple" in d.current_url.lower())
    reloaded_names = extract_product_names(driver, test_config, limit=10)
    print("\n--- [FILTER EXTENDED TEST: PRODUCTS AFTER RELOAD] ---")
    for i, name in enumerate(reloaded_names[:5], 1):
        print(f"{i}. {_safe_str(name)}")
    mismatches = [
        name for name in reloaded_names
        if not any(keyword in name.lower() for keyword in brand_keywords)
    ]

    assert reloaded_names, "No products after reloading filtered page"
    assert not mismatches, f"Filter state was not preserved after reload: {mismatches}"


def test_filter_then_sort_price_keeps_filtered_sorted_results(driver, test_config):
    """Hồi quy: Danh sách sản phẩm vừa lọc theo thương hiệu phải giữ nguyên bộ lọc sau khi thực hiện sắp xếp giá tăng dần."""
    brand = test_config["test_data"]["brand_to_filter"]
    brand_keywords = test_config.get("test_data", {}).get("brand_match_keywords", {}).get(brand, [brand.lower()])
    brand_keywords = [keyword.lower() for keyword in brand_keywords]

    driver.get(test_config["pages"]["laptop"])
    old_names = extract_product_names(driver, test_config, limit=10)
    click_checkbox_by_text(driver, brand)
    WebDriverWait(driver, 12).until(lambda d: "brands=apple" in d.current_url.lower())
    filtered_names = wait_products_updated(driver, test_config, old_names, target_brand=brand, timeout=12)
    print("\n--- [FILTER + SORT EXTENDED TEST: FILTERED ONLY] ---")
    for i, name in enumerate(filtered_names[:5], 1):
        print(f"{i}. {_safe_str(name)}")
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
    print("\n--- [FILTER + SORT EXTENDED TEST: FILTERED AND SORTED] ---")
    for name, price in zip(names_after_sort[:5], prices[:5]):
        print(f"Product: {_safe_str(name)} | Price: {price:,} VND")
    mismatches = [
        name for name in names_after_sort
        if not any(keyword in name.lower() for keyword in brand_keywords)
    ]

    assert names_after_sort, "No products after filter + sort"
    assert not mismatches, f"Sort lost the selected brand filter: {mismatches}"
    assert len(prices) >= 3, f"Not enough prices after filter + sort: {prices}"
    assert is_sorted(prices, ascending=True), f"Filtered products are not sorted ascending by price: {prices}"
