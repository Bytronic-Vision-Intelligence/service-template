import yaml
from pathlib import Path


def _config_path() -> Path:
    return Path(__file__).resolve().parent / "config.yaml"


def get_config() -> dict:
    """Read and return configuration from the local `config.yaml` next to this module.

    Returns an empty dict if the file is missing or empty.
    """
    path = _config_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config


def return_config_value(key: str) -> str:
    """Return the value for `key` from the loaded config.

    Raises ValueError for empty keys and KeyError when the key is missing.
    """
    if not key:
        raise ValueError("Key cannot be empty.")
    config = get_config()
    if key not in config:
        raise KeyError(f"Key '{key}' not found in configuration.")
    return config[key]