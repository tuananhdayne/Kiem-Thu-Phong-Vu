import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from pytest_html import extras
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from utils.artifacts import capture_screenshot
from utils.config_loader import load_config
from utils.logging_utils import configure_logging
from utils.testcase_ids import testcase_conclusion_for_nodeid, testcase_id_for_nodeid, testcase_meta_for_nodeid

# Use a consistent logger name across the project
LOGGER = logging.getLogger("phongvu-tests-selenium")
_WORKER_BROWSER = {"browser": None, "user_data_dir": None, "chromedriver_pid": None}
_SELENIUM_CHROMEDRIVER_PIDS = set()


def _console_safe(value):
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return str(value).encode(encoding, errors="replace").decode(encoding, errors="replace")


def _safe_artifact_stem(node, suffix):
    testcase_id = testcase_id_for_nodeid(node.nodeid)
    raw_name = f"{node.name}_{suffix}"
    if testcase_id:
        raw_name = f"{testcase_id}_{raw_name}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_name).strip("_") or "artifact"


def _kill_windows_process_tree(pid):
    """Best-effort cleanup for Selenium-owned Chrome/ChromeDriver processes."""
    if not pid or os.name != "nt":
        return

    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        LOGGER.warning("Failed to kill Selenium process tree PID %s: %s", pid, exc)


def _register_chromedriver_pid(pid):
    if pid:
        _SELENIUM_CHROMEDRIVER_PIDS.add(pid)


def _unregister_chromedriver_pid(pid):
    if pid:
        _SELENIUM_CHROMEDRIVER_PIDS.discard(pid)


def _kill_registered_selenium_processes():
    for pid in list(_SELENIUM_CHROMEDRIVER_PIDS):
        LOGGER.info("Final cleanup: killing Selenium ChromeDriver process tree PID %s.", pid)
        _kill_windows_process_tree(pid)
        _unregister_chromedriver_pid(pid)


def pytest_configure(config):
    """Cấu hình pytest: thiết lập logging cho toàn bộ test suite."""
    if getattr(config.option, "collectonly", False):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        configure_logging()
    LOGGER.info("selenium-pytest configured: logging initialized")


def pytest_addoption(parser):
    parser.addoption(
        "--run-destructive",
        action="store_true",
        default=False,
        help="Run resource-heavy browser stress tests marked as destructive.",
    )
    parser.addoption(
        "--run-security",
        action="store_true",
        default=False,
        help="Run black-box security payload tests marked as security.",
    )


def pytest_collection_modifyitems(config, items):
    skip_destructive = pytest.mark.skip(reason="destructive test skipped; pass --run-destructive to run it")
    skip_security = pytest.mark.skip(reason="security payload test skipped; pass --run-security to run it")
    for item in items:
        testcase_meta = testcase_meta_for_nodeid(item.nodeid)
        if testcase_meta:
            item.user_properties.append(("test_case_id", testcase_meta["id"]))
            if testcase_meta.get("title"):
                item.user_properties.append(("test_case_title", testcase_meta["title"]))
        if "destructive" in item.keywords and not config.getoption("--run-destructive"):
            item.add_marker(skip_destructive)
        if "security" in item.keywords and not config.getoption("--run-security"):
            item.add_marker(skip_security)


def pytest_runtest_setup(item):
    """Ghi log khi một test bắt đầu."""
    testcase_meta = testcase_meta_for_nodeid(item.nodeid)
    if testcase_meta:
        title = _console_safe(testcase_meta.get("title") or item.name)
        LOGGER.info("TEST CASE ID: %s | %s | nodeid=%s", testcase_meta["id"], title, item.nodeid)
        print(f"\n=== TEST CASE ID: {testcase_meta['id']} | {title} ===")
    LOGGER.info("START TEST: %s", item.name)


