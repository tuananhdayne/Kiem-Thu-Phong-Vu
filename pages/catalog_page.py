import logging
import re
import time
import unicodedata

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.base_page import BasePage, all_visible, first_visible
from utils.parsers import parse_price_to_int, shorten_for_log

logger = logging.getLogger("phongvu-tests-selenium")
NO_RESULTS_TEXT = "kh\u00f4ng t\u00ecm th\u1ea5y s\u1ea3n ph\u1ea9m n\u00e0o"


def _safe_log_text(value, limit=180):
    return shorten_for_log(str(value or "").replace("\r", " ").replace("\n", " "), limit=limit)


def log_test_evidence(label, **fields):
    """Print and log a compact evidence block for pytest reports."""
    header = f"--- [EVIDENCE: {label}] ---"
    print(f"\n{header}")
    logger.info(header)
    if not fields:
        print("(no fields)")
        logger.info("(no fields)")
        return
    for key, value in fields.items():
        if isinstance(value, (list, tuple)):
            print(f"{key}: {len(value)} item(s)")
            logger.info("%s: %s item(s)", key, len(value))
            if not value:
                print("  (empty)")
                logger.info("  (empty)")
            for index, item in enumerate(value, 1):
                line = f"  {index}. {_safe_log_text(item)}"
                print(line)
                logger.info(line)
        else:
            line = f"{key}: {_safe_log_text(value, limit=500)}"
            print(line)
            logger.info(line)


def _normalize_text(text):
    value = unicodedata.normalize("NFD", str(text or ""))
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.replace("\u0111", "d").replace("\u0110", "D")
    return re.sub(r"\s+", " ", value.strip()).lower()


def _find_sort_label(driver, timeout=10):
    end_time = time.time() + timeout
    script = """
    const normalize = (value) => String(value || '')
      .normalize('NFD')
      .replace(/[\\u0300-\\u036f]/g, '')
      .replace(/đ/g, 'd')
      .replace(/Đ/g, 'D')
      .replace(/\\s+/g, ' ')
      .trim()
      .toLowerCase();

    const elements = Array.from(document.querySelectorAll('body *'));
    for (const el of elements) {
      const rects = el.getClientRects();
      if (!rects || rects.length === 0) continue;
      const text = (el.innerText || el.textContent || '').trim();
      if (!text || text.length > 40) continue;
      if (normalize(text) === 'sap xep theo') return el;
    }
    return null;
    """
    while time.time() < end_time:
        try:
            element = driver.execute_script(script)
            if element is not None and element.is_displayed():
                return element
        except Exception:
            pass
        time.sleep(0.2)
    raise Exception("Could not find sort label")


def _find_sort_container(driver, timeout=10):
    sort_label = _find_sort_label(driver, timeout=timeout)
    current = sort_label
    for _ in range(8):
        try:
            normalized = _normalize_text(current.text)
            if "gia tang dan" in normalized and "gia giam dan" in normalized:
                return current
            current = current.find_element(By.XPATH, "./parent::*")
        except Exception:
            break
    return sort_label.find_element(By.XPATH, "./parent::*")


class CatalogPage(BasePage):
    """Page object for category and search-result listing behavior."""

    def product_names(self, limit=20):
        return extract_product_names(self.driver, self.config, limit=limit)

    def latest_prices(self, limit=20):
        return extract_latest_prices(self.driver, self.config, limit=limit)

    def search(self, keyword, wait_for_results=True, timeout=10):
        return search_with_keyword(
            self.driver,
            self.config,
            keyword,
            wait_for_results=wait_for_results,
            timeout=timeout,
        )

    def click_filter(self, text, timeout=10):
        return click_checkbox_by_text(self.driver, text, timeout=timeout)

    def apply_sort(self, option_text, timeout=5):
        return apply_sort_option(self.driver, option_text, timeout=timeout)


