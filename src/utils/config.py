import json
import os
from pathlib import Path
from typing import Any, Dict

from src.utils.logger import logger

# Define the default configuration
DEFAULT_CONFIG = {
    "simple_mode": False,
    "show_thinking": True,
    "show_sql": True,
    "show_data": True,
    "show_visualization": True, # Added based on PRD
}

# Use env var for config dir or default to project-relative data/config
# This is better for containers and avoids permission issues with Path.home()
env_config_dir = os.getenv("APP_CONFIG_DIR")
if env_config_dir:
    CONFIG_DIR = Path(env_config_dir)
else:
    # Fallback to local data/config in current working directory
    CONFIG_DIR = Path.cwd() / "data" / "config"

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
            logger.warning(f"Invalid config file at {CONFIG_FILE_PATH}. Using default configuration.")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(key: str, value: Any):
    """
    Saves a specific key-value pair to the configuration file.
    """
    _ensure_config_dir_exists()
    config = load_config() # Load current config (or defaults)
    config[key] = value
    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info(f"Configuration '{key}' updated to '{value}'.")

def get_config_value(key: str) -> Any:
    """
    Retrieves a specific configuration value.
    """
    config = load_config()
    return config.get(key)

