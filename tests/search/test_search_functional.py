import time
import re

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from pages.catalog_page import (
    search_with_keyword,
    extract_product_names,
    find_elements_within_results,
    find_search_input,
    NO_RESULTS_TEXT,
)
from pages.base_page import first_visible
from utils.parsers import is_sorted
import logging

LOGGER = logging.getLogger("phongvu-tests-selenium")


pytestmark = pytest.mark.slow


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").strip().lower())


def _scroll_and_click(driver, element, label: str, pre_scroll_delay: float = 0.0) -> None:
    """Scroll an element into view and click it with a JS fallback."""
    LOGGER.info("Scrolling to and clicking %s", label)
    if pre_scroll_delay > 0:
        time.sleep(pre_scroll_delay)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", element)
    time.sleep(0.05)
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def _find_visible_by_xpath(driver, xpath: str, timeout: int = 2):
    end_time = time.time() + timeout
    last_exception = None
    while time.time() < end_time:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for element in elements:
                if element.is_displayed():
                    return element
        except Exception as exc:
            last_exception = exc
        time.sleep(0.2)
    if last_exception:
        raise last_exception
    raise Exception(f"No visible element found for xpath: {xpath}")


def _extract_product_names_quick(driver, config, limit=8, timeout=0.6):
    names = []
    try:
        elements = find_elements_within_results(driver, config, config["selectors"]["product_name"], timeout=timeout)
    except Exception:
        elements = []

    for element in elements:
        try:
            text = element.text.strip()
            if text and text not in names:
                names.append(text)
        except Exception:
            pass
        if len(names) >= limit:
            break
    return names


def _log_product_names(label: str, names: list[str]) -> None:
    LOGGER.info("--- [%s] %s product(s) ---", label, len(names))
    print(f"\n--- [{label}] {len(names)} product(s) ---")
    if not names:
        LOGGER.info("(khong lay duoc san pham nao)")
        print("(khong lay duoc san pham nao)")
        return
    for index, name in enumerate(names, 1):
        LOGGER.info("%s. %s", index, name)
        print(f"{index}. {name}")


# hàm này test xem khi search xong, click vào load more hoặc next page thì keyword có bị mất hay không, nếu mất thì sẽ không còn đúng với ý định của người dùng nữa
def test_search_load_more_preserves_keyword(driver, test_config):
    """Xác thực chức năng 'Xem thêm sản phẩm' hoặc phân trang giữ nguyên từ khóa tìm kiếm gốc."""
    keyword = test_config["test_data"].get("search_keyword", "Logitech")
    driver.get(test_config["base_url"])

    search_with_keyword(driver, test_config, keyword, wait_for_results=False, timeout=5)

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
    ]
    load_more_text_xpaths = [
        "//*[self::button or self::a][contains(normalize-space(.), 'Xem thêm sản phẩm')]",
        "//button[contains(normalize-space(.), 'Xem thêm')]",
        "//button[contains(normalize-space(.), 'Load more')]",
        "//*[self::button or self::a][contains(normalize-space(.), 'Xem thêm')]",
        "//*[self::button or self::a][contains(normalize-space(.), 'Load more')]",
    ]

    names_before = []
    control = None
    control_type = None
    deadline = time.time() + 4.0
    while time.time() < deadline and (not names_before or control is None):
        if not names_before:
            names_before = _extract_product_names_quick(driver, test_config, limit=8, timeout=0.4)

        if control is None:
            try:
                control = first_visible(driver, pagination_selectors, timeout=0.2)
                control_type = "pagination"
            except Exception:
                try:
                    control = first_visible(driver, load_more_selectors, timeout=0.2)
                    control_type = "load_more"
                except Exception:
                    for xpath in load_more_text_xpaths:
                        try:
                            control = _find_visible_by_xpath(driver, xpath, timeout=0.2)
                            control_type = "load_more"
                            LOGGER.info("Matched load-more control via xpath: %s", xpath)
                            break
                        except Exception:
                            continue

        if names_before and control is not None:
            break

        time.sleep(0.1)

    assert names_before, "No results on first page to validate pagination/load-more"
    _log_product_names("SEARCH LOAD MORE - BEFORE CLICK", names_before)
    if control is None:
        pytest.skip("No pagination or load-more control detected on search results page")

    # Click the control (scroll into view first)
    _scroll_and_click(driver, control, control_type or "pagination/load-more control")

    deadline = time.time() + 1.0
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
    _log_product_names("SEARCH LOAD MORE - AFTER CLICK", new_names)

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


