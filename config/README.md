# Configuration

The active Selenium configuration is currently kept in `../config.json` for compatibility with the existing dashboard and tests.

Recommended future split:

- `env.json`: base URLs and environment-specific values
- `selectors.json`: CSS/XPath selectors
- `test_data.json`: brands, search terms, and expected matching keywords

Keep selectors out of test files whenever possible so UI changes can be handled in one place.

