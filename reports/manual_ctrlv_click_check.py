import os
import time
import unicodedata
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

BASE_URL = 'https://phongvu.vn'
CHUNK_SIZE = 1_000_000
PASTES = 11

def short(e, limit=300):
    text = unicodedata.normalize('NFKD', str(e or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c)).replace('\r',' ').replace('\n',' ')
    return text[:limit] + ('... [truncated]' if len(text) > limit else '')

options = Options()
options.add_argument('--disable-notifications')
options.add_argument('--disable-popup-blocking')
options.add_argument('--start-maximized')
options.add_argument('--blink-settings=imagesEnabled=false')
service = Service()
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(60)
driver.command_executor.set_timeout(30)
try:
    driver.get(BASE_URL)
    time.sleep(3)
    selectors = ['input[role="searchbox"]', 'input[placeholder*="muon mua"]', 'input[type="text"]']
    seed = 'x' * CHUNK_SIZE
    result = driver.execute_script('''
        const selectors = arguments[0];
        const chunk = arguments[1];
        let el = null;
        for (const sel of selectors) { el = document.querySelector(sel); if (el) break; }
        if (!el) return {found:false, length:0};
        el.focus();
        el.value = chunk;
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        return {found:true, length:el.value.length};
    ''', selectors, seed)
    if not result.get('found'):
        print('RESULT: cannot find search input')
        raise SystemExit(2)
    search_input = driver.find_element(By.CSS_SELECTOR, 'input[role="searchbox"], input[placeholder*="muon mua"], input[type="text"]')
    search_input.send_keys(Keys.CONTROL, 'a')
    search_input.send_keys(Keys.CONTROL, 'c')
    search_input.send_keys(Keys.END)
    print(f'SEED_OK length={result.get("length")}')
    last_len = result.get('length')
    for i in range(1, PASTES + 1):
        t0 = time.time()
        try:
            search_input.send_keys(Keys.CONTROL, 'v')
            last_len = driver.execute_script('return arguments[0].value.length;', search_input)
            print(f'PASTE_OK i={i} length={last_len} elapsed={time.time()-t0:.2f}s')
        except Exception as e:
            print(f'PASTE_FAIL i={i} last_length={last_len} elapsed={time.time()-t0:.2f}s error={short(e)}')
            break
    print('TRY_CLICK_SEARCH_INPUT')
    t0 = time.time()
    try:
        driver.execute_script('arguments[0].blur();', search_input)
        search_input.click()
        focused = driver.execute_script('return document.activeElement === arguments[0];', search_input)
        print(f'CLICK_RESULT target=search_input focused={focused} elapsed={time.time()-t0:.2f}s')
    except Exception as e:
        print(f'CLICK_RESULT target=search_input focused=False elapsed={time.time()-t0:.2f}s error={short(e)}')
    print('TRY_CLICK_BODY')
    t0 = time.time()
    try:
        driver.find_element(By.TAG_NAME, 'body').click()
        print(f'CLICK_RESULT target=body ok=True elapsed={time.time()-t0:.2f}s')
    except Exception as e:
        print(f'CLICK_RESULT target=body ok=False elapsed={time.time()-t0:.2f}s error={short(e)}')
finally:
    try:
        driver.quit()
    except Exception:
        pass
