import sys

import pytest

from dependencies.loadConfig import (
    LOCAL_CONFIG_PATH,
    config_path,
    get_config,
    load_yaml,
    return_config_value,
)


def test_test_flag_selects_the_bundled_config():
    assert config_path() == LOCAL_CONFIG_PATH


def test_config_flag_is_used_verbatim(monkeypatch, tmp_path):
    # service-orchestrator launches every service with --config <abs path>
    supplied = tmp_path / "orchestrator-written.yaml"
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(supplied)])

    assert config_path() == supplied


def test_no_flag_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py"])

    with pytest.raises(SystemExit):
        config_path()


def test_missing_config_file_exits_rather_than_starting_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(tmp_path / "absent.yaml")])

    with pytest.raises(SystemExit):
        get_config()


def test_load_yaml_returns_empty_for_missing_empty_and_non_mapping(tmp_path):
    assert load_yaml(tmp_path / "missing.yaml") == {}

    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    assert load_yaml(empty) == {}

    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("a bare string\n", encoding="utf-8")
    assert load_yaml(scalar) == {}


def test_bundled_config_supplies_every_key_main_requires():
    # main() refuses to start without these, so the shipped example must have them
    config = get_config()

    assert "broker_details" in config
    assert "topics" in config
    assert {"mqtt_ip", "mqtt_port"} <= set(config["broker_details"])


def test_return_config_value():
    config = get_config()
    assert return_config_value("broker_details") == config["broker_details"]

    with pytest.raises(KeyError):
        return_config_value("non_existent_key")

    with pytest.raises(ValueError):
        return_config_value("")