def pytest_runtest_teardown(item, nextitem):
    """Ghi log khi một test kết thúc."""
    report = getattr(item, "rep_call", None)
    if report is not None:
        if report.passed:
            status = "PASS"
        elif report.failed:
            status = "FAIL"
        elif report.skipped:
            status = "SKIP"
        else:
            status = "UNKNOWN"

        conclusion = testcase_conclusion_for_nodeid(item.nodeid, status)
        if conclusion:
            safe_conclusion = _console_safe(conclusion)
            LOGGER.info("TEST CASE CONCLUSION: %s", safe_conclusion)
            print(f"\n=== TEST CASE CONCLUSION: {safe_conclusion} ===")
    LOGGER.info("END TEST: %s", item.name)


@pytest.fixture(scope="session")
def test_config():
    """Fixture phiên làm việc: tải cấu hình test từ file config.json."""
    return load_config()


def _create_isolated_chrome_driver():
    """Create a Chrome WebDriver that is isolated from the shared session browser."""
    chrome_options = Options()
    user_data_dir = tempfile.mkdtemp(prefix="phongvu_selenium_chrome_")

    chrome_options.page_load_strategy = "eager"
    if os.getenv("SELENIUM_HEADLESS", "0") == "1":
        chrome_options.add_argument("--headless=new")

    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    block_images = os.getenv("SELENIUM_BLOCK_IMAGES", "1")
    if str(block_images).lower() in ("0", "false", "no", "off"):
        prefs = {"profile.managed_default_content_settings.images": 1}
    else:
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)

    try:
        chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    except Exception:
        pass
    browser = webdriver.Chrome(options=chrome_options)
    command_timeout = int(os.getenv("SELENIUM_COMMAND_TIMEOUT", "30"))
    try:
        browser.command_executor._client_config.timeout = command_timeout
        LOGGER.info("SELENIUM_COMMAND_TIMEOUT=%s", command_timeout)
    except Exception as exc:
        LOGGER.warning("Failed to configure Selenium command timeout: %s", exc)

    try:
        browser.execute_cdp_cmd("Network.enable", {})
        browser.execute_cdp_cmd(
            "Network.setBlockedURLs",
            {
                "urls": [
                    "*google-analytics*",
                    "*googletagmanager*",
                    "*doubleclick.net*",
                    "*facebook.com/tr*",
                    "*facebook.net*",
                    "*tiktok.com*",
                    "*hotjar.com*",
                    "*clarity.ms*",
                ]
            },
        )
        LOGGER.info("CDP Network blocking enabled: tracking/analytics URLs blocked.")
    except Exception as exc:
        LOGGER.warning("Failed to enable CDP network blocking: %s", exc)

    browser.implicitly_wait(0)
    browser.maximize_window()
    try:
        browser._base_window_handle = browser.current_window_handle
    except Exception:
        browser._base_window_handle = None

    try:
        chromedriver_pid = browser.service.process.pid
    except Exception:
        chromedriver_pid = None
    _register_chromedriver_pid(chromedriver_pid)
    _register_chromedriver_pid(chromedriver_pid)

    return browser, user_data_dir, chromedriver_pid


def _cleanup_isolated_chrome_driver(browser, user_data_dir, chromedriver_pid, quit_browser=True):
    if quit_browser and browser is not None:
        try:
            browser.quit()
        except Exception:
            pass
    _kill_windows_process_tree(chromedriver_pid)
    _unregister_chromedriver_pid(chromedriver_pid)
    try:
        shutil.rmtree(user_data_dir, ignore_errors=True)
    except Exception as exc:
        LOGGER.warning("Failed to remove Chrome temp profile %s: %s", user_data_dir, exc)


def _worker_browser_alive(browser):
    try:
        _ = browser.current_window_handle
        return True
    except Exception:
        return False


def _get_worker_browser():
    browser = _WORKER_BROWSER.get("browser")
    if browser is not None and _worker_browser_alive(browser):
        return browser

    _reset_worker_browser(quit_browser=False)
    browser, user_data_dir, chromedriver_pid = _create_isolated_chrome_driver()
    _WORKER_BROWSER.update(
        {"browser": browser, "user_data_dir": user_data_dir, "chromedriver_pid": chromedriver_pid}
    )
    LOGGER.info("Created worker-local ChromeDriver for this pytest worker.")
    return browser


