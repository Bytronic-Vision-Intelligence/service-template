import yaml
from pathlib import Path

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.yaml"
_CONFIG_PATH: Path | None = None


def set_config_path(path: str | Path | None) -> Path:
    """Set the config file path for this process. None selects the default fallback."""
    global _CONFIG_PATH
    _CONFIG_PATH = _DEFAULT_CONFIG_PATH if path is None else Path(path).resolve()
    return _CONFIG_PATH


def config_path() -> Path:
    """Return the config path currently in effect for this process."""
    return _CONFIG_PATH if _CONFIG_PATH is not None else _DEFAULT_CONFIG_PATH


def get_config(path: str | Path | None = None) -> dict:
    """Read a YAML mapping from `path`.

    Args:
        path: file to read. When omitted, uses the path from `set_config_path`
            or the default `config.yaml` at the project root.
    Returns:
        data: the parsed mapping, or an empty dict if the file is missing,
            empty, or does not contain a mapping at the top level.
    """
    resolved_path = set_config_path(path)
    if not resolved_path.is_file():
        return {}
    with open(resolved_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}
