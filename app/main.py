import time
from json import JSONDecodeError, loads
from logging import info
from queue import Empty, Queue
from threading import Event

from mqtt_client import MQTTClient, MQTTConfig

from dependencies import loadConfig
from dependencies.mqtt_functions import start_subscribe_thread


def require(config: dict, key: str):
    """Return a required top-level config value, or exit describing what is missing.

    Args:
        config: the loaded configuration mapping.
        key: the top-level key the service cannot start without.
    Returns:
        the value stored under `key`.
    Raises:
        SystemExit: when `key` is absent, naming both the key and the file.
    """
    if key not in config:
        raise SystemExit(f"Missing required config key '{key}' in {loadConfig.config_path()}")
    return config[key]


def start_subscribers(broker: dict, topics: list, stop_event: Event) -> list:
    """Start one listener thread per subscribed topic.

    Each topic entry with `is_subscribe` true gains a `queue` key, which
    `next_trigger` later reads from.

    Args:
        broker: mapping containing mqtt_ip and mqtt_port.
        topics: configured topic entries; mutated in place to carry queues.
        stop_event: shared shutdown signal handed to every listener.
    Returns:
        threads: the started listener threads.
    """
    threads = []
    for topic in topics:
        if not topic.get("is_subscribe"):
            continue
        topic["queue"] = Queue()
        threads.append(
            start_subscribe_thread(
                broker["mqtt_ip"],
                broker["mqtt_port"],
                topic["topic"],
                topic["queue"],
                stop_event,
            )
        )
    return threads


def next_trigger(topics: list):
    """Poll every trigger queue once and return the first payload waiting.

    Args:
        topics: configured topic entries, after `start_subscribers` has run.
    Returns:
        message: the decoded payload, or None when no trigger is waiting or the
            payload was not valid JSON.
    """
    for topic in topics:
        if not topic.get("is_trigger") or "queue" not in topic:
            continue
        try:
            payload = topic["queue"].get_nowait()
        except Empty:
            continue
        try:
            return loads(payload)
        except (JSONDecodeError, TypeError) as exc:
            info(f"Discarding malformed payload on {topic['topic']}: {exc}")
            print(f"Discarding malformed payload on {topic['topic']}: {exc}")
    return None


def output_topics(topics: list) -> list:
    """Return the topic strings this service publishes to.

    Args:
        topics: configured topic entries.
    Returns:
        the topic strings whose `is_subscribe` flag is false.
    """
    return [topic["topic"] for topic in topics if not topic.get("is_subscribe")]


def worker_process_function(client: MQTTClient, message: dict, outputs: list) -> None:
    """Replace this with your service's work.

    Args:
        client: connected MQTT client, for publishing results.
        message: the decoded trigger payload.
        outputs: topic strings this service publishes to.
    """
    print("insert your program here")


def main():
    config = loadConfig.get_config()
    broker = require(config, "broker_details")
    topics = require(config, "topics")

    client = MQTTClient(MQTTConfig(host=broker["mqtt_ip"], port=broker["mqtt_port"]))
    client.connect()

    outputs = output_topics(topics)
    stop_event = Event()
    threads = start_subscribers(broker, topics, stop_event)

    try:
        while True:
            time.sleep(0.1)

            message = next_trigger(topics)
            if message is None:
                continue

            worker_process_function(client, message, outputs)

    except KeyboardInterrupt:
        print("Shutting down subscribe listener and exiting.")
    finally:
        stop_event.set()
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=2)


if __name__ == "__main__":
    main()
