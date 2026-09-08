"""Read this service's configuration from beside its own binary.

One rule: ``config.yaml`` sits in the directory the service runs from, and the
orchestrator puts it there. A service is never configured by hand, never runs
standalone in deployment, and takes no path argument -- there is nothing to
pass, because there is only one place to look.

    <root>/
        bytronic-orchestrator
        config.yaml              <- the orchestrator's own, the source of truth
        camera-service/
            camera-service       <- the binary
            config.yaml          <- written here by the orchestrator

The bundled copy in this repository is not deployment configuration. It is the
documented shape of a section, so the loader and anyone reading the repo can
see what a service accepts.

Finding "beside the binary" is the one subtle part. Once PyInstaller has frozen
the service, ``__file__`` points inside ``sys._MEIPASS`` -- a temporary
directory that is created on launch and deleted on exit -- so a config resolved
from it is neither the operator's file nor even present after the process ends.
``sys.executable`` is the real location. Getting this wrong is silent: the
service reads a stale bundled copy and ignores everything the operator wrote.
"""

import argparse
import sys
from pathlib import Path

import yaml

CONFIG_NAME = "config.yaml"


def service_root() -> Path:
    """The directory the service runs from, frozen or not.

    Frozen, that is where the binary sits. From source it is the repository
    root, which is the same relationship: one level above ``app/``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def config_path() -> Path:
    """Where this service reads its configuration from."""
    return service_root() / CONFIG_NAME


def load_yaml(path: Path) -> dict:
    """Read a YAML mapping, or an empty dict when there is nothing usable."""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def get_config() -> dict:
    """This service's configuration.

    Raises:
        SystemExit: when the file is absent. Starting with no configuration is
            worse than not starting: the service comes up subscribed to
            nothing, publishing nowhere, and looks healthy to anything
            watching it.
    """
    path = config_path()
    if not path.is_file():
        raise SystemExit(
            f"No {CONFIG_NAME} beside the binary (looked in {path.parent}). "
            "The orchestrator writes it there when it launches a service.")
    return load_yaml(path)


def return_config_value(key: str):
    """One top-level value, or a KeyError naming the file it is missing from."""
    config = get_config()
    if key not in config:
        raise KeyError(f"Key '{key}' not found in {config_path()}")
    return config[key]


def parse_cli(argv=None) -> argparse.Namespace:
    """Handle the only argument a service takes: --help.

    It takes no --config: there is one place a config can be. --help is here
    because the release pipeline's build action smoke-tests every binary by
    running it with --help and fails the build on a non-zero exit, and because
    it is what anyone types first.
    """
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="A Bytronic service. Reads config.yaml from its own "
                    "directory, which service-orchestrator writes.")
    parser.parse_args(argv)
    return parser
