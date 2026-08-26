import yaml
from pathlib import Path


def get_local_config_path() -> Path:
    return Path(__file__).resolve().parent / "config.yaml"


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def get_config() -> dict:
    """Load config from the orchestrator root, else fall back to local config.yaml.

    Orchestrator layout (cwd = this worker's root):

        service-orchestrator/config.yaml  -> section keyed by worker dir name
        service-orchestrator/<worker>/

    If that file or section is missing, use ``app/dependencies/config.yaml``.
    """
    worker_dir = Path.cwd().resolve()
    orch_path = worker_dir.parent / "config.yaml"
    section = load_yaml(orch_path).get(worker_dir.name)
    if isinstance(section, dict):
        return section

    return load_yaml(get_local_config_path())


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
