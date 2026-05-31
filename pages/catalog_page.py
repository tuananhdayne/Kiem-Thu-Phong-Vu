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


def find_elements_within_results(driver, config, selectors, timeout=10):
    """Find elements inside the main product-results region."""
    scoped_after_sort = _visible_elements_after_sort_bar(driver, selectors, timeout=timeout)
    if scoped_after_sort:
        return scoped_after_sort

    results_selectors = config.get("selectors", {}).get("results_container")
    if results_selectors:
        try:
            container = first_visible(driver, results_selectors, timeout=timeout)
            for selector in selectors:
                elements = container.find_elements(By.CSS_SELECTOR, selector)
                visible_elements = [element for element in elements if element.is_displayed()]
                if visible_elements:
                    return visible_elements
        except Exception:
            pass

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


def _visible_elements_after_sort_bar(driver, selectors, timeout=5):
    """Return listing elements visually below the sort bar, excluding featured blocks above it."""
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            sort_label = _find_sort_label(driver)
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
                matched.sort(key=lambda item: (item[0], item[1]))
                return [item[2] for item in matched]
        except Exception:
            pass
        time.sleep(0.2)
    return []


def get_product_name_elements(driver, config):
    return find_elements_within_results(driver, config, config["selectors"]["product_name"], timeout=3)


def extract_product_names(driver, config, limit=20):
    """Extract unique visible product names from the current listing page."""
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if NO_RESULTS_TEXT in body_text:
            logger.info("No product results are displayed.")
            return []
    except Exception:
        pass

    logger.info("Extracting visible product names...")
    names = []
    for element in get_product_name_elements(driver, config):
        try:
            text = element.text.strip()
            if text and text not in names:
                names.append(text)
        except Exception:
            pass
        if len(names) >= limit:
            break
    logger.info("Extracted %s product names.", len(names))
    return names


def extract_latest_prices(driver, config, limit=20):
    """Extract latest product prices from the current listing page."""
    logger.info("Extracting visible product prices...")
    price_elements = find_elements_within_results(driver, config, config["selectors"]["latest_price"], timeout=3)
    prices = []
    for element in price_elements:
        try:
            price_value = parse_price_to_int(element.text)
            if price_value:
                prices.append(price_value)
        except Exception:
            pass
        if len(prices) >= limit:
            break
    logger.info("Extracted %s prices.", len(prices))
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
        new_names = extract_product_names(driver, config, limit=10)
        brand_count = sum(1 for name in new_names if any(keyword in name.lower() for keyword in keywords))
        if new_names and new_names != old_names and brand_count >= 3:
            logger.info("Product list updated after %.2f seconds.", time.time() - start_time)
            return new_names
        time.sleep(0.25)

    logger.warning("Timed out waiting for product list update after %.2f seconds.", time.time() - start_time)
    return extract_product_names(driver, config, limit=10)


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
        return

    logger.info("Waiting for search results to be ready...")

    def _search_state_ready():
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            names = extract_product_names(driver, config, limit=1)
            return bool(names) or NO_RESULTS_TEXT in body_text or "tim-kiem" in driver.current_url.lower()
        except Exception:
            return False

    start_time = time.time()
    end_time = start_time + timeout
    while time.time() < end_time:
        if _search_state_ready():
            logger.info("Search result state became ready after %.2f seconds.", time.time() - start_time)
            return
        time.sleep(0.25)
    logger.warning("Timed out waiting for a concrete search-result state.")


def resolve_available_text(driver, candidates, timeout=10):
    """Resolve an available sort text from candidate labels."""
    end_time = time.time() + timeout
    available_texts = []

    while time.time() < end_time:
        try:
            remaining = max(0.5, min(2, end_time - time.time()))
            sort_container = _find_sort_container(driver, timeout=remaining)
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


def click_checkbox_by_text(driver, checkbox_text, timeout=10):
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
        time.sleep(0.2)

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

    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
        time.sleep(0.2)
        checkbox.click()
    except Exception:
        driver.execute_script("arguments[0].click();", checkbox)

    logger.info("Clicked checkbox: %s", checkbox_text)
    return checkbox


def apply_sort_option(driver, option_text, timeout=5):
    """Apply a visible sort option."""
    logger.info("Applying sort option: %s", option_text)
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

    logger.info("Applied sort option: %s", option_text)
    return option_node
