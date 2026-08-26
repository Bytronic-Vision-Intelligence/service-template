import yaml
import argparse
from pathlib import Path


# app/dependencies/loadConfig.py -> app/configs/config.yaml
LOCAL_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "config.yaml"


def _config_path() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", default=None)
    args, _ = parser.parse_known_args()
    if args.config:
        return Path(args.config)
    return LOCAL_CONFIG_PATH


def get_config() -> dict:
    """Read config from ``--config`` path, else local ``config.yaml``.

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