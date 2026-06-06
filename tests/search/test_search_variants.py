import pytest
import re
import logging
from selenium.webdriver.common.by import By
from pages.catalog_page import extract_product_names, search_with_keyword

pytestmark = pytest.mark.slow
LOGGER = logging.getLogger("phongvu-tests-selenium")


def _print_search_results(label, keyword, names):
    header = f"--- [SEARCH RESULTS: {label}] keyword={keyword!r} ---"
    print(f"\n{header}")
    LOGGER.info(header)
    if not names:
        print("(khong lay duoc san pham nao)")
        LOGGER.info("(khong lay duoc san pham nao)")
        return
    for index, name in enumerate(names, 1):
        line = f"{index}. {name}"
        print(line)
        LOGGER.info(line)


@pytest.mark.parametrize("variant", [
    "logitech",
    "Logitech",
    "  Logitech  ",
    "Logitech!@#",
])
def test_search_variants_returns_relevant_results(driver, test_config, variant):
    base_url = test_config["base_url"]
    driver.get(base_url)

    search_with_keyword(driver, test_config, variant)

    top = extract_product_names(driver, test_config, limit=5)
    _print_search_results("variant", variant, top)
    assert top, f"Không có kết quả cho tìm kiếm '{variant}'"
    normalized = re.sub(r"[^a-z0-9]+", "", variant.strip().lower())
    assert any(normalized in t.lower() for t in top), f"Kết quả không liên quan tới '{variant}': {top}"


@pytest.mark.parametrize("typo", [
    "Logitec",
    "Logit ech",
    "Logitechk",
    "Logtech",
    "Logit3ch",
])
def test_search_typo_tolerance_returns_relevant_results(driver, test_config, typo):
    base_url = test_config["base_url"]
    driver.get(base_url)

    search_with_keyword(driver, test_config, typo)

    top = extract_product_names(driver, test_config, limit=5)
    _print_search_results("typo", typo, top)
    assert top, f"Không có kết quả cho tìm kiếm lỗi chính tả '{typo}'"
    assert any("logit" in name.lower() for name in top), f"Kết quả không liên quan tới '{typo}': {top}"


def test_search_not_found_shows_no_results(driver, test_config):
    base_url = test_config["base_url"]
    driver.get(base_url)

    search_with_keyword(driver, test_config, "nonexistentsku12345")

    body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    assert "không tìm thấy sản phẩm nào" in body_text, "Dự kiến hiển thị thông báo no-result"
