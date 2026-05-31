import pytest
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from pages.catalog_page import (
    extract_product_names,
    click_checkbox_by_text,
    wait_products_updated,
    search_with_keyword,
)

pytestmark = pytest.mark.slow


def _visible_filter_label_texts(driver, timeout=8):
    """Return visible filter labels with retry to avoid stale nodes."""
    end_time = time.time() + timeout
    labels = []
    while time.time() < end_time:
        labels = []
        for element in driver.find_elements(By.CSS_SELECTOR, "label.check-box"):
            try:
                text = element.text.strip()
                if element.is_displayed() and text:
                    labels.append(text)
            except Exception:
                continue
        if labels:
            return labels
        time.sleep(0.25)
    return labels


def test_filter_all_products_match_brand(driver, test_config):
    base_url = test_config["pages"]["laptop"]
    brand = test_config["test_data"]["brand_to_filter"]

    driver.get(base_url)
    wait = WebDriverWait(driver, 25)

    old_names = extract_product_names(driver, test_config, limit=20)
    click_checkbox_by_text(driver, brand)
    wait.until(lambda d: "brands=apple" in d.current_url.lower())

    new_names = wait_products_updated(driver, test_config, old_names, target_brand=brand, timeout=30)

    assert new_names != old_names, "Danh sách sản phẩm không thay đổi sau khi áp dụng filter"
    
    brand_mapping = test_config.get("test_data", {}).get("brand_match_keywords", {})
    match_keywords = [k.lower() for k in brand_mapping.get(brand, [brand.lower()])]
    mismatches = [n for n in new_names if not any(k in n.lower() for k in match_keywords)]
    assert not mismatches, f"Các sản phẩm không phù hợp filter '{brand}': {mismatches}"


def test_unfilter_restores_list(driver, test_config):
    base_url = test_config["pages"]["laptop"]
    brand = test_config["test_data"]["brand_to_filter"]

    driver.get(base_url)
    wait = WebDriverWait(driver, 25)

    click_checkbox_by_text(driver, brand)
    wait.until(lambda d: "brands=apple" in d.current_url.lower())

    click_checkbox_by_text(driver, brand)

    wait.until(lambda d: "brands=apple" not in d.current_url.lower())

    restored = extract_product_names(driver, test_config, limit=20)
    assert restored, "Danh sách sản phẩm sau khi bỏ lọc rỗng"
    brand_mapping = test_config.get("test_data", {}).get("brand_match_keywords", {})
    match_keywords = [k.lower() for k in brand_mapping.get(brand, [brand.lower()])]
    assert any(not any(k in name.lower() for k in match_keywords) for name in restored), "Danh sách sau khi bỏ lọc vẫn chỉ chứa thương hiệu đã lọc"


def test_filter_combination_no_results(driver, test_config):
    base_url = test_config["pages"]["laptop"]
    brand = test_config["test_data"]["brand_to_filter"]
    nonsense = test_config["test_data"].get("nonexistent_search", "noresults_xyz_98765")

    driver.get(base_url)
    wait = WebDriverWait(driver, 25)

    click_checkbox_by_text(driver, brand)
    wait.until(lambda d: "brands=apple" in d.current_url.lower())

    search_with_keyword(driver, test_config, nonsense)

    body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    assert "không tìm thấy sản phẩm nào" in body_text, "Không hiển thị thông báo no-result sau khi lọc + search"


def test_filter_multiple_conditions_then_remove_one_updates_results(driver, test_config):
    """Apply two visible filters, then remove one and verify the result set updates again."""
    base_url = test_config["pages"]["laptop"]

    driver.get(base_url)
    wait = WebDriverWait(driver, 25)
    wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "label.check-box input[type='checkbox']"))

    old_names = extract_product_names(driver, test_config, limit=10)
    labels = _visible_filter_label_texts(driver)
    assert len(labels) >= 2, "Không đủ filter để kiểm tra việc bỏ một điều kiện"

    first_label, second_label = labels[:2]
    click_checkbox_by_text(driver, first_label)
    click_checkbox_by_text(driver, second_label)
    combined_names = wait_products_updated(driver, test_config, old_names, timeout=12)

    assert combined_names, "Không có sản phẩm sau khi áp dụng 2 filter"
    assert combined_names != old_names, "Danh sách không thay đổi sau khi áp dụng 2 filter"

    click_checkbox_by_text(driver, first_label)
    updated_names = []
    deadline = time.time() + 10
    while time.time() < deadline:
        updated_names = extract_product_names(driver, test_config, limit=10)
        if updated_names and updated_names != combined_names:
            break
        time.sleep(0.3)

    assert updated_names, "Không có sản phẩm sau khi bỏ một filter"
    assert updated_names != combined_names, "Danh sách không đổi sau khi bỏ một filter"
