import json
import os
from pathlib import Path
from typing import Any, Dict

# Define the default configuration
DEFAULT_CONFIG = {
    "simple_mode": False,
    "show_thinking": True,
    "show_sql": True,
    "show_data": True,
    "show_visualization": True, # Added based on PRD
}

CONFIG_DIR = Path.home() / ".llm-dw"
CONFIG_FILE_PATH = CONFIG_DIR / "config.json"


def _ensure_config_dir_exists():
    """Ensures the configuration directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """
    Loads the configuration from the config file, or returns the default config
    if the file does not exist or is invalid.
    """
    _ensure_config_dir_exists()
    if CONFIG_FILE_PATH.exists():
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Merge with default config to ensure all keys are present
                # and new keys are added automatically
                return {**DEFAULT_CONFIG, **config}
        except json.JSONDecodeError:
            print(f"Warning: Invalid config file at {CONFIG_FILE_PATH}. Using default configuration.")
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG


def save_config(key: str, value: Any):
    """
    Saves a specific key-value pair to the configuration file.
    """
    _ensure_config_dir_exists()
    config = load_config() # Load current config (or defaults)
    config[key] = value
    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"Configuration '{key}' updated to '{value}'.")

def get_config_value(key: str) -> Any:
    """
    Retrieves a specific configuration value.
    """
    config = load_config()
    return config.get(key)

