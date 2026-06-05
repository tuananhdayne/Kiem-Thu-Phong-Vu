import time
import unicodedata
import subprocess

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


BASE_URL = "https://phongvu.vn"
CHUNK_SIZE = 1_000_000
MAX_PASTES = 16
COMMAND_TIMEOUT = 45


def short_error(error, limit=300):
    text = unicodedata.normalize("NFKD", str(error or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else f"{text[:limit]}... [truncated]"


def timed(label, action):
    started = time.time()
    try:
        value = action()
        print(f"{label}: OK elapsed={time.time() - started:.2f}s result={value}")
        return True
    except Exception as error:
        print(f"{label}: FAIL elapsed={time.time() - started:.2f}s error={short_error(error)}")
        return False


def find_search_input(driver):
    selectors = [
        'input[role="searchbox"]',
        'input[placeholder*="muon mua"]',
        'input[placeholder*="mua gi"]',
        'input[type="text"]',
    ]
    for selector in selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        for element in elements:
            if element.is_displayed():
                return element
    raise RuntimeError("Search input not found")


def find_product_click_target(driver):
    script = """
        const selectors = ["a[href*='/p/']", "button", "a[href*='/c/']"];
        const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 40 && rect.height > 20 && style.visibility !== 'hidden' && style.display !== 'none';
        };
        const isProductLike = (el) => {
            const text = (el.innerText || el.textContent || '').trim().toLowerCase();
            const href = el.href || '';
            return href.includes('/p/') || text.includes('them vao gio') || text.includes('thêm vào giỏ') || text.includes('xem chi tiet');
        };
        for (let pass = 0; pass < 8; pass++) {
            for (const selector of selectors) {
                for (const el of document.querySelectorAll(selector)) {
                    if (!isVisible(el) || !isProductLike(el)) continue;
                    el.scrollIntoView({ block: 'center', inline: 'center' });
                    const rect = el.getBoundingClientRect();
                    const x = Math.floor(rect.left + rect.width / 2);
                    const y = Math.floor(rect.top + rect.height / 2);
                    const top = document.elementFromPoint(x, y);
                    if (top && (top === el || el.contains(top))) return el;
                }
            }
            window.scrollBy(0, Math.floor(window.innerHeight * 0.7));
        }
        return null;
    """
    target = driver.execute_script(script)
    if not target:
        raise RuntimeError("Product/click target not found")
    return target


options = Options()
options.add_argument("--disable-notifications")
options.add_argument("--disable-popup-blocking")
options.add_argument("--start-maximized")
options.add_argument("--blink-settings=imagesEnabled=false")

service = Service()
driver = webdriver.Chrome(service=service, options=options)
driver_pid = service.process.pid if service.process else None
driver.set_page_load_timeout(60)
driver.command_executor.set_timeout(COMMAND_TIMEOUT)

try:
    driver.get(BASE_URL)
    time.sleep(3)
    search_input = find_search_input(driver)
    seed = "x" * CHUNK_SIZE
    driver.execute_script(
        """
        const el = arguments[0];
        const value = arguments[1];
        el.focus();
        el.value = value;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        search_input,
        seed,
    )
    search_input.send_keys(Keys.CONTROL, "a")
    search_input.send_keys(Keys.CONTROL, "c")
    search_input.send_keys(Keys.END)
    print(f"SEED_OK length={CHUNK_SIZE:,}")

    last_length = CHUNK_SIZE
    for paste_index in range(1, MAX_PASTES + 1):
        started = time.time()
        try:
            search_input.send_keys(Keys.CONTROL, "v")
            last_length = int(driver.execute_script("return arguments[0].value.length;", search_input))
            print(f"PASTE_OK i={paste_index} length={last_length:,} elapsed={time.time() - started:.2f}s")
        except Exception as error:
            print(f"PASTE_FAIL i={paste_index} last_length={last_length:,} elapsed={time.time() - started:.2f}s error={short_error(error)}")
            break

        if paste_index >= 10:
            print(f"CLICK_CHECK after_paste={paste_index} length={last_length:,}")
            timed(
                "CLICK_SEARCH_INPUT",
                lambda: (
                    driver.execute_script("arguments[0].blur();", search_input),
                    search_input.click(),
                    driver.execute_script("return document.activeElement === arguments[0];", search_input),
                )[-1],
            )
            timed("CLICK_BODY", lambda: driver.find_element(By.TAG_NAME, "body").click() or True)
            before_url = driver.current_url
            timed("CLICK_PRODUCT_OR_BUTTON", lambda: ActionChains(driver).move_to_element(find_product_click_target(driver)).click().perform() or True)
            try:
                if driver.current_url != before_url:
                    driver.back()
                    time.sleep(1)
                search_input = find_search_input(driver)
            except Exception as error:
                print(f"POST_PRODUCT_CLICK_RECOVERY: FAIL error={short_error(error)}")
                break
finally:
    try:
        driver.quit()
    except Exception as error:
        print(f"CLEANUP_QUIT_FAIL error={short_error(error)}")
    if driver_pid:
        subprocess.run(
            ["taskkill", "/PID", str(driver_pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        print(f"CLEANUP_KILL_PROCESS_TREE pid={driver_pid}")