def _is_search_result_page(driver):
    try:
        current_url = driver.current_url.lower()
        return "tim-kiem" in current_url or "search" in current_url or "?q=" in current_url
    except Exception:
        return False


def _elements_from_results_container(driver, config, selectors, timeout=10):
    results_selectors = config.get("selectors", {}).get("results_container")
    if not results_selectors:
        return []

    try:
        container = first_visible(driver, results_selectors, timeout=timeout)
        for selector in selectors:
            elements = container.find_elements(By.CSS_SELECTOR, selector)
            visible_elements = [element for element in elements if element.is_displayed()]
            if visible_elements:
                return visible_elements
    except Exception:
        return []

    return []


def find_elements_within_results(driver, config, selectors, timeout=10):
    """Find elements inside the main product-results region."""
    if _is_search_result_page(driver):
        container_elements = _elements_from_results_container(driver, config, selectors, timeout=min(timeout, 1))
        if container_elements:
            return container_elements

    scoped_after_sort = _visible_elements_after_sort_bar(driver, selectors, timeout=timeout)
    if scoped_after_sort:
        return scoped_after_sort

    container_elements = _elements_from_results_container(driver, config, selectors, timeout=min(timeout, 1))
    if container_elements:
        return container_elements

    try:
        sort_container = driver.find_element(By.XPATH, "//*[normalize-space()='S\u1eafp x\u1ebfp theo']/parent::*")
        parent = sort_container.find_element(By.XPATH, "./parent::*")
        following = parent.find_elements(By.XPATH, "./following-sibling::*")
        if not following:
            following = sort_container.find_elements(By.XPATH, "./following-sibling::*")

        for node in following:
            for selector in selectors:
                elements = node.find_elements(By.CSS_SELECTOR, selector)
                visible_elements = [element for element in elements if element.is_displayed()]
                if visible_elements:
                    return visible_elements
    except Exception:
        pass

    return all_visible(driver, selectors, timeout=timeout)


def sort_elements_by_reading_order(elements_with_coords, tolerance=50.0):
    """Sort elements by top-to-bottom, left-to-right reading order with a row tolerance."""
    if not elements_with_coords:
        return []
    # Sort primarily by top coordinate
    sorted_by_top = sorted(elements_with_coords, key=lambda item: item[0])
    
    rows = []
    current_row = []
    current_row_top = None
    
    for item in sorted_by_top:
        top = item[0]
        if current_row_top is None:
            current_row_top = top
            current_row.append(item)
        elif top - current_row_top <= tolerance:
            current_row.append(item)
        else:
            # Sort the completed row by left coordinate
            current_row.sort(key=lambda item: item[1])
            rows.extend(current_row)
            # Start a new row
            current_row = [item]
            current_row_top = top
            
    if current_row:
        current_row.sort(key=lambda item: item[1])
        rows.extend(current_row)
        
    return [item[2] for item in rows]


def _visible_elements_after_sort_bar(driver, selectors, timeout=2):
    """Return listing elements visually below the sort bar, excluding featured blocks above it."""
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            remaining = max(0.2, min(0.6, end_time - time.time()))
            sort_label = _find_sort_label(driver, timeout=remaining)
            sort_rect = driver.execute_script(
                """
                const rect = arguments[0].getBoundingClientRect();
                return { top: rect.top + window.scrollY, bottom: rect.bottom + window.scrollY };
                """,
                sort_label,
            )
            min_y = float(sort_rect["bottom"]) - 2
            matched = []
            seen = set()
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    try:
                        if not element.is_displayed():
                            continue
                        rect = driver.execute_script(
                            """
                            const rect = arguments[0].getBoundingClientRect();
                            return { top: rect.top + window.scrollY, left: rect.left + window.scrollX };
                            """,
                            element,
                        )
                        if float(rect["top"]) <= min_y:
                            continue
                        element_id = element.id
                        if element_id in seen:
                            continue
                        seen.add(element_id)
                        matched.append((float(rect["top"]), float(rect["left"]), element))
                    except Exception:
                        continue
            if matched:
                return sort_elements_by_reading_order(matched)
        except Exception:
            pass
        time.sleep(0.2)
    return []


