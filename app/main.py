import time
from json import JSONDecodeError, loads
from logging import info, warning
from queue import Empty, Queue
from threading import Event

from mqtt_client import MQTTClient, MQTTConfig

from dependencies import loadConfig, logging_setup
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
    # `is None` as well as absent: a key present but empty is a section
    # somebody meant to fill in, and letting it through moves the failure to
    # whatever first subscripts it.
    if key not in config or config[key] is None:
        # Named only if one has been loaded. require() is also called on
        # nested sections in contexts that never parsed arguments, and
        # config_path() refuses to guess there -- which would replace this
        # message with one about the wrong problem entirely.
        try:
            where = f" in {loadConfig.config_path()}"
        except SystemExit:
            where = ""
        raise SystemExit(f"Missing required config key '{key}'{where}")
    return config[key]


def start_subscribers(mqtt_config: dict, topics: list, stop_event: Event) -> list:
    """Start one listener thread per subscribed topic.

    Each topic entry with `is_subscribe` true gains a `queue` key, which
    `next_trigger` later reads from.

    Args:
        mqtt_config: the `mqtt` section, carrying mqtt_ip and mqtt_port.
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
                mqtt_config["mqtt_ip"],
                mqtt_config["mqtt_port"],
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
            warning(f"Discarding malformed payload on {topic['topic']}: {exc}")
    return None


def output_topics(topics: list) -> list:
    """Return the topic strings this service publishes to.

    Args:
        topics: configured topic entries.
    Returns:
        the topic strings whose `is_subscribe` flag is false.
    """
    return [topic["topic"] for topic in topics if not topic.get("is_subscribe")]


def service_process_function(client: MQTTClient, message: dict, outputs: list) -> None:
    """Replace this with your service's work.

    Args:
        client: connected MQTT client, for publishing results.
        message: the decoded trigger payload.
        outputs: topic strings this service publishes to.
    """

    # insert your service's work here

    return None


def main(argv=None):
    args = loadConfig.parse_cli(argv)

    config = loadConfig.get_config(args.config)

    log_settings = config.get("logging") or {}
    logging_setup.configure(log_settings.get("level", logging_setup.DEFAULT_LEVEL))

    mqtt_config = require(config, "mqtt")
    topics = require(mqtt_config, "topics")
    require(config, "service")

    client = MQTTClient(
        MQTTConfig(host=mqtt_config["mqtt_ip"], port=mqtt_config["mqtt_port"]))
    client.connect()

    outputs = output_topics(topics)
    stop_event = Event()
    threads = start_subscribers(mqtt_config, topics, stop_event)

    try:
        while True:
            time.sleep(0.1)

            message = next_trigger(topics)
            if message is None:
                continue

            service_process_function(client, message, outputs)

    except KeyboardInterrupt:
        info("Shutting down subscribe listener and exiting.")
    finally:
        stop_event.set()
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=2)


if __name__ == "__main__":
    main()