def _reset_worker_browser(quit_browser=True):
    browser = _WORKER_BROWSER.get("browser")
    user_data_dir = _WORKER_BROWSER.get("user_data_dir")
    chromedriver_pid = _WORKER_BROWSER.get("chromedriver_pid")
    if browser is not None or chromedriver_pid is not None or user_data_dir is not None:
        _cleanup_isolated_chrome_driver(browser, user_data_dir, chromedriver_pid, quit_browser=quit_browser)
    _WORKER_BROWSER.update({"browser": None, "user_data_dir": None, "chromedriver_pid": None})


@pytest.fixture(scope="session")
def browser_session():
    """Fixture phiên làm việc: khởi tạo và quản lý Chrome WebDriver duy nhất.

    Giúp giảm thời gian chạy test suite bằng cách tái sử dụng trình duyệt cho tất cả các test.
    """
    chrome_options = Options()
    user_data_dir = tempfile.mkdtemp(prefix="phongvu_selenium_chrome_")

    # Thiết lập chiến lược tải trang eager (trả quyền điều khiển ngay khi DOMContentLoaded kích hoạt)
    chrome_options.page_load_strategy = "eager"

    # Thiết lập headless mode
    if os.getenv("SELENIUM_HEADLESS", "0") == "1":
        chrome_options.add_argument("--headless=new")

    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    # Vô hiệu hóa tải ảnh để tăng tốc khi chạy Selenium Chrome.
    # 2 = Block images
    # Mặc định repo trước đó chặn ảnh để tăng tốc; giờ cho phép điều khiển
    # qua biến môi trường SELENIUM_BLOCK_IMAGES (0 = allow, 1 = block)
    block_images = os.getenv("SELENIUM_BLOCK_IMAGES", "1")
    try:
        if str(block_images).lower() in ("0", "false", "no", "off"):
            prefs = {"profile.managed_default_content_settings.images": 1}
        else:
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")
            prefs = {"profile.managed_default_content_settings.images": 2}
    except Exception:
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)

    # Bật logging console từ Chrome để có thể thu thập console logs
    try:
        chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    except Exception:
        pass

    browser = webdriver.Chrome(options=chrome_options)
    command_timeout = int(os.getenv("SELENIUM_COMMAND_TIMEOUT", "30"))
    try:
        browser.command_executor._client_config.timeout = command_timeout
        LOGGER.info("SELENIUM_COMMAND_TIMEOUT=%s", command_timeout)
    except Exception as exc:
        LOGGER.warning("Failed to configure Selenium command timeout: %s", exc)

    chromedriver_pid = None
    try:
        chromedriver_pid = browser.service.process.pid
    except Exception:
        chromedriver_pid = None

    # Log current environment settings to help debugging why browser may be headless
    try:
        LOGGER.info("SELENIUM_HEADLESS=%s", os.getenv("SELENIUM_HEADLESS", "0"))
        LOGGER.info("SELENIUM_BLOCK_IMAGES=%s", os.getenv("SELENIUM_BLOCK_IMAGES", "1"))
        LOGGER.info("RUN_ID=%s", os.getenv("RUN_ID", "-"))
        LOGGER.info("GIT_COMMIT=%s", os.getenv("GIT_COMMIT", "-"))
    except Exception:
        pass

    # Kích hoạt CDP Network blocking để chặn tracker quảng cáo (KHÔNG chặn ảnh vì prefs đã xử lý)
    try:
        browser.execute_cdp_cmd("Network.enable", {})
        browser.execute_cdp_cmd(
            "Network.setBlockedURLs",
            {
                "urls": [
                    "*google-analytics*",
                    "*googletagmanager*",
                    "*doubleclick.net*",
                    "*facebook.com/tr*",
                    "*facebook.net*",
                    "*tiktok.com*",
                    "*hotjar.com*",
                    "*clarity.ms*",
                ]
            },
        )
        LOGGER.info("CDP Network blocking enabled: tracking/analytics URLs blocked.")
    except Exception as exc:
        LOGGER.warning("Failed to enable CDP network blocking: %s", exc)

    # Thiết lập timeout từ biến môi trường (mặc định tắt implicit wait để không xung đột với explicit wait)
    browser.implicitly_wait(0)
    browser.maximize_window()

    try:
        browser._base_window_handle = browser.current_window_handle
    except Exception:
        browser._base_window_handle = None

    try:
        yield browser
    finally:
        fast_shutdown = os.getenv("SELENIUM_FAST_SHUTDOWN", "1").lower() in ("1", "true", "yes", "on")
        if fast_shutdown and os.name == "nt":
            LOGGER.info("Fast Selenium shutdown enabled; killing ChromeDriver process tree.")
            _kill_windows_process_tree(chromedriver_pid)
            _unregister_chromedriver_pid(chromedriver_pid)
        else:
            try:
                for handle in list(browser.window_handles):
                    try:
                        browser.switch_to.window(handle)
                        browser.close()
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                browser.quit()
            except Exception as exc:
                LOGGER.exception("Failed to quit browser: %s", exc)

            _kill_windows_process_tree(chromedriver_pid)
            _unregister_chromedriver_pid(chromedriver_pid)

        try:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception as exc:
            LOGGER.warning("Failed to remove Chrome temp profile %s: %s", user_data_dir, exc)


