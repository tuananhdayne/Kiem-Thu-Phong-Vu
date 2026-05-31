# QA Automation Strategy

## Scope

This independent learning/testing suite validates critical ecommerce flows on the public Phong Vu website through Selenium:

- Product filtering by brand
- Price sorting
- Product search
- Search/filter/sort combinations
- Negative and no-result states

The tests run against a third-party live website, so assertions must prove business behavior from visible UI data instead of only checking that pages load. Destructive and security-payload checks are disabled by default and should only run on authorized/demo/mock targets.

## Test Levels

### Smoke

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Default smoke tests are fast checks for core journeys. They must fail when:

- A filter URL changes but visible products do not match the selected filter
- A sort URL changes but visible prices are not ordered
- A search returns unrelated top results

### Regression

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "regression and not destructive and not security"
```

Regression tests cover combinations and edge cases. They should be used before release or after changing selectors/helper logic.

### Slow

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "slow and not destructive and not security"
```

Slow tests cover broader verification but may be more affected by live-site timing.

### Security Payload

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "security and not destructive" --run-security
```

Security payload tests use XSS-like and SQL-like search strings to check UI symptoms such as alerts, blank pages, or leaked database errors. Do not run them against a third-party live website unless the target is authorized; keep them for demo/mock environments or explicitly approved testing.

### Destructive

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest -m destructive --run-destructive
```

Destructive tests intentionally stress the browser with very long input. Do not run them during normal smoke/regression work. They are skipped unless `--run-destructive` is explicitly passed.

## Anti-False-Pass Rules

- Do not pass a filter test because one item matches. Check all sampled visible items.
- Do not pass a sort test because the sort control was clicked. Compare the extracted prices/order.
- Do not pass a search test because the page has content. Check relevance of the visible result names.
- Avoid `try/except: pass` around business assertions.
- Use `pytest.skip` only when the scenario is genuinely unavailable, not when behavior is suspicious.
- Keep stress tests separate from normal regression to avoid Chrome/RAM exhaustion.
- Keep security payload tests separate from normal regression to avoid unauthorized testing against third-party systems.

## Browser Cleanup

The Selenium fixture uses a temporary Chrome profile for the test session, closes extra tabs after each test, quits the browser at session end, and kills only the ChromeDriver-owned process tree on Windows. It should not close personal Chrome windows opened outside the test.

For parallel destructive/security runs, each pytest worker owns an independent Chrome instance and each test opens a separate tab inside that worker browser. This keeps destructive failures from poisoning the shared browser while keeping Chrome usage bounded by the worker count.

## Current Quality Notes

- Default collection selects only smoke tests by design.
- Regression should be run with `-m "regression and not destructive and not security"` for a fuller safe signal.
- Because the target is a live ecommerce site, some failures can be caused by UI/selector changes or inventory changes. Treat such failures as useful signals and inspect screenshots/page source in `reports/artifacts`.

## Framework Organization

- `pages/` owns Selenium UI interactions and page-object style helpers.
- `utils/` owns framework support code: config loading, logging, artifacts, parsing, and paths.
- `tests/` owns business assertions and scenario intent.
- `conftest.py` owns pytest fixtures, browser lifecycle, and report artifact hooks.
- `main.py` is retained only as a backward-compatible facade while imports move to `pages.*` and `utils.*`.
