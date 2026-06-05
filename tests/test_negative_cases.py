import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from pages.base_page import first_visible

pytestmark = [pytest.mark.slow, pytest.mark.framework]


def test_missing_selector_raises(driver, test_config):
    """Framework: Kiểm tra xem hàm first_visible có ném ra ngoại lệ chính xác khi selector không tồn tại hay không."""
    with pytest.raises(Exception):
        first_visible(driver, [".this-selector-does-not-exist-xyz"], timeout=3)


def test_slow_page_timeout(driver, test_config):
    """Framework: Kiểm tra xem WebDriverWait có ném ra ngoại lệ timeout chính xác khi phần tử không xuất hiện hay không."""
    with pytest.raises(Exception):
        WebDriverWait(driver, 2).until(lambda d: d.find_element(By.CSS_SELECTOR, ".nonexistent-element-abc"))