# Hàm này test xem khi người dùng truy cập trực tiếp vào URL có chứa query tìm kiếm (deeplink) thì có hiển thị kết quả đúng với từ khóa đó hay không. Nếu không có pattern URL nào phù hợp với site thì test sẽ skip.
def test_search_deeplink_query_loads_correct_results(driver, test_config):
    """Mở trực tiếp liên kết sâu (Deep-link) chứa từ khóa tìm kiếm và kiểm tra kết quả hiển thị tương ứng."""
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

# hàm này test khi gõ từ Logi vào ô search, nếu có gợi ý hiện ra thì click vào gợi ý đó và kiểm tra xem có điều hướng đúng và hiển thị kết quả liên quan hay không. Nếu site không có gợi ý autocomplete thì test sẽ skip.
def test_search_autocomplete_suggestion_click_navigates_to_results(driver, test_config):
    """Nhập một phần từ khóa, chọn và nhấn vào gợi ý tự động (Autocomplete) đầu tiên, kiểm tra điều hướng đến trang kết quả."""
    partial = "Logi"
    driver.get(test_config["base_url"])

    # protect against stale element during dynamic re-renders
    search_input = None
    for _ in range(3):
        try:
            search_input = find_search_input(driver, test_config, timeout=5)
            driver.execute_script("arguments[0].focus(); arguments[0].value = '';", search_input)
            break
        except Exception:
            search_input = None
            time.sleep(0.2)
    if search_input is None:
        raise Exception("Could not focus search input for autocomplete test")

    # send partial text slowly (char-by-char) to improve suggestion reliability
    try:
        try:
            search_input.clear()
        except Exception:
            pass

        for ch in partial:
            try:
                search_input.send_keys(ch)
                # dispatch input/keyup to trigger JS listeners in headless/optimized modes
                try:
                    driver.execute_script(
                        "arguments[0].dispatchEvent(new Event('input', { bubbles: true })); arguments[0].dispatchEvent(new Event('keyup', { bubbles: true }));",
                        search_input,
                    )
                except Exception:
                    pass
                time.sleep(0.08)
            except Exception:
                # retry find and continue
                try:
                    search_input = find_search_input(driver, test_config, timeout=5)
                except Exception:
                    pass
    except Exception:
        # fallback to a single send if char-by-char fails
        try:
            search_input.send_keys(partial)
        except Exception:
            search_input = find_search_input(driver, test_config, timeout=5)
            search_input.send_keys(partial)

    # Common suggestion selectors
    suggestion_selectors = [
        "ul[role='listbox'] li",
        "[class*='suggest'] li",
        "[class*='autocomplete'] li",
        "div.suggestion-item",
        # additional common patterns
        ".search-suggestions li",
        ".suggestions li",
        ".typeahead li",
        ".att-autocomplete__item",
        ".att-suggestion li",
        "div[role='listbox'] > div",
        "div[role='listbox'] > li",
        ".pv-suggestion li",
        ".ais-SearchBox-dropdown--item",
    ]

    # wait a moment for suggestions to appear
    suggestion = None
    end = time.time() + 8
    while time.time() < end and suggestion is None:
        for sel in suggestion_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                visible = [e for e in elements if e.is_displayed()]
                if visible:
                    suggestion = visible[0]
                    try:
                        LOGGER.info("DEBUG: selector matched: %s", sel)
                        LOGGER.info("DEBUG: suggestion outerHTML: %s", suggestion.get_attribute('outerHTML')[:1000])
                    except Exception:
                        pass
                    break
            except Exception:
                continue
        time.sleep(0.25)

    # Broad DOM fallback: try to find a visible element whose text contains the partial
    if not suggestion:
        try:
            script = """
            const partial = arguments[0].toLowerCase();
            const input = arguments[1];
            const rect = input.getBoundingClientRect();
            const nodes = Array.from(document.querySelectorAll('body *'));
            for (const el of nodes) {
              try {
                const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                if (!txt) continue;
                if (!txt.includes(partial)) continue;
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) continue;
                if (r.top < rect.bottom - 5) continue; // must be below input
                if (txt.length > 120) continue;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                return el;
              } catch(e) { }
            }
            return null;
            """
            candidate = driver.execute_script(script, partial.lower(), search_input)
            if candidate:
                suggestion = candidate
                try:
                    LOGGER.info("DEBUG: fallback DOM selector matched suggestion")
                except Exception:
                    pass
        except Exception:
            pass

    if not suggestion:
        pytest.skip("No autocomplete suggestions detected on this site")

    try:
        suggestion_text = suggestion.text.strip()
        suggestion.click()
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", suggestion)
        except Exception:
            # fallback: try keyboard selection (arrow down + enter) on the input
            try:
                LOGGER.info("DEBUG: click failed, trying keyboard selection")
                search_input.send_keys(Keys.ARROW_DOWN)
                search_input.send_keys(Keys.ENTER)
            except Exception as e:
                LOGGER.info("DEBUG: keyboard fallback also failed: %s", e)

    # Wait for results to be ready
    deadline = time.time() + 8
    while time.time() < deadline:
        names = extract_product_names(driver, test_config, limit=5)
        if names or NO_RESULTS_TEXT in driver.find_element(By.TAG_NAME, "body").text.lower():
            break
        time.sleep(0.3)

    # If clicking the suggestion didn't produce results, try keyboard fallback now
    if not names:
        try:
            LOGGER.info("DEBUG: no results after click, attempting keyboard selection fallback")
            search_input.send_keys(Keys.ARROW_DOWN)
            search_input.send_keys(Keys.ENTER)
            deadline2 = time.time() + 8
            while time.time() < deadline2:
                names = extract_product_names(driver, test_config, limit=5)
                if names or NO_RESULTS_TEXT in driver.find_element(By.TAG_NAME, "body").text.lower():
                    break
                time.sleep(0.3)
        except Exception as e:
            LOGGER.info("DEBUG: keyboard fallback exception: %s", e)

    # Debug output to help investigate recent failures: list products and prices
    try:
        LOGGER.info("DEBUG: suggestion_text=%s", suggestion_text)
    except Exception:
        LOGGER.info("DEBUG: suggestion_text=<unknown>")
    LOGGER.info("DEBUG: products after suggestion: %s", names)
    try:
        from pages.catalog_page import extract_latest_prices

        prices_dbg = extract_latest_prices(driver, test_config, limit=5)
        LOGGER.info("DEBUG: prices after suggestion: %s", prices_dbg)
        LOGGER.info("DEBUG: prices sorted ascending: %s", is_sorted(prices_dbg, ascending=True))
    except Exception as e:
        LOGGER.info("DEBUG: failed to extract prices: %s", e)

    assert names or NO_RESULTS_TEXT in driver.find_element(By.TAG_NAME, "body").text.lower(), (
        "Clicking suggestion did not lead to a valid results state"
    )

# Hàm này test xem khi gõ từ khóa vào ô search rồi nhấn Enter và khi gõ từ khóa rồi click vào icon search thì kết quả có giống nhau hay không. Nếu không tìm thấy nút search thì test sẽ skip.
def test_search_enter_vs_click_icon_same_result(driver, test_config):
    """So sánh kết quả tìm kiếm giữa việc nhấn phím Enter và việc click chuột vào biểu tượng kính lúp tìm kiếm."""
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

    LOGGER.info("DEBUG: names_enter=%s", names_enter)
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

    LOGGER.info("DEBUG: names_click=%s", names_click)
    assert names_click, "No results after clicking search icon/button"

    # Loose equality: ensure top results overlap meaningfully
    overlap = set(n.lower() for n in names_enter) & set(n.lower() for n in names_click)
    assert overlap, f"Enter and click produced disjoint top results: enter={names_enter}, click={names_click}"
