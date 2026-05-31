import json
from pathlib import Path

from utils.paths import CONFIG_PATH


def load_config(config_path=CONFIG_PATH):
    """Load the Selenium test configuration."""
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)

