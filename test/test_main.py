from queue import Queue

import pytest

from fakes import FakeMQTTClient, FakeMQTTConfig, FakeThread

import main


def make_topics():
    """The shape shipped in the root config.yaml, plus a non-trigger feed."""
    return [
        {
            "name": "trigger",
            "topic": "template/worker/trigger",
            "is_subscribe": True,
            "is_trigger": True,
        },
        {
            "name": "feed",
            "topic": "template/worker/feed",
            "is_subscribe": True,
            "is_trigger": False,
        },
        {
            "name": "output",
            "topic": "template/worker/output",
            "is_subscribe": False,
            "is_trigger": False,
        },
    ]


def test_require_returns_the_value_when_present():
    assert main.require({"topics": []}, "topics") == []


def test_require_exits_naming_the_missing_key():
    with pytest.raises(SystemExit) as excinfo:
        main.require({}, "mqtt")

    assert "mqtt" in str(excinfo.value)


def test_output_topics_returns_only_the_unsubscribed_topics():
    assert main.output_topics(make_topics()) == ["template/worker/output"]


def test_next_trigger_returns_none_when_no_queues_exist():
    assert main.next_trigger(make_topics()) is None


def test_next_trigger_returns_none_when_queues_are_empty():
    topics = make_topics()
    for topic in topics:
        topic["queue"] = Queue()

    assert main.next_trigger(topics) is None


def test_next_trigger_decodes_the_waiting_payload():
    topics = make_topics()
    topics[0]["queue"] = Queue()
    topics[0]["queue"].put('{"command": "run", "value": 3}')

    assert main.next_trigger(topics) == {"command": "run", "value": 3}


def test_next_trigger_ignores_queues_that_are_not_triggers():
    topics = make_topics()
    topics[1]["queue"] = Queue()
    topics[1]["queue"].put('{"command": "should not fire"}')

    assert main.next_trigger(topics) is None


def test_next_trigger_discards_malformed_payloads_without_raising(caplog):
    topics = make_topics()
    topics[0]["queue"] = Queue()
    topics[0]["queue"].put("not json at all")

    with caplog.at_level("WARNING"):
        assert main.next_trigger(topics) is None
    # WARNING, not INFO: a payload the service cannot read is something being
    # published wrongly, and at INFO it reads as routine chatter.
    assert "Discarding malformed payload" in caplog.text
    assert "WARNING" in caplog.text


def test_start_subscribers_spawns_only_for_subscribed_topics(monkeypatch):
    started = []

    def fake_start_subscribe_thread(ip, port, topic, queue, stop_event):
        started.append(topic)
        return FakeThread()

    monkeypatch.setattr(main, "start_subscribe_thread", fake_start_subscribe_thread)
    topics = make_topics()

    threads = main.start_subscribers(
        {"mqtt_ip": "127.0.0.1", "mqtt_port": 1883}, topics, main.Event()
    )

    assert started == ["template/worker/trigger", "template/worker/feed"]
    assert len(threads) == 2
    assert "queue" in topics[0] and "queue" in topics[1]
    assert "queue" not in topics[2]


def test_service_process_function_logs_the_placeholder(caplog):
    """Logged, not printed. A frozen binary block-buffers print() output, so
    under the orchestrator it is invisible until several KB accumulate and is
    lost entirely on a crash. Logging handlers flush per record."""
    with caplog.at_level("INFO"):
        main.service_process_function(None, {"command": "run"}, [])

    assert "insert your program here" in caplog.text


