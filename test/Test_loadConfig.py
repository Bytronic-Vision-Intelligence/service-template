import pytest
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.dependencies.loadConfig import return_config_value, get_config


@pytest.fixture(autouse=True)
def use_local_config(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pytest", "--test"])


def test_return_config_value():
    config = get_config()
    assert return_config_value("key1") == config.get("key1")
    assert return_config_value("key2") == config.get("key2")

    with pytest.raises(KeyError):
        return_config_value("non_existent_key")

    with pytest.raises(ValueError):
        return_config_value("")


def test_missing_config_without_test_flag(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog"])
    with pytest.raises(SystemExit):
        get_config()


def main():
    test_return_config_value()


if __name__ == "__main__":
    pytest.main()