@pytest.fixture
def driver(request):
    """Fixture để cung cấp browser instance cho mỗi test và chụp screenshot khi lỗi.

    Tái sử dụng browser_session để tối ưu tốc độ chạy test.
    """
    isolate_each_test = os.getenv("SELENIUM_ISOLATE_EACH_TEST", "0").lower() in ("1", "true", "yes", "on")
    isolate_worker_browser = os.getenv("SELENIUM_WORKER_BROWSER", "0").lower() in ("1", "true", "yes", "on")
    owns_browser = isolate_each_test
    uses_worker_browser = isolate_worker_browser and not owns_browser
    user_data_dir = None
    chromedriver_pid = None
    if owns_browser:
        browser_session, user_data_dir, chromedriver_pid = _create_isolated_chrome_driver()
        LOGGER.info("Using isolated ChromeDriver for test: %s", request.node.name)
    elif uses_worker_browser:
        browser_session = _get_worker_browser()
        LOGGER.info("Using worker-local ChromeDriver for test: %s", request.node.name)
    else:
        browser_session = request.getfixturevalue("browser_session")

    test_window_handle = None
    if not owns_browser:
        try:
            browser_session.switch_to.new_window("tab")
            test_window_handle = browser_session.current_window_handle
        except Exception as exc:
            LOGGER.warning("Failed to open dedicated tab for %s: %s", request.node.name, exc)

    yield browser_session

    # After test execution: save artifacts on failure (always) and optionally on pass
    try:
        rep = getattr(request.node, "rep_call", None)
        passed = bool(rep and rep.passed)
        failed = bool(rep and rep.failed)
    except Exception:
        passed = False
        failed = False

    def _save_page_source(suffix: str):
        try:
            # Save artifacts under reports/artifacts/<RUN_ID>/pages/
            project_root = Path(__file__).resolve().parent
            reports_dir = project_root / "reports"
            run_id = os.environ.get("RUN_ID") or time.strftime("run_%Y%m%d_%H%M%S")
            pages_dir = reports_dir / "artifacts" / run_id / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            safe_name = _safe_artifact_stem(request.node, suffix)
            file_path = pages_dir / f"{safe_name}_{timestamp}.html"
            file_path.write_text(browser_session.page_source, encoding="utf-8")
            LOGGER.info("Saved page source: %s", file_path)
            return file_path
        except Exception as exc:
            LOGGER.exception("Failed to save page source: %s", exc)
            return None

    def _save_console_logs(suffix: str):
        try:
            # Save console logs under reports/artifacts/<RUN_ID>/console/
            project_root = Path(__file__).resolve().parent
            reports_dir = project_root / "reports"
            run_id = os.environ.get("RUN_ID") or time.strftime("run_%Y%m%d_%H%M%S")
            logs_dir = reports_dir / "artifacts" / run_id / "console"
            logs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            safe_name = _safe_artifact_stem(request.node, suffix)
            file_path = logs_dir / f"{safe_name}_{timestamp}_console.json"
            logs = []
            try:
                logs = browser_session.get_log("browser")
            except Exception:
                pass
            file_path.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")
            LOGGER.info("Saved console logs: %s", file_path)
            return file_path
        except Exception as exc:
            LOGGER.exception("Failed to save console logs: %s", exc)
            return None

    try:
        if failed:
            try:
                skip_webdriver_artifacts = "destructive" in request.node.keywords and os.getenv(
                    "SELENIUM_CAPTURE_DESTRUCTIVE_ARTIFACTS", "0"
                ) != "1"
                if skip_webdriver_artifacts:
                    LOGGER.error(
                        "Skipping WebDriver artifact capture for destructive failure %s. "
                        "The browser may be unresponsive; set SELENIUM_CAPTURE_DESTRUCTIVE_ARTIFACTS=1 to force it.",
                        request.node.name,
                    )
                else:
                    # Save screenshot into artifacts/<run_id>/screenshots/
                    project_root = Path(__file__).resolve().parent
                    reports_dir = project_root / "reports"
                    run_id = os.environ.get("RUN_ID") or time.strftime("run_%Y%m%d_%H%M%S")
                    screenshots_dir = reports_dir / "artifacts" / run_id / "screenshots"
                    screenshots_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    safe_name = _safe_artifact_stem(request.node, "failed")
                    screenshot_path = screenshots_dir / f"{safe_name}_{timestamp}.png"
                    try:
                        browser_session.execute_script("window.scrollTo(0, 0);")
                    except Exception:
                        pass
                    try:
                        browser_session.save_screenshot(str(screenshot_path))
                    except Exception as exc:
                        LOGGER.exception("Failed to save screenshot on failure: %s", exc)

                    LOGGER.error("Screenshot saved on failure: %s", screenshot_path)
                    _save_page_source("failed")
                    _save_console_logs("failed")

                    existing_extras = getattr(request.node.rep_call, "extras", [])
                    existing_extras.append(extras.png(str(screenshot_path)))
                    request.node.rep_call.extras = existing_extras
            except Exception as exc:
                LOGGER.exception("Failed to capture artifacts on failure: %s", exc)

        save_on_pass = os.getenv("SELENIUM_SAVE_PASS", "0")
        if passed and str(save_on_pass).lower() in ("1", "true", "yes"):
            try:
                project_root = Path(__file__).resolve().parent
                reports_dir = project_root / "reports"
                run_id = os.environ.get("RUN_ID") or time.strftime("run_%Y%m%d_%H%M%S")
                screenshots_dir = reports_dir / "artifacts" / run_id / "screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                safe_name = _safe_artifact_stem(request.node, "passed")
                screenshot_path = screenshots_dir / f"{safe_name}_{timestamp}.png"
                try:
                    browser_session.execute_script("window.scrollTo(0, 0);")
                except Exception:
                    pass
                try:
                    browser_session.save_screenshot(str(screenshot_path))
                except Exception as exc:
                    LOGGER.exception("Failed to save screenshot on pass: %s", exc)

                LOGGER.info("Screenshot saved on pass: %s", screenshot_path)
                _save_page_source("passed")
                _save_console_logs("passed")
            except Exception as exc:
                LOGGER.exception("Failed to capture artifacts on pass: %s", exc)
    except Exception:
        pass

    if failed and "destructive" in request.node.keywords:
        try:
            destructive_pid = browser_session.service.process.pid
        except Exception:
            destructive_pid = None
        LOGGER.warning("Stopping Selenium browser immediately after destructive failure: %s", request.node.name)
        _kill_windows_process_tree(destructive_pid)
        _unregister_chromedriver_pid(destructive_pid)
        if owns_browser:
            _cleanup_isolated_chrome_driver(browser_session, user_data_dir, chromedriver_pid, quit_browser=False)
        elif uses_worker_browser:
            _reset_worker_browser(quit_browser=False)
        return

    if owns_browser:
        _cleanup_isolated_chrome_driver(browser_session, user_data_dir, chromedriver_pid)
        return

    try:
        handles = list(browser_session.window_handles)
        base_window_handle = getattr(browser_session, "_base_window_handle", None)

        for handle in handles:
            if handle == base_window_handle:
                continue
            try:
                browser_session.switch_to.window(handle)
                browser_session.close()
            except Exception as exc:
                LOGGER.warning("Failed to close extra tab %s after %s: %s", handle, request.node.name, exc)

        handles = list(browser_session.window_handles)
        if base_window_handle and base_window_handle in handles:
            browser_session.switch_to.window(base_window_handle)
        elif handles:
            browser_session.switch_to.window(handles[0])

        LOGGER.info("Closed dedicated/extra tabs after %s", request.node.name)
    except Exception as exc:
        LOGGER.warning("Failed to close dedicated tab after %s: %s", request.node.name, exc)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook pytest: Gắn report vào item để fixture teardown dùng."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