def get_product_name_elements(driver, config, timeout=3):
    return find_elements_within_results(driver, config, config["selectors"]["product_name"], timeout=timeout)


def _extract_visible_texts_fast(driver, selectors, limit=20, require_after_sort=True):
    """Extract visible texts in one browser-side pass to avoid slow per-element WebDriver calls."""
    try:
        return driver.execute_script(
            """
            const selectors = arguments[0];
            const limit = arguments[1];
            const requireAfterSort = arguments[2];
            const seen = new Set();
            const items = [];
            let minY = -Infinity;

            if (requireAfterSort) {
                const sortNode = document.evaluate(
                    "//*[normalize-space()='Sắp xếp theo']",
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                ).singleNodeValue;
                if (!sortNode) return [];
                const sortRect = sortNode.getBoundingClientRect();
                minY = sortRect.bottom + window.scrollY - 2;
            }

            for (const selector of selectors) {
                for (const el of document.querySelectorAll(selector)) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (!rect || rect.width <= 0 || rect.height <= 0) continue;
                    if ((rect.top + window.scrollY) <= minY) continue;
                    if (style.visibility === 'hidden' || style.display === 'none') continue;
                    const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                    if (!text || seen.has(text)) continue;
                    seen.add(text);
                    items.push({
                        text,
                        top: rect.top + window.scrollY,
                        left: rect.left + window.scrollX,
                    });
                }
                if (items.length >= limit) break;
            }

            items.sort((a, b) => (a.top - b.top) || (a.left - b.left));
            return items.slice(0, limit).map((item) => item.text);
            """,
            selectors,
            int(limit),
            bool(require_after_sort),
        )
    except Exception:
        return []


def extract_product_names(driver, config, limit=20, timeout=3):
    """Extract unique visible product names from the current listing page."""
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if NO_RESULTS_TEXT in body_text:
            logger.info("No product results are displayed.")
            return []
    except Exception:
        pass

    logger.info("Extracting visible product names...")
    fast_selectors = [
        selector for selector in config["selectors"]["product_name"]
        if selector != "[class*='product'] h3"
    ]
    fast_names = _extract_visible_texts_fast(driver, fast_selectors, limit=limit)
    if fast_names:
        logger.info("Extracted %s product names via fast DOM path.", len(fast_names))
        log_test_evidence(
            "PRODUCT NAMES",
            url=driver.current_url,
            count=len(fast_names),
            products=fast_names,
        )
        return fast_names

    names = []
    for element in get_product_name_elements(driver, config, timeout=timeout):
        try:
            text = element.text.strip()
            if text and text not in names:
                names.append(text)
        except Exception:
            pass
        if len(names) >= limit:
            break
    logger.info("Extracted %s product names.", len(names))
    log_test_evidence(
        "PRODUCT NAMES",
        url=driver.current_url,
        count=len(names),
        products=names,
    )
    return names


def extract_latest_prices(driver, config, limit=20, timeout=3):
    """Extract latest product prices from the current listing page."""
    logger.info("Extracting visible product prices...")
    price_elements = find_elements_within_results(driver, config, config["selectors"]["latest_price"], timeout=timeout)
    # Normalize reading order by sorting elements by their page position: top then left
    positioned = []
    for el in price_elements:
        try:
            rect = driver.execute_script(
                "const r = arguments[0].getBoundingClientRect(); return {top: r.top + window.scrollY, left: r.left + window.scrollX};",
                el,
            )
            positioned.append((float(rect.get("top", 0)), float(rect.get("left", 0)), el))
        except Exception:
            positioned.append((float('inf'), float('inf'), el))

    sorted_elements = sort_elements_by_reading_order(positioned)

    prices = []
    for element in sorted_elements:
        try:
            price_value = parse_price_to_int(element.text)
            if price_value:
                prices.append(price_value)
        except Exception:
            pass
        if len(prices) >= limit:
            break

    logger.info("Extracted %s prices.", len(prices))
    log_test_evidence(
        "LATEST PRICES",
        url=driver.current_url,
        count=len(prices),
        prices=[f"{price:,} VND" for price in prices],
    )
    return prices