def test_main_processes_one_message_then_shuts_down_cleanly(monkeypatch):
    config = {
        "mqtt": {"mqtt_ip": "127.0.0.1", "mqtt_port": 1883,
                 "topics": make_topics()},
        "service": {},
    }
    monkeypatch.setattr(main.loadConfig, "get_config", lambda: config)
    monkeypatch.setattr(main, "MQTTClient", FakeMQTTClient)
    monkeypatch.setattr(main, "MQTTConfig", FakeMQTTConfig)

    threads = []
    captured = {}

    def fake_start_subscribe_thread(ip, port, topic, queue, stop_event):
        captured["stop_event"] = stop_event
        if topic == "template/worker/trigger":
            queue.put('{"command": "run"}')
        thread = FakeThread()
        threads.append(thread)
        return thread

    monkeypatch.setattr(main, "start_subscribe_thread", fake_start_subscribe_thread)

    handled = []
    monkeypatch.setattr(
        main,
        "service_process_function",
        lambda client, message, outputs: handled.append((message, outputs)),
    )

    ticks = {"count": 0}

    def fake_sleep(_duration):
        ticks["count"] += 1
        if ticks["count"] == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(main.time, "sleep", fake_sleep)

    main.main([])

    assert handled == [({"command": "run"}, ["template/worker/output"])]
    assert captured["stop_event"].is_set()
    assert all(thread.join_called for thread in threads)


def test_main_exits_when_a_required_key_is_missing(monkeypatch):
    monkeypatch.setattr(main.loadConfig, "get_config", lambda: {"topics": []})

    with pytest.raises(SystemExit):
        main.main([])


def test_main_configures_logging_before_it_can_fail(monkeypatch):
    """Until configure() runs, the root logger sits at WARNING and every
    info() call is dropped. A service that failed while starting would then
    report nothing about why -- which is precisely when the log matters.

    So it must run before the first thing that can raise: `require`, which
    exits when a config key is missing."""
    import logging as _logging

    from dependencies import logging_setup

    order = []
    monkeypatch.setattr(logging_setup, "configure",
                        lambda level=None: order.append("configured"))
    monkeypatch.setattr(main.loadConfig, "get_config", lambda: {})

    with pytest.raises(SystemExit):
        main.main([])          # no broker_details -> require() exits
    assert order == ["configured"], "logging was not configured before the first failure"
    _logging.getLogger().handlers[:] = _logging.getLogger().handlers


def test_the_configured_level_comes_from_the_service_config(monkeypatch):
    seen = []
    from dependencies import logging_setup
    monkeypatch.setattr(logging_setup, "configure", lambda level=None: seen.append(level))
    monkeypatch.setattr(main.loadConfig, "get_config",
                        lambda: {"logging": {"level": "DEBUG"}})
    with pytest.raises(SystemExit):
        main.main([])
    assert seen == ["DEBUG"]


def test_a_config_without_a_logging_section_still_starts(monkeypatch):
    """Every existing service config predates this setting. A missing section
    must mean the default, not a crash on startup."""
    seen = []
    from dependencies import logging_setup
    monkeypatch.setattr(logging_setup, "configure", lambda level=None: seen.append(level))
    monkeypatch.setattr(main.loadConfig, "get_config", lambda: {})
    with pytest.raises(SystemExit):
        main.main([])
    assert seen == [logging_setup.DEFAULT_LEVEL]


def test_main_answers_help_before_looking_for_a_config(monkeypatch):
    """--help must exit 0 on a binary that has no config beside it, which is
    every binary the release pipeline builds. Reaching get_config() first
    exits 1 for want of a file that only exists once deployed, and no release
    could ever be published."""
    monkeypatch.setattr(main.loadConfig, "get_config",
                        lambda: pytest.fail("looked for a config before --help"))
    with pytest.raises(SystemExit) as exit_info:
        main.main(["--help"])
    assert exit_info.value.code == 0


def test_a_section_present_but_empty_is_refused():
    """`service:` written and left blank is a section somebody meant to fill
    in. Letting it through moves the failure to whatever first subscripts it,
    a stack frame away from the config that caused it."""
    with pytest.raises(SystemExit, match="mqtt"):
        main.require({"mqtt": None}, "mqtt")


def test_the_config_shipped_in_the_repo_satisfies_what_main_requires():
    """The root config.yaml is what a customer receives beside the binary. If
    it lacks a key main requires, every fresh install fails on first start."""
    import yaml
    from pathlib import Path

    config = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "config.yaml").read_text())
    mqtt = main.require(config, "mqtt")
    main.require(mqtt, "topics")
    main.require(config, "service")
    for key in ("mqtt_ip", "mqtt_port"):
        assert key in mqtt, f"{key} missing from the shipped config"
