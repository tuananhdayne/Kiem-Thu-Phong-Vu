import pytest
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.by import By

from pages.catalog_page import (
    search_with_keyword,
    extract_product_names,
    log_test_evidence,
    NO_RESULTS_TEXT,
)

pytestmark = pytest.mark.slow


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert(1)</script>",
        '\"<img src=x onerror=alert(1)>',
    ],
)
@pytest.mark.security
def test_search_xss_payload_is_sanitized(driver, test_config, payload):
    driver.get(test_config["base_url"]) 

    search_with_keyword(driver, test_config, payload, timeout=8)

    try:
        alert = driver.switch_to.alert
        text = alert.text
        alert.dismiss()
        pytest.fail(f"XSS payload opened a browser alert: {text}")
    except NoAlertPresentException:
        pass

    body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    names = extract_product_names(driver, test_config, limit=5)
    log_test_evidence(
        "XSS PAYLOAD RESULT",
        payload=payload,
        url=driver.current_url,
        alert="no alert",
        no_result=NO_RESULTS_TEXT in body_text,
        products=names,
    )

    assert len(body_text.strip()) > 100, "Page became blank after script-like search payload"
    assert names or NO_RESULTS_TEXT in body_text, "Search payload did not end in a valid result/no-result state"


@pytest.mark.parametrize(
    "payload",
    [
        "' OR '1'='1",
        '" OR "1"="1',
        "' UNION SELECT NULL --",
        "' UNION SELECT username,password FROM users --",
        "') UNION SELECT NULL,NULL --",
        "'; DROP TABLE products; --",
        "admin' --",
    ],
)
@pytest.mark.security
def test_search_sql_payload_is_handled_safely(driver, test_config, payload):
    driver.get(test_config["base_url"]) 

    search_with_keyword(driver, test_config, payload, timeout=8)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    body_lower = body_text.lower()
    names = extract_product_names(driver, test_config, limit=5)
    sql_error_signatures = [
        "sql syntax",
        "mysql",
        "postgres",
        "sqlite",
        "odbc",
        "jdbc",
        "ora-",
        "syntax error",
        "unclosed quotation",
        "database error",
        "stack trace",
    ]
    leaked_errors = [signature for signature in sql_error_signatures if signature in body_lower]
    log_test_evidence(
        "SQL PAYLOAD RESULT",
        payload=payload,
        url=driver.current_url,
        leaked_errors=leaked_errors,
        no_result=NO_RESULTS_TEXT in body_lower,
        products=names,
    )

    assert len(body_text.strip()) > 100, "Page became blank after SQL-like search payload"
    assert not leaked_errors, f"SQL/database error details leaked to the UI: {leaked_errors}"
    assert names or NO_RESULTS_TEXT in body_lower, "SQL-like payload did not end in a valid result/no-result state"
