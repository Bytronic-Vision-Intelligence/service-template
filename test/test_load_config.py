# test/test_load_config.py
"""Finding the one config a service is allowed to read.

A service takes no path argument. `config.yaml` sits beside its binary and the
orchestrator writes it there, so every test here is about that single rule and
the one way it is easy to get wrong.
"""
import re
import sys
from pathlib import Path

import pytest

from dependencies import loadConfig


@pytest.fixture(autouse=True)
def _forget_the_active_config(monkeypatch):
    """Reset the resolved path between tests.

    It is deliberately process state -- a service reads one config for its
    lifetime -- so without this a test inherits whatever file the previous one
    settled on.
    """
    monkeypatch.setattr(loadConfig, "_ACTIVE", None)


@pytest.fixture
def rooted(tmp_path, monkeypatch):
    """Pretend the service runs from tmp_path."""
    monkeypatch.setattr(loadConfig, "service_root", lambda: tmp_path)
    return tmp_path


def test_the_config_sits_beside_the_binary(rooted):
    assert loadConfig.config_path() == rooted / "config.yaml"


def test_a_frozen_service_looks_next_to_its_executable(monkeypatch, tmp_path):
    """The one subtle part, and the reason the previous loader was wrong.

    Once frozen, `__file__` points inside sys._MEIPASS -- a directory created
    on launch and deleted on exit -- so a config resolved from it is neither
    the operator's file nor present afterwards. The service would read a stale
    bundled copy and ignore everything the operator wrote, silently.
    """
    binary = tmp_path / "camera-service" / "camera-service"
    binary.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(binary))
    assert loadConfig.service_root() == binary.parent


def test_from_source_the_root_is_the_repository_root(monkeypatch):
    """Same relationship as when frozen: one level above app/. Otherwise a
    developer and the deployed binary read different files."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert loadConfig.service_root() == Path(loadConfig.__file__).resolve().parents[2]


def test_the_config_is_read(rooted):
    (rooted / "config.yaml").write_text("mqtt:\n  ip: 10.0.0.1\n")
    assert loadConfig.get_config()["mqtt"]["ip"] == "10.0.0.1"


def test_a_missing_config_stops_the_service(rooted):
    """Starting unconfigured is worse than not starting: the service comes up
    subscribed to nothing, publishing nowhere, and looks healthy to anything
    watching it."""
    with pytest.raises(SystemExit, match="config.yaml"):
        loadConfig.get_config()


def test_the_refusal_names_where_it_looked(rooted):
    """An operator who put the file in the wrong place needs the path, not
    just the filename.

    re.escape because a Windows path is full of backslashes, and `match` is a
    regex: `C:\\Users\\...` raises "incomplete escape \\U" rather than
    failing the assertion, so the test breaks on the platform it still has to
    pass on.
    """
    with pytest.raises(SystemExit, match=re.escape(str(rooted))):
        loadConfig.get_config()


@pytest.mark.parametrize("text", ["", "\n", "- a\n- b\n", "just a string\n"])
def test_an_empty_or_non_mapping_config_reads_as_empty(rooted, text):
    """A list or a bare string is not a config section. Returning it would push
    an AttributeError into whatever asked for a key."""
    (rooted / "config.yaml").write_text(text)
    assert loadConfig.get_config() == {}


def test_return_config_value_names_the_file_it_looked_in(rooted):
    (rooted / "config.yaml").write_text("mqtt: {}\n")
    with pytest.raises(KeyError, match="config.yaml"):
        loadConfig.return_config_value("absent")


def test_help_exits_zero(capsys):
    """The release build smoke-tests every binary with --help and fails on a
    non-zero exit. There is no input to change that argument, so a service
    that cannot answer --help cannot ship."""
    with pytest.raises(SystemExit) as exit_info:
        loadConfig.parse_cli(["--help"])
    assert exit_info.value.code == 0
    assert "config.yaml" in capsys.readouterr().out


def test_a_config_path_can_be_supplied():
    """One binary serves several instances, each pointed at its own file."""
    assert loadConfig.parse_cli(["--config", "/somewhere/else.yaml"]).config == \
        "/somewhere/else.yaml"


def test_omitting_the_flag_leaves_the_path_unset():
    """None means "beside the binary", which is what the orchestrator writes."""
    assert loadConfig.parse_cli([]).config is None


# One binary can serve several instances, each pointed at its own config, so a
# path may be supplied. These cover what happens when it is, and when what is
# supplied is nothing at all.


def test_an_explicit_config_path_is_used(tmp_path):
    other = tmp_path / "instance-2.yaml"
    other.write_text("mqtt:\n  ip: 10.0.0.2\n")
    assert loadConfig.get_config(other)["mqtt"]["ip"] == "10.0.0.2"


@pytest.mark.parametrize("empty", ["", "   ", "\t", "\n"])
def test_an_empty_config_path_is_refused(empty, rooted):
    """Falling back to the default here would start a DIFFERENT instance's
    configuration. The service would come up, look entirely healthy, and be
    the wrong one -- which is worse than not starting, because nothing
    anywhere would say so.

    An empty --config is a caller that meant to pass something and passed
    nothing: an unset shell variable, a dropped argument in a launcher.
    """
    (rooted / "config.yaml").write_text("mqtt:\n  ip: 10.0.0.1\n")
    with pytest.raises(SystemExit, match="empty path"):
        loadConfig.get_config(empty)


def test_the_refusal_does_not_quietly_read_the_default(rooted):
    """The failure must be the empty path, not a missing file: with a perfectly
    good default sitting there, a fallback would succeed and hide the bug."""
    (rooted / "config.yaml").write_text("mqtt:\n  ip: 10.0.0.1\n")
    with pytest.raises(SystemExit) as exit_info:
        loadConfig.get_config("")
    assert "10.0.0.1" not in str(exit_info.value)
    assert "empty path" in str(exit_info.value)


def test_omitting_the_path_still_uses_the_default(rooted):
    (rooted / "config.yaml").write_text("mqtt:\n  ip: 10.0.0.1\n")
    assert loadConfig.get_config()["mqtt"]["ip"] == "10.0.0.1"
    assert loadConfig.get_config(None)["mqtt"]["ip"] == "10.0.0.1"


def test_errors_name_the_config_actually_in_use(tmp_path, rooted):
    """A service told to use one file must never report about another. Without
    a resolved path, config_path() would answer with the default and every
    error would point at a file the service never opened."""
    other = tmp_path / "instance-2.yaml"
    other.write_text("mqtt: {}\n")
    loadConfig.get_config(other)
    assert loadConfig.config_path() == other
    with pytest.raises(KeyError, match="instance-2.yaml"):
        loadConfig.return_config_value("absent")
