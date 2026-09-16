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


def topic_named(topics: list, name: str) -> str:
    """Return the topic string declared under `name`.

    Topics are matched by their `name`, not their position or their text, so a
    deployment can point this service anywhere without the code knowing which
    entry carries what.

    Args:
        topics: the `mqtt.topics` entries.
        name: the `name:` to find.
    Raises:
        SystemExit: when no entry carries that name, or it carries no topic.
            Refusing here costs a startup; discovering it later means a service
            that connects, reports itself healthy and publishes into nothing.
    """
    for topic in topics:
        if topic.get("name") != name:
            continue
        value = topic.get("topic")
        if not value:
            raise SystemExit(
                f"The topic named '{name}' declares no topic string")
        return value
    raise SystemExit(
        f"No topic named '{name}'. This service looks its topics up by name; "
        f"add `- name: {name}` under mqtt.topics.")


def read_settings(config: dict) -> dict:
    """Everything this service needs from its configuration, validated up front.

    All of it, before the broker is touched. Read a key inside the loop instead
    and a config missing it starts the service, connects it, subscribes it, and
    kills it on the first message that arrives -- which is the worst place to
    find out, because everything up to then looked healthy. inference-service
    shipped exactly that with `on_capture`.

    **Extend this when you write your service.** Every `mqtt.topics` name you
    use and every `service.*` key you read belongs here, resolved with
    `topic_named` and `require`, so a misconfigured deployment costs a startup
    rather than a shift. The orchestrator's contract tests find this function by
    name and check the whole of what it returns; without it they can only check
    the four keys every service shares.

    Args:
        config: the whole configuration mapping.
    Returns:
        the settings main() runs on.
    Raises:
        SystemExit: naming the first key that is missing, and the file.
    """
    mqtt_config = require(config, "mqtt")
    topics = require(mqtt_config, "topics")
    require(config, "service")

    return {
        "broker_ip": require(mqtt_config, "mqtt_ip"),
        "broker_port": require(mqtt_config, "mqtt_port"),
        "topics": topics,
        "outputs": output_topics(topics),
    }


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

    # All of it, before the broker is touched: a missing key then costs a
    # startup rather than killing the service on its first message.
    settings = read_settings(config)
    mqtt_config = config["mqtt"]
    topics = settings["topics"]
    outputs = settings["outputs"]

    client = MQTTClient(
        MQTTConfig(host=settings["broker_ip"], port=settings["broker_port"]))
    client.connect()

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
