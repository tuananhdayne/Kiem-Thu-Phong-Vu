# Phong Vu Selenium Test Framework

Selenium + pytest automation framework for validating key ecommerce flows on the public Phong Vu website: Search, Filter, and Sort.

This is an independent learning/testing project, not an official Phong Vu test suite. By default, commands exclude destructive and security-payload checks.

## Project Layout

```text
.
|-- config/                  # Configuration notes and future split plan
|-- pages/                   # Page objects and UI interaction helpers
|   |-- base_page.py
|   `-- catalog_page.py
|-- tests/                   # Pytest test cases
|-- utils/                   # Shared framework utilities
|   |-- artifacts.py
|   |-- config_loader.py
|   |-- logging_utils.py
|   |-- parsers.py
|   `-- paths.py
|-- reports/                 # Generated reports and artifacts
|-- conftest.py              # Pytest fixtures, Selenium lifecycle, artifact hooks
|-- dashboard.py             # Streamlit dashboard
|-- main.py                  # Backward-compatible facade
|-- pytest.ini               # Pytest defaults and marker registry
`-- QA_STRATEGY.md           # QA rules and operating model
```

## Common Commands

Run smoke tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run prioritized regression without destructive/security-payload tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "regression and not destructive and not security"
```

Run slow tests without destructive/security-payload tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "slow and not destructive and not security"
```

Run security-payload checks only on authorized/demo/mock targets:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "security and not destructive" --run-security
```

Run destructive long-query checks intentionally:

```powershell
.\.venv\Scripts\python.exe -m pytest -m destructive --run-destructive
```

Start the dashboard:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

## Browser Safety

The Selenium fixture creates a temporary Chrome profile, closes extra tabs after each test, quits the driver at session end, and kills only the ChromeDriver-owned process tree on Windows. Personal Chrome windows are not targeted.

For parallel destructive/security runs, each pytest worker owns an independent Chrome instance and each test opens a separate tab inside that worker browser. This keeps the number of Chrome instances bounded by the worker count while still isolating test state.

## QA Scope

- `smoke`: fast business checks for Search, Filter, and Sort.
- `regression`: fuller business checks for combinations and edge cases.
- `slow`: non-critical cases that should not block quick feedback.
- `security`: black-box payload checks; not run by default and should only be used on authorized/demo/mock targets.
- `destructive`: long-input stress checks that can make Chrome heavy or unresponsive.
- `framework`: Selenium/helper behavior, useful internally but not highlighted as business website testing.

## Development Rules

- Put reusable browser interactions in `pages/`.
- Put config loading, parsing, logging, artifact, and path helpers in `utils/`.
- Keep business assertions in `tests/`.
- Keep long-input and browser stress cases marked as `destructive`.
- Keep XSS/SQL-like payload checks marked as `security`.
- Do not rely on URL-only pass/fail checks; validate visible product data.
