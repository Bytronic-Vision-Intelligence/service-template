import threading
from queue import Queue

from fakes import FakeMQTTClient, FakeMQTTConfig

import dependencies.mqtt_functions as mqtt_functions


def test_subscribe_listener_puts_the_payload_into_the_queue(monkeypatch):
    monkeypatch.setattr(mqtt_functions, "MQTTClient", FakeMQTTClient)
    monkeypatch.setattr(mqtt_functions, "MQTTConfig", FakeMQTTConfig)
    result_queue = Queue()

    mqtt_functions.subscribe_listener(
        "127.0.0.1", 1883, "test/topic", result_queue, threading.Event()
    )

    assert result_queue.get_nowait() == '{"command": "run"}'


def test_subscribe_listener_connects_before_subscribing(monkeypatch):
    created = []

    def record(config):
        client = FakeMQTTClient(config)
        created.append(client)
        return client

    monkeypatch.setattr(mqtt_functions, "MQTTClient", record)
    monkeypatch.setattr(mqtt_functions, "MQTTConfig", FakeMQTTConfig)

    mqtt_functions.subscribe_listener(
        "127.0.0.1", 1883, "test/topic", Queue(), threading.Event()
    )

    assert created[0].connected is True
    assert created[0].subscriptions[0][0] == "test/topic"


def test_start_subscribe_thread_returns_a_daemon_thread_that_runs(monkeypatch):
    monkeypatch.setattr(mqtt_functions, "MQTTClient", FakeMQTTClient)
    monkeypatch.setattr(mqtt_functions, "MQTTConfig", FakeMQTTConfig)
    result_queue = Queue()

    thread = mqtt_functions.start_subscribe_thread(
        "127.0.0.1", 1883, "test/topic", result_queue, threading.Event()
    )
    thread.join(timeout=2)

    assert thread.daemon is True
    assert result_queue.get_nowait() == '{"command": "run"}'
