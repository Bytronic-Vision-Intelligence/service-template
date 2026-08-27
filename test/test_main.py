from queue import Queue

import pytest

from fakes import FakeMQTTClient, FakeMQTTConfig, FakeThread

import main


def make_topics():
    """The shape shipped in app/dependencies/config.yaml, plus a non-trigger feed."""
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
        main.require({}, "broker_details")

    assert "broker_details" in str(excinfo.value)


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


def test_next_trigger_discards_malformed_payloads_without_raising(capsys):
    topics = make_topics()
    topics[0]["queue"] = Queue()
    topics[0]["queue"].put("not json at all")

    assert main.next_trigger(topics) is None
    assert "Discarding malformed payload" in capsys.readouterr().out


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


def test_worker_process_function_prints_the_placeholder(capsys):
    main.worker_process_function(None, {"command": "run"}, [])

    assert "insert your program here" in capsys.readouterr().out


def test_main_processes_one_message_then_shuts_down_cleanly(monkeypatch):
    config = {
        "broker_details": {"mqtt_ip": "127.0.0.1", "mqtt_port": 1883},
        "topics": make_topics(),
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
        "worker_process_function",
        lambda client, message, outputs: handled.append((message, outputs)),
    )

    ticks = {"count": 0}

    def fake_sleep(_duration):
        ticks["count"] += 1
        if ticks["count"] == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(main.time, "sleep", fake_sleep)

    main.main()

    assert handled == [({"command": "run"}, ["template/worker/output"])]
    assert captured["stop_event"].is_set()
    assert all(thread.join_called for thread in threads)


def test_main_exits_when_a_required_key_is_missing(monkeypatch):
    monkeypatch.setattr(main.loadConfig, "get_config", lambda: {"topics": []})

    with pytest.raises(SystemExit):
        main.main()
