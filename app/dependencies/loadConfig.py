import argparse
import sys
import yaml
from pathlib import Path


# Fallback used by --test only. service-orchestrator passes an absolute
# --config path in deployment, so this file is a standalone-development aid.
LOCAL_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def config_path() -> Path:
    """Resolve which config file to read.

    service-orchestrator launches every service as
    ``app/main.py --config <path>``, so ``--config`` is the deployment path.
    ``--test`` selects the bundled example config for standalone runs.

    Returns:
        path: the config file to load.
    Raises:
        SystemExit: when neither flag is supplied.
    """
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="A Bytronic service. Started by service-orchestrator, "
                    "which supplies --config.",
        add_help=False)
    # -h/--help is declared explicitly rather than left to argparse's default,
    # because the rest of this parser deliberately ignores unknown arguments
    # (parse_known_args) so a service can take flags of its own. With
    # add_help=True those two settings interact badly; with add_help=False and
    # no declaration at all, --help fell through to the SystemExit below and
    # exited 1.
    #
    # Exiting non-zero on --help is not cosmetic: the release pipeline's build
    # action smoke-tests every binary by running it with --help, and treats a
    # non-zero exit as a broken build. There is no input to change that
    # argument, so a service that cannot answer --help cannot be released.
    parser.add_argument("-h", "--help", action="help",
                        help="show this message and exit")
    parser.add_argument("--config", default=None, metavar="PATH",
                        help="configuration file to run with")
    parser.add_argument("--test", action="store_true",
                        help="use the bundled example config, for standalone runs")
    args, _ = parser.parse_known_args()
    if args.config:
        return Path(args.config)
    if args.test:
        return LOCAL_CONFIG_PATH
    raise SystemExit("Missing required --config path (or pass --test to use local config).")


def load_yaml(path: Path) -> dict:
    """Read a YAML mapping from `path`.

    Args:
        path: file to read.
    Returns:
        data: the parsed mapping, or an empty dict if the file is missing,
            empty, or does not contain a mapping at the top level.
    """
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def get_config() -> dict:
    """Load the configuration selected by --config or --test.

    Returns:
        config: the parsed configuration mapping.
    Raises:
        SystemExit: when the selected file does not exist. A missing file means
            the orchestrator handed over a path it did not write, so failing
            here is preferable to starting on an empty config.
    """
    path = config_path()
    if not path.is_file():
        raise SystemExit(f"Config file not found: {path}")
    return load_yaml(path)


def return_config_value(key: str):
    """Return the value for `key` from the loaded config.

    Re-reads the config file on every call. Prefer a single `get_config()` in
    your entrypoint when reading more than one key.

    Args:
        key: a top-level key from the yaml file.
    Returns:
        the value stored under `key`.
    Raises:
        ValueError: when `key` is empty.
        KeyError: when `key` is not present in the configuration.
    """
    if not key:
        raise ValueError("Key cannot be empty.")
    config = get_config()
    if key not in config:
        raise KeyError(f"Key '{key}' not found in configuration.")
    return config[key]
