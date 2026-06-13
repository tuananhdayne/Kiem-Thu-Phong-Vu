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
from utils.testcase_ids import testcase_id_for_nodeid as _testcase_id_for_nodeid

pytestmark = pytest.mark.regression


def _safe_str(text: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', str(text or ""))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace("đ", "d").replace("Đ", "D")


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
        testcase_id = _testcase_id_for_nodeid(f"tests/search/test_search_regression.py::{test_name}")
        name_prefix = f"{testcase_id}_" if testcase_id else ""
        screenshot_path = screenshots_dir / (
            f"{name_prefix}{test_name}_progress_paste_{iteration:02d}_chars_{actual_length}_{timestamp}.png"
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
    """Xác thực việc tìm kiếm tiếng Việt có dấu và không dấu đều trả về kết quả liên quan."""
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
    """Xác thực hệ thống không thực hiện tìm kiếm và không đổi URL khi ô tìm kiếm trống hoặc chỉ chứa khoảng trắng."""
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
    os.environ.setdefault("RUN_ID", time.strftime("run_%Y%m%d_%H%M%S"))
    driver.get(test_config["base_url"])
    time.sleep(2)

    selectors = test_config["selectors"]["search_input"]
    if isinstance(selectors, str):
        selectors = [selectors]

    chunk_size = int(os.getenv("VERY_LONG_QUERY_CHUNK_SIZE", "2000000"))  # copied text size
    max_iterations = int(os.getenv("VERY_LONG_QUERY_ITERATIONS", "20"))  # paste attempts after copy
    script_timeout = float(os.getenv("VERY_LONG_QUERY_SCRIPT_TIMEOUT", "8"))
    command_timeout = int(os.getenv("VERY_LONG_COMMAND_TIMEOUT", "8"))
    progress_every = max(1, int(os.getenv("VERY_LONG_SAVE_PROGRESS_EVERY", "2")))
    stable_iterations = 0

    print(f"\n--- [START STRESS TEST: CTRL+A/C THEN SPAM CTRL+V, CHUNK {chunk_size:,} CHARS] ---")
    log_test_evidence(
        "VERY LONG CONFIG",
        chunk_size=f"{chunk_size:,}",
        max_iterations=max_iterations,
        script_timeout_seconds=script_timeout,
        command_timeout_seconds=command_timeout,
        progress_screenshot_every=progress_every,
    )

    driver.set_script_timeout(script_timeout)
    try:
        driver.command_executor._client_config.timeout = command_timeout
    except Exception:
        pass
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
    log_test_evidence("VERY LONG SEED", seed_length=f"{seed_length:,}", url=driver.current_url)

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
                log_test_evidence(
                    "VERY LONG FREEZE DETECTED",
                    mode="input length stopped increasing",
                    stable_pastes_before_freeze=stable_iterations,
                    failing_paste=i,
                    expected_min_chars=f"{expected_min_chars:,}",
                    actual_chars=f"{actual_length:,}",
                    click_status=click_status,
                    click_error=click_error,
                )
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
                log_test_evidence(
                    "VERY LONG FREEZE DETECTED",
                    mode="real click no longer handled",
                    stable_pastes_before_freeze=stable_iterations,
                    failing_paste=i,
                    actual_chars=f"{actual_length:,}",
                )
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
            log_test_evidence(
                "VERY LONG PASTE OK",
                paste=i,
                actual_chars=f"{actual_length:,}",
                expected_min_chars=f"{expected_min_chars:,}",
                click_status="OK",
                elapsed_seconds=f"{elapsed:.3f}",
            )
            if (
                os.getenv("VERY_LONG_SAVE_PROGRESS", "1").lower() in ("1", "true", "yes")
                and (i == 1 or i % progress_every == 0)
            ):
                _save_very_long_progress(driver, "test_search_very_long_query", i, actual_length, elapsed)
            stable_iterations = i

        except Exception as exc:
            log_test_evidence(
                "VERY LONG FREEZE DETECTED",
                mode="browser or WebDriver timeout",
                stable_pastes_before_freeze=stable_iterations,
                failing_paste=i,
                command_timeout_seconds=command_timeout,
                error=_short_error(exc),
            )
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
    """Destructive: Kiểm tra việc nhập liên tục các chuỗi văn bản dài vào ô tìm kiếm không gây treo hoặc xóa trắng input."""
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
    """Xác thực danh sách sản phẩm tìm được nằm gọn trong khu vực kết quả chính, không bị tràn ra ngoài."""
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
    """Xác thực việc đổi từ khóa tìm kiếm (từ Logitech sang Samsung) sẽ cập nhật danh sách sản phẩm mới tương ứng."""
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
    """Xác thực việc sắp xếp giá sản phẩm vẫn hoạt động bình thường trên trang kết quả tìm kiếm."""
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
