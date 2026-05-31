"""Compatibility facade for the Selenium test framework.

New code should import from pages.* and utils.* modules directly. Existing tests
and dashboard code can continue importing from main while the project is being
refactored incrementally.
"""

from pages.base_page import BasePage, all_visible, first_visible
from pages.catalog_page import (
    CatalogPage,
    apply_sort_option,
    click_checkbox_by_text,
    extract_latest_prices,
    extract_product_names,
    find_elements_within_results,
    find_search_input,
    get_product_name_elements,
    resolve_available_text,
    search_with_keyword,
    wait_products_updated,
)
from utils.artifacts import capture_screenshot
from utils.config_loader import load_config
from utils.logging_utils import configure_logging, ensure_report_directories
from utils.parsers import is_sorted, parse_price_to_int, shorten_for_log as _shorten_for_log
from utils.paths import CONFIG_PATH, PROJECT_ROOT, REPORTS_DIR, SCREENSHOT_DIR

__all__ = [
    "BasePage",
    "CatalogPage",
    "CONFIG_PATH",
    "PROJECT_ROOT",
    "REPORTS_DIR",
    "SCREENSHOT_DIR",
    "_shorten_for_log",
    "all_visible",
    "apply_sort_option",
    "capture_screenshot",
    "click_checkbox_by_text",
    "configure_logging",
    "ensure_report_directories",
    "extract_latest_prices",
    "extract_product_names",
    "find_elements_within_results",
    "find_search_input",
    "first_visible",
    "get_product_name_elements",
    "is_sorted",
    "load_config",
    "parse_price_to_int",
    "resolve_available_text",
    "search_with_keyword",
    "wait_products_updated",
]
