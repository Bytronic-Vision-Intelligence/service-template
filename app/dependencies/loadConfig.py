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

The tracked ``config.yaml`` at the repository root is not deployment
configuration. It is the documented shape of a section, so anyone reading the
repository can see what a service accepts, and the release package ships a copy
beside the binary as a starting point.

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

#: The file actually in use this process, once resolved. Error messages read
#: it, so that a service told to use one config never reports about another.
_ACTIVE: Path | None = None


def service_root() -> Path:
    """The directory the service runs from, frozen or not.

    Frozen, that is where the binary sits. From source it is the repository
    root, which is the same relationship: one level above ``app/``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def resolve_config_path(supplied=None) -> Path:
    """The config file to read, from an explicit path or the default.

    One binary can serve several instances, each pointed at its own config, so
    a path may be supplied. Omitting it means `config.yaml` beside the binary.

    Args:
        supplied: a path, or None for the default.
    Raises:
        SystemExit: when a path is supplied but empty or blank. Falling back to
            the default there would silently run a DIFFERENT instance's
            configuration -- the service would start, look healthy, and be the
            wrong one. An empty --config is a caller that meant to pass
            something and passed nothing.
    """
    global _ACTIVE
    if supplied is None:
        # Once a config has been chosen for this process, later calls read the
        # SAME file. Re-resolving to the default would mean return_config_value
        # quietly reading a different instance's config than the one the
        # service started with.
        if _ACTIVE is None:
            _ACTIVE = service_root() / CONFIG_NAME
        return _ACTIVE
    text = str(supplied).strip()
    if not text:
        raise SystemExit(
            "--config was given an empty path. Pass the config to run with, "
            f"or omit --config to use {CONFIG_NAME} beside the binary. "
            "Falling back here would run a different instance's config.")
    _ACTIVE = Path(text)
    return _ACTIVE


def config_path() -> Path:
    """The config file in use, for error messages.

    Reports whatever `resolve_config_path` last settled on, so a service told
    to use one file never names another in its errors.
    """
    return _ACTIVE if _ACTIVE is not None else service_root() / CONFIG_NAME


def load_yaml(path: Path) -> dict:
    """Read a YAML mapping, or an empty dict when there is nothing usable."""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def get_config(supplied=None) -> dict:
    """This service's configuration.

    Args:
        supplied: an explicit config path, or None for the default.
    Raises:
        SystemExit: when the path is empty, or the file is absent. Starting
            with no configuration is worse than not starting: the service
            comes up subscribed to nothing, publishing nowhere, and looks
            healthy to anything watching it.
    """
    path = resolve_config_path(supplied)
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
    """Parse the arguments a service accepts.

    `--config` exists so one binary can serve several instances, each pointed
    at its own file. Omitted, the service reads `config.yaml` beside itself,
    which is what the orchestrator writes.

    `--help` must exit 0: the release pipeline's build action smoke-tests every
    binary by running it with --help and fails the build on a non-zero exit.
    """
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="A Bytronic service. Reads config.yaml from its own "
                    "directory, which service-orchestrator writes.")
    parser.add_argument(
        "--config", default=None, metavar="PATH",
        help=f"config to run with; omit for {CONFIG_NAME} beside the binary. "
             "One binary can serve several instances this way.")
    return parser.parse_args(argv)