def wait_products_updated(driver, config, old_names, target_brand="Apple", timeout=5):
    """Wait until the product list changes and has enough brand matches."""
    logger.info("Waiting for product list to update for filter: %s", target_brand)
    if isinstance(target_brand, (list, tuple)):
        keywords = [keyword.lower() for keyword in target_brand]
    else:
        mapping = config.get("test_data", {}).get("brand_match_keywords", {})
        keywords = [keyword.lower() for keyword in mapping.get(target_brand, [target_brand])]

    start_time = time.time()
    end_time = start_time + timeout
    while time.time() < end_time:
        new_names = extract_product_names(driver, config, limit=10, timeout=0.8)
        brand_count = sum(1 for name in new_names if any(keyword in name.lower() for keyword in keywords))
        if new_names and new_names != old_names and brand_count >= 3:
            logger.info("Product list updated after %.2f seconds.", time.time() - start_time)
            return new_names
        time.sleep(0.25)

    logger.warning("Timed out waiting for product list update after %.2f seconds.", time.time() - start_time)
    return extract_product_names(driver, config, limit=10, timeout=0.8)


def find_search_input(driver, config, timeout=5):
    return first_visible(driver, config["selectors"]["search_input"], timeout=timeout)


def search_with_keyword(driver, config, keyword, wait_for_results=True, timeout=10):
    """Search by keyword through the site search input."""
    logger.info("Searching keyword: '%s'", shorten_for_log(keyword, limit=80))
    keyword_str = str(keyword)
    normalized_keyword = keyword_str.strip()
    search_input = None
    last_exc = None

    for _ in range(3):
        try:
            search_input = find_search_input(driver, config, timeout=timeout)
            driver.execute_script("arguments[0].focus();", search_input)
            break
        except StaleElementReferenceException as exc:
            last_exc = exc
            search_input = None
            time.sleep(0.25)

    if search_input is None:
        raise last_exc or Exception("Could not focus search input")

    if len(keyword_str) > 120:
        logger.info("Long query has %s characters; setting value through JS.", len(keyword_str))
        driver.execute_script(
            """
            const el = arguments[0];
            const value = arguments[1];
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            search_input,
            keyword_str,
        )
        search_input = find_search_input(driver, config, timeout=timeout)
        search_input.send_keys(Keys.ENTER)
    else:
        try:
            search_input.clear()
            if normalized_keyword:
                search_input.send_keys(keyword_str)
            search_input.send_keys(Keys.ENTER)
        except StaleElementReferenceException:
            search_input = find_search_input(driver, config, timeout=timeout)
            search_input.clear()
            if normalized_keyword:
                search_input.send_keys(keyword_str)
            search_input.send_keys(Keys.ENTER)

    if not wait_for_results:
        log_test_evidence("SEARCH SUBMITTED", keyword=keyword_str, url=driver.current_url)
        return

    logger.info("Waiting for search results to be ready...")

    def _search_state_ready():
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            names = extract_product_names(driver, config, limit=2)
            return len(names) >= 2 or NO_RESULTS_TEXT in body_text
        except Exception:
            return False

    start_time = time.time()
    end_time = start_time + timeout
    while time.time() < end_time:
        if _search_state_ready():
            logger.info("Search result state became ready after %.2f seconds.", time.time() - start_time)
            log_test_evidence(
                "SEARCH READY",
                keyword=keyword_str,
                url=driver.current_url,
                elapsed_seconds=f"{time.time() - start_time:.2f}",
            )
            return
        time.sleep(0.25)
    logger.warning("Timed out waiting for a concrete search-result state.")
    log_test_evidence("SEARCH WAIT TIMEOUT", keyword=keyword_str, url=driver.current_url)


def resolve_available_text(driver, candidates, timeout=20):
    """Resolve an available sort text from candidate labels."""
    end_time = time.time() + timeout
    available_texts = []

    while time.time() < end_time:
        try:
            remaining = max(0.5, min(2, end_time - time.time()))
            sort_container = _find_sort_container(driver, timeout=remaining)
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                    sort_container,
                )
            except Exception:
                pass
            elements = sort_container.find_elements(By.XPATH, ".//*[normalize-space()]")
            available_texts = []
            for element in elements:
                try:
                    text = element.text.strip()
                    if text and text not in available_texts:
                        available_texts.append(text)
                except Exception:
                    continue
        except Exception:
            available_texts = []

        normalized_texts = [_normalize_text(text) for text in available_texts]
        for candidate in candidates:
            normalized_candidate = _normalize_text(candidate)
            for normalized_text, raw_text in zip(normalized_texts, available_texts):
                if normalized_candidate == normalized_text:
                    return raw_text
            for normalized_text, raw_text in zip(normalized_texts, available_texts):
                if normalized_candidate in normalized_text or normalized_text in normalized_candidate:
                    return raw_text

        time.sleep(0.25)

    raise AssertionError(f"No candidate text found. Candidates: {candidates}. Available: {available_texts}")


def click_checkbox_by_text(driver, checkbox_text, timeout=8, desired_state=None):
    """Click a visible checkbox or checkbox label by display text."""
    logger.info("Clicking filter checkbox: %s", checkbox_text)
    checkbox_xpath = (
        f"//label[contains(@class, 'check-box') and contains(., '{checkbox_text}')]//input[@type='checkbox']"
        f" | //input[@type='checkbox' and @aria-label='{checkbox_text}']"
        f" | //label[contains(., '{checkbox_text}')]//input[@type='checkbox']"
    )

    start_time = time.time()
    checkbox = None
    while time.time() - start_time < timeout:
        try:
            elements = driver.find_elements(By.XPATH, checkbox_xpath)
            for element in elements:
                if element.is_displayed():
                    checkbox = element
                    break
            if checkbox:
                break
        except Exception:
            pass
        time.sleep(0.05)

    if not checkbox:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, "label.check-box")
            for element in elements:
                if element.is_displayed() and checkbox_text.lower() in element.text.lower():
                    checkbox = element
                    break
        except Exception:
            pass

    if not checkbox:
        try:
            elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{checkbox_text}')]")
            for element in elements:
                if not element.is_displayed():
                    continue
                tag_name = element.tag_name.upper()
                if tag_name == "A" or element.find_elements(By.XPATH, "./ancestor::a"):
                    continue
                checkbox = element
                break
        except Exception:
            pass

    if not checkbox:
        raise Exception(f"Could not find checkbox or label containing: {checkbox_text}")

    def _target_for_click(element):
        try:
            if element.tag_name.lower() == "input":
                labels = element.find_elements(By.XPATH, "./ancestor::label[1]")
                if labels:
                    return labels[0]
        except Exception:
            pass
        return element

    def _is_checked(element):
        try:
            if element.tag_name.lower() == "input":
                return element.is_selected()
            inputs = element.find_elements(By.XPATH, ".//input[@type='checkbox']")
            return any(item.is_selected() for item in inputs)
        except StaleElementReferenceException:
            return True
        except Exception:
            return False

    def _click_once(element, use_js=False):
        target = _target_for_click(element)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        time.sleep(0.1)
        if use_js:
            driver.execute_script("arguments[0].click();", target)
        else:
            target.click()

    original_url = driver.current_url
    last_error = None
    for attempt in range(1, 4):
        try:
            _click_once(checkbox, use_js=True)
            end_time = time.time() + min(2.5, max(1, timeout / 3))
            while time.time() < end_time:
                try:
                    checked = _is_checked(checkbox)
                    state_ok = checked if desired_state is None else checked == desired_state
                    if state_ok or driver.current_url != original_url:
                        logger.info("Clicked checkbox: %s", checkbox_text)
                        return checkbox
                except StaleElementReferenceException:
                    logger.info("Clicked checkbox: %s", checkbox_text)
                    return checkbox
                time.sleep(0.15)
        except Exception as exc:
            last_error = exc
            try:
                driver.execute_script("arguments[0].click();", _target_for_click(checkbox))
            except Exception as js_exc:
                last_error = js_exc
        time.sleep(0.25)

    raise Exception(
        f"Clicked checkbox label but state/url did not change for: {checkbox_text}. "
        f"Current URL: {driver.current_url}. Last error: {last_error}"
    )


def apply_sort_option(driver, option_text, timeout=5):
    """Apply a visible sort option."""
    logger.info("Applying sort option: %s", option_text)
    original_url = driver.current_url
    start_time = time.time()
    sort_container = None
    while time.time() - start_time < timeout:
        try:
            sort_container = _find_sort_container(driver)
            if sort_container.is_displayed():
                break
        except Exception:
            pass
        time.sleep(0.25)

    if not sort_container:
        raise Exception("Could not find sort container")

    option_node = None
    nodes = sort_container.find_elements(By.XPATH, ".//*[normalize-space()]")

    for node in nodes:
        try:
            if node.is_displayed() and _normalize_text(node.text) == _normalize_text(option_text):
                option_node = node
                break
        except Exception:
            pass

    if not option_node:
        for node in nodes:
            try:
                node_text = _normalize_text(node.text)
                requested_text = _normalize_text(option_text)
                if node.is_displayed() and (requested_text in node_text or node_text in requested_text):
                    option_node = node
                    break
            except Exception:
                pass

    if not option_node:
        available = [node.text.strip() for node in nodes if node.text.strip()]
        raise AssertionError(f"Sort option not found: {option_text}. Available: {available}")

    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", option_node)
        time.sleep(0.2)
        option_node.click()
    except Exception:
        driver.execute_script("arguments[0].click();", option_node)

    normalized_option = _normalize_text(option_text)
    expected_query_parts = []
    if "gia tang dan" in normalized_option or "gia thap den cao" in normalized_option:
        expected_query_parts = ["sort=SORT_BY_PRICE", "order=ASC"]
    elif "gia giam dan" in normalized_option or "gia cao den thap" in normalized_option:
        expected_query_parts = ["sort=SORT_BY_PRICE", "order=DESC"]
    elif "khuyen mai" in normalized_option:
        expected_query_parts = ["sort=SORT_BY_DISCOUNT_PERCENT", "order=DESC"]
    elif "ban chay" in normalized_option:
        expected_query_parts = ["sort=SORT_BY_TOP_SALE_QUANTITY_7_DAYS", "order=DESC"]

    end_time = time.time() + max(3, timeout)
    applied_url = original_url
    while time.time() < end_time:
        try:
            applied_url = driver.current_url
            if expected_query_parts:
                if all(part.lower() in applied_url.lower() for part in expected_query_parts):
                    logger.info("Applied sort option: %s | url=%s", option_text, applied_url)
                    return option_node
            elif applied_url != original_url:
                logger.info("Applied sort option: %s | url=%s", option_text, applied_url)
                return option_node
        except Exception:
            pass
        time.sleep(0.2)

    if not expected_query_parts:
        # Some sort controls update the listing without changing the URL.
        logger.info("Applied sort option without URL confirmation: %s | url=%s", option_text, applied_url)
        return option_node

    raise AssertionError(
        f"Sort option was clicked but not applied: '{option_text}'. "
        f"Expected URL parts: {expected_query_parts}. Original URL: {original_url}. Current URL: {applied_url}"
    )