def pytest_sessionstart(session):
    """Ghi nhận thời gian bắt đầu session."""
    session._session_start_time = time.time()


def pytest_sessionfinish(session, exitstatus):
    """Ghi lại lịch sử chạy vào run_history.json sau khi kết thúc pytest session."""
    _reset_worker_browser(quit_browser=True)
    _kill_registered_selenium_processes()
    # 1. Tránh ghi đè nếu chạy từ Streamlit Dashboard (vì Dashboard tự ghi lại lịch sử với thông tin chuẩn hơn)
    if os.getenv("STREAMLIT_DASHBOARD_RUN") == "1":
        return

    # 2. Tránh ghi đè từ các tiến trình con (workers) của pytest-xdist
    if hasattr(session.config, "workerinput"):
        return

    # collect-only chỉ dùng để kiểm tra danh sách testcase, không phải một lần chạy test thật.
    if getattr(session.config.option, "collectonly", False):
        return

    from datetime import datetime, timezone

    project_root = Path(session.config.rootdir)
    reports_dir = project_root / "reports"
    run_history_path = reports_dir / "run_history.json"

    duration = 0.0
    if hasattr(session, "_session_start_time"):
        duration = round(time.time() - session._session_start_time, 2)

    args = session.config.invocation_params.args
    args_str = " ".join(args) if args else ""
    mode = "Tùy chỉnh"
    if not args:
        mode = "Smoke nhanh"
    elif "test_regression" in args_str:
        mode = "Regression ưu tiên"
    elif "tests" in args_str:
        mode = "Full suite"

    entry = {
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_id": os.environ.get("RUN_ID", "-"),
        "git_commit": os.environ.get("GIT_COMMIT", "-"),
        "description": os.environ.get("SELENIUM_RUN_DESCRIPTION", ""),
        "mode": f"Selenium CLI ({mode})",
        "target": args_str if args_str else "tests (smoke)",
        "returncode": int(exitstatus),
        "duration": duration,
    }

    history = []
    try:
        if run_history_path.exists():
            history = json.loads(run_history_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    history.insert(0, entry)
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        run_history_path.write_text(json.dumps(history[:50], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def pytest_unconfigure(config):
    """Last-resort cleanup for Selenium-owned Chrome processes."""
    _reset_worker_browser(quit_browser=True)
    _kill_registered_selenium_processes()
