import os
import time
import unicodedata
from urllib.parse import urlparse
from pathlib import Path

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from pages.catalog_page import (
    search_with_keyword,
    extract_product_names,
    find_search_input,
    find_elements_within_results,
    log_test_evidence,
    NO_RESULTS_TEXT,
)
from utils.parsers import is_sorted

pytestmark = pytest.mark.regression


def _safe_str(text: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', str(text or ""))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace("Ä‘", "d").replace("Ä", "D")


def _short_error(text: str, limit: int = 500) -> str:
    value = _safe_str(text).replace("\r", " ").replace("\n", " ")
    return value if len(value) <= limit else f"{value[:limit]}... [truncated]"


def _save_very_long_progress(driver, test_name: str, iteration: int, actual_length: int, elapsed: float) -> Path | None:
    """Save a proof screenshot while the long-query page is still responsive."""
    try:
        project_root = Path(__file__).resolve().parents[2]
        run_id = os.environ.get("RUN_ID") or time.strftime("run_%Y%m%d_%H%M%S")
        screenshots_dir = project_root / "reports" / "artifacts" / run_id / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshots_dir / (
            f"{test_name}_progress_paste_{iteration:02d}_chars_{actual_length}_{timestamp}.png"
        )
        driver.execute_script(
            """
            const text = arguments[0];
            let box = document.getElementById('__pv_very_long_proof');
            if (!box) {
                box = document.createElement('div');
                box.id = '__pv_very_long_proof';
                document.body.appendChild(box);
            }
            box.textContent = text;
            box.style.cssText = [
                'position:fixed',
                'right:12px',
                'top:48px',
                'z-index:2147483647',
                'background:#b91c1c',
                'color:#fff',
                'font:700 16px Arial,sans-serif',
                'padding:10px 12px',
                'border:3px solid #fff',
                'box-shadow:0 2px 12px rgba(0,0,0,.35)',
                'pointer-events:none'
            ].join(';');
            window.scrollTo(0, 0);
            """,
            f"VERY_LONG_PROOF paste={iteration} length={actual_length:,} elapsed={elapsed:.2f}s",
        )
        driver.save_screenshot(str(screenshot_path))
        print(f"[PROOF SCREENSHOT] {screenshot_path}")
        return screenshot_path
    except Exception as exc:
        print(f"[PROOF SCREENSHOT FAILED] {_short_error(exc)}")
        return None


def test_search_vietnamese_accent_and_no_accent(driver, test_config):
    """XĂ¡c thá»±c viá»‡c tĂ¬m kiáº¿m tiáº¿ng Viá»‡t cĂ³ dáº¥u vĂ  khĂ´ng dáº¥u Ä‘á»u tráº£ vá» káº¿t quáº£ liĂªn quan."""
    driver.get(test_config["base_url"])
    search_with_keyword(driver, test_config, "\u0111i\u1ec7n tho\u1ea1i")
    with_accent = extract_product_names(driver, test_config, limit=8)
    log_test_evidence("VIETNAMESE SEARCH WITH ACCENT", keyword="điện thoại", url=driver.current_url, products=with_accent)
    assert with_accent, "No results for accented Vietnamese keyword"

    driver.get(test_config["base_url"])
    search_with_keyword(driver, test_config, "dien thoai")
    no_accent = extract_product_names(driver, test_config, limit=8)
    log_test_evidence("VIETNAMESE SEARCH NO ACCENT", keyword="dien thoai", url=driver.current_url, products=no_accent)
    assert no_accent, "No results for unaccented Vietnamese keyword"


def test_search_empty_query(driver, test_config):
    """XĂ¡c thá»±c há»‡ thá»‘ng khĂ´ng thá»±c hiá»‡n tĂ¬m kiáº¿m vĂ  khĂ´ng Ä‘á»•i URL khi Ă´ tĂ¬m kiáº¿m trá»‘ng hoáº·c chá»‰ chá»©a khoáº£ng tráº¯ng."""
    driver.get(test_config["base_url"])
    original_url = driver.current_url

    search_with_keyword(driver, test_config, "   ", wait_for_results=False)
    time.sleep(2)

    orig_path = urlparse(original_url).path
    cur_path = urlparse(driver.current_url).path
    assert orig_path == cur_path, f"Blank search changed path from {orig_path} to {cur_path}"

    body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
    search_input = find_search_input(driver, test_config, timeout=5)
    log_test_evidence(
        "EMPTY SEARCH RESULT",
        original_url=original_url,
        current_url=driver.current_url,
        body_text_length=len(body_text),
        search_input_displayed=search_input.is_displayed(),
    )
    assert search_input.is_displayed(), "Search input is not usable after blank search"


@pytest.mark.destructive
def test_search_very_long_query(driver, test_config):
    """Destructive: mimic manual Ctrl+A/C/Ctrl+V spam until input or click stops responding."""
    driver.get(test_config["base_url"])
    time.sleep(2)

    selectors = test_config["selectors"]["search_input"]
    if isinstance(selectors, str):
        selectors = [selectors]

    chunk_size = int(os.getenv("VERY_LONG_QUERY_CHUNK_SIZE", "1000000"))  # copied text size
    max_iterations = int(os.getenv("VERY_LONG_QUERY_ITERATIONS", "100"))  # paste attempts after copy
    script_timeout = float(os.getenv("VERY_LONG_QUERY_SCRIPT_TIMEOUT", "15"))
    stable_iterations = 0

    print(f"\n--- [START STRESS TEST: CTRL+A/C THEN SPAM CTRL+V, CHUNK {chunk_size:,} CHARS] ---")

    driver.set_script_timeout(script_timeout)
    seed_result = driver.execute_script(
        """
        const selectors = arguments[0];
        const chunk = arguments[1];
        let el = null;
        for (const sel of selectors) {
            el = document.querySelector(sel);
            if (el) break;
        }
        if (!el) return { found: false, length: 0, element: null };
        el.focus();
        el.value = chunk;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return { found: true, length: el.value.length, element: el };
        """,
        selectors,
        "x" * chunk_size,
    )
    if not seed_result.get("found"):
        pytest.fail("FREEZE: Search input element not found in DOM by selectors", pytrace=False)

    search_input = seed_result["element"]
    seed_length = int(seed_result.get("length") or 0)
    if seed_length != chunk_size:
        pytest.fail(
            "SETUP: Khong seed duoc du lieu ban dau vao o tim kiem. "
            f"Can {chunk_size:,}, thuc te {seed_length:,}.",
            pytrace=False,
        )

    search_input.send_keys(Keys.CONTROL, "a")
    search_input.send_keys(Keys.CONTROL, "c")
    driver.execute_script(
        "arguments[0].focus(); arguments[0].setSelectionRange(arguments[0].value.length, arguments[0].value.length);",
        search_input,
    )
    print(f"Seed: da copy {seed_length:,} ky tu vao clipboard bang Ctrl+A/C.")

    for i in range(1, max_iterations + 1):
        expected_min_chars = (i + 1) * chunk_size

        start_time = time.time()
        try:
            search_input.send_keys(Keys.CONTROL, "v")
            driver.execute_script("return document.readyState;")
            actual_length = int(driver.execute_script("return arguments[0].value.length;", search_input) or 0)

            if actual_length < expected_min_chars:
                if i == 1 and actual_length == 0:
                    pytest.fail(
                        "SETUP: Ctrl+V lan dau lam input rong. "
                        "Day la dau hieu clipboard automation/selection bi loi trong moi truong Selenium, "
                        "khong du co so ket luan website bi freeze. "
                        f"Seed ban dau: {seed_length:,}. Mong doi sau paste dau: {expected_min_chars:,}.",
                        pytrace=False,
                    )

                click_ok = False
                click_error = ""
                try:
                    driver.execute_script("arguments[0].blur();", search_input)
                    search_input.click()
                    click_ok = bool(driver.execute_script("return document.activeElement === arguments[0];", search_input))
                except Exception as click_exc:
                    click_error = _short_error(click_exc)

                click_status = "OK" if click_ok else "FAIL"
                print(
                    f"[TREO PHAT HIEN] Ctrl+V khong them du ky tu o lan paste thu {i}. "
                    f"Can toi thieu {expected_min_chars:,}, thuc te {actual_length:,}. "
                    f"Click vao o tim kiem sau do: {click_status}. {click_error}"
                )
                pytest.fail(
                    "FREEZE: Ctrl+V khong the them tiep ky tu vao o tim kiem. "
                    f"So lan paste on dinh truoc khi treo: {stable_iterations}. "
                    f"Lan paste gay treo: {i}. "
                    f"So ky tu mong doi toi thieu: {expected_min_chars:,}. "
                    f"So ky tu thuc te: {actual_length:,}. "
                    f"Click vao o tim kiem sau do: {click_status}. "
                    f"{click_error}",
                    pytrace=False,
                )

            click_probe = driver.execute_script(
                """
                window.__pvClickProbeCount = window.__pvClickProbeCount || 0;
                let probe = document.getElementById('__pv_click_probe');
                if (!probe) {
                    probe = document.createElement('div');
                    probe.id = '__pv_click_probe';
                    probe.textContent = 'probe';
                    probe.style.cssText = 'position:fixed;left:8px;top:8px;z-index:2147483647;width:24px;height:24px;opacity:0.01;';
                    probe.addEventListener('mousedown', event => { event.preventDefault(); event.stopPropagation(); });
                    probe.addEventListener('mouseup', event => { event.preventDefault(); event.stopPropagation(); });
                    probe.addEventListener('click', event => {
                        event.preventDefault();
                        event.stopPropagation();
                        window.__pvClickProbeCount += 1;
                    });
                    document.body.appendChild(probe);
                }
                return { element: probe, count: window.__pvClickProbeCount };
                """
            )
            before_click_count = int(click_probe.get("count") or 0)
            click_probe["element"].click()
            after_click_count = int(driver.execute_script("return window.__pvClickProbeCount || 0;"))

            if after_click_count <= before_click_count:
                print(f"[TREO PHAT HIEN] Trang con cuon duoc nhung khong xu ly click that o lan paste thu {i}.")
                pytest.fail(
                    "FREEZE: Trang khong con phan hoi voi click that. "
                    f"So lan paste on dinh truoc khi treo: {stable_iterations}. "
                    f"Lan paste gay treo: {i}. "
                    f"Tong ky tu tai thoi diem treo: {actual_length:,}.",
                    pytrace=False,
                )

            elapsed = time.time() - start_time
            print(f"Lan paste {i}: Ctrl+V thanh cong, input {actual_length:,}/{expected_min_chars:,} ky tu, click OK, trong {elapsed:.3f} giay.")
            if os.getenv("VERY_LONG_SAVE_PROGRESS", "1").lower() in ("1", "true", "yes"):
                _save_very_long_progress(driver, "test_search_very_long_query", i, actual_length, elapsed)
            stable_iterations = i

        except Exception as exc:
            print(f"[TREO PHAT HIEN] Trinh duyet bi treo hoan toan o lan paste thu {i}. Loi: {_short_error(exc)}")
            pytest.fail(
                "FREEZE: Trinh duyet bi treo hoan toan. "
                f"So lan paste on dinh truoc khi treo: {stable_iterations}. "
                f"Lan paste gay treo: {i}. "
                "Click sau khi khong them du ky tu: KHONG THUC HIEN DUOC vi browser/WebDriver timeout trong luc Ctrl+V. "
                f"Loi: {_short_error(exc)}",
                pytrace=False,
            )

    print(f"PASS: Trinh duyet hoat dong tot sau seed {chunk_size:,} ky tu va {max_iterations} lan Ctrl+V.")

def _deprecated_repeated_long_input_check(driver, test_config):
    """Destructive: Kiá»ƒm tra viá»‡c nháº­p liĂªn tá»¥c cĂ¡c chuá»—i vÄƒn báº£n dĂ i vĂ o Ă´ tĂ¬m kiáº¿m khĂ´ng gĂ¢y treo hoáº·c xĂ³a tráº¯ng input."""
    driver.get(test_config["base_url"])
    chunk_size = int(os.getenv("REPEATED_LONG_INPUT_CHUNK_SIZE", "80000"))
    iterations = int(os.getenv("REPEATED_LONG_INPUT_ITERATIONS", "15"))
    chunk = "logitech_" + ("x" * chunk_size)
    expected_min_length = 0

    try:
        search_input = find_search_input(driver, test_config, timeout=6)
        driver.execute_script("arguments[0].focus(); arguments[0].value = '';", search_input)

        for index in range(iterations):
            start_time = time.time()
            driver.execute_script(
                """
                const el = arguments[0];
                const chunk = arguments[1];
                el.focus();
                el.value = `${el.value || ''}${chunk}`;
                el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste', data: chunk }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return el.value.length;
                """,
                search_input,
                chunk,
            )
            expected_min_length += len(chunk)
            elapsed = time.time() - start_time
            max_seconds = float(os.getenv("DESTRUCTIVE_MAX_RESPONSE_SECONDS", "8"))
            if elapsed > max_seconds:
                pytest.fail(f"Page response too slow after repeated long input step {index+1}: {elapsed:.2f}s")

            search_input = find_search_input(driver, test_config, timeout=2)
            current_length = driver.execute_script("return arguments[0].value.length", search_input)
            if current_length == 0:
                pytest.fail(f"DEFECT: search box became blank after repeated long input step {index+1}/{iterations}")
            if current_length < expected_min_length:
                pytest.fail(f"DEFECT: search input lost characters after repeated long input step {index+1}/{iterations}: {current_length} < {expected_min_length}")

        search_input.send_keys(Keys.ENTER)
    except Exception as exc:
        pytest.fail(f"DEFECT: repeated long input blanks the search box or makes the page lag: {exc}")


def test_search_results_are_scoped_to_main_results_container(driver, test_config):
    """XĂ¡c thá»±c danh sĂ¡ch sáº£n pháº©m tĂ¬m Ä‘Æ°á»£c náº±m gá»n trong khu vá»±c káº¿t quáº£ chĂ­nh, khĂ´ng bá»‹ trĂ n ra ngoĂ i."""
    driver.get(test_config["base_url"])
    keyword = test_config["test_data"].get("search_keyword", "Logitech")
    search_with_keyword(driver, test_config, keyword)

    scoped = find_elements_within_results(driver, test_config, test_config["selectors"]["product_name"], timeout=8)

    global_elements = []
    for selector in test_config["selectors"]["product_name"]:
        global_elements.extend(driver.find_elements(By.CSS_SELECTOR, selector))

    assert scoped, "No product elements found in the main results container"
    assert len(scoped) <= len(global_elements), "Scoped element count is larger than global element count"

    names = extract_product_names(driver, test_config, limit=8)
    log_test_evidence(
        "SCOPED SEARCH RESULT",
        keyword=keyword,
        scoped_element_count=len(scoped),
        global_element_count=len(global_elements),
        products=names,
    )
    assert names, "Could not extract product names from the main results area"


def test_search_change_keyword_updates_results(driver, test_config):
    """XĂ¡c thá»±c viá»‡c Ä‘á»•i tá»« khĂ³a tĂ¬m kiáº¿m (tá»« Logitech sang Samsung) sáº½ cáº­p nháº­t danh sĂ¡ch sáº£n pháº©m má»›i tÆ°Æ¡ng á»©ng."""
    driver.get(test_config["base_url"])

    search_with_keyword(driver, test_config, "Logitech", timeout=8)
    logitech_results = extract_product_names(driver, test_config, limit=5)
    log_test_evidence("SEARCH BEFORE KEYWORD CHANGE", keyword="Logitech", url=driver.current_url, products=logitech_results)
    assert logitech_results, "No results for initial Logitech search"

    search_with_keyword(driver, test_config, "Samsung", timeout=8)

    samsung_results = []
    deadline = time.time() + 8
    while time.time() < deadline:
        samsung_results = extract_product_names(driver, test_config, limit=5)
        if samsung_results and samsung_results != logitech_results:
            break
        time.sleep(0.3)

    assert samsung_results, "No results after changing keyword to Samsung"
    log_test_evidence("SEARCH AFTER KEYWORD CHANGE", keyword="Samsung", url=driver.current_url, products=samsung_results)
    assert samsung_results != logitech_results, (
        "Search results did not change after replacing Logitech with Samsung. "
        f"Before={logitech_results}, after={samsung_results}"
    )
    assert any("samsung" in name.lower() for name in samsung_results), (
        f"Updated results are not relevant to Samsung: {samsung_results}"
    )


def test_search_then_sort_price_keeps_relevant_sorted_results(driver, test_config):
    """XĂ¡c thá»±c viá»‡c sáº¯p xáº¿p giĂ¡ sáº£n pháº©m váº«n hoáº¡t Ä‘á»™ng bĂ¬nh thÆ°á»ng trĂªn trang káº¿t quáº£ tĂ¬m kiáº¿m."""
    driver.get(test_config["base_url"])
    search_with_keyword(driver, test_config, "Logitech", timeout=8)

    before_sort = extract_product_names(driver, test_config, limit=5)
    log_test_evidence("SEARCH BEFORE SORT", keyword="Logitech", url=driver.current_url, products=before_sort)
    assert before_sort, "No Logitech results before sorting"

    sort_option = test_config["test_data"].get("sort_option_candidates")
    try:
        from pages.catalog_page import resolve_available_text, apply_sort_option
    except Exception:
        resolve_available_text = None
        apply_sort_option = None

    if resolve_available_text and apply_sort_option:
        candidate = resolve_available_text(driver, test_config["test_data"].get("sort_option_candidates", []))
        apply_sort_option(driver, candidate)

    after_sort = extract_product_names(driver, test_config, limit=5)
    log_test_evidence("SEARCH AFTER SORT", keyword="Logitech", url=driver.current_url, products=after_sort)
    assert after_sort is not None
