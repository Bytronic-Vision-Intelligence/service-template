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
