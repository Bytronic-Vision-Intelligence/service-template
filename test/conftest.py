import logging
import sys

import pytest


@pytest.fixture(autouse=True)
def use_local_config(monkeypatch):
    """Point loadConfig at the bundled example config for every test.

    loadConfig resolves its file from sys.argv, which under pytest carries
    pytest's own arguments. Without this, every call would raise SystemExit.
    Individual tests can still override sys.argv themselves.
    """
    monkeypatch.setattr(sys, "argv", ["pytest", "--test"])


@pytest.fixture(autouse=True)
def _restore_root_logging():
    """Put the root logger back after every test.

    logging_setup.configure() replaces the root handlers deliberately -- a
    service calling it twice must not double every line. But pytest's own
    capture handler lives there too, so a test that configures logging silently
    disables caplog for every test that runs after it, in any file. The symptom
    is an empty caplog.text somewhere unrelated.
    """
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
