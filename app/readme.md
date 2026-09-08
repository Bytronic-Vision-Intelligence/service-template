# Application

`main.py` is the entrypoint. It reads `config.yaml` from the directory the
service runs from, connects to the broker, starts one subscriber thread per subscribed
topic, and calls `worker_process_function` for every trigger message.

## What to edit

`worker_process_function(client, message, outputs)` is the only function a new
service needs to replace. It receives the connected MQTT client, the decoded
trigger payload, and the topic strings this service publishes to.

Everything else is deliberately small and testable:

| Function | Purpose |
|---|---|
| `require(config, key)` | fetch a required key, or exit naming it and the config file |
| `start_subscribers(broker, topics, stop_event)` | one queue and thread per `is_subscribe` topic |
| `next_trigger(topics)` | poll the `is_trigger` queues once; decoded payload or `None` |
| `output_topics(topics)` | the topics this service publishes to |

`next_trigger` returns `None` both when nothing is waiting and when a payload
was not valid JSON. Malformed payloads are logged and dropped rather than
killing the loop.

Config is read inside `main()`, not at import time, so `main.py` can be
imported by tests without a config file present.

## Configuration

`dependencies/loadConfig.py`:

- `service_root()` — the directory the service runs from: beside the binary when
  frozen, the repository root from source
- `resolve_config_path(supplied)` — the supplied path, or `config.yaml` beside
  the binary. An empty supplied path is refused, never defaulted
- `config_path()` — the file actually in use, for error messages
- `load_yaml(path)` — parses a YAML mapping; `{}` if missing, empty, or not a mapping
- `get_config()` — the config; exits, naming the directory, if it is absent
- `return_config_value(key)` — one value; re-reads the file on each call
- `parse_cli(argv)` — handles `--help` and `--config PATH`

A missing config is a hard error rather than an empty dict: the orchestrator
writes that file when it launches a service, so its absence means the
deployment is broken. Starting anyway would bring the service up subscribed to
nothing and publishing nowhere, looking healthy to anything watching it.

`service_root()` uses `sys.executable` rather than `__file__` because once
PyInstaller has frozen the service `__file__` points inside a temporary
extraction directory — so a config resolved from it is neither the operator's
file nor present after the process exits.

## Running

```bash
cp dependencies/config.yaml ../config.yaml   # a starting point
python main.py
```

See the repository [README](../Readme.md) for the orchestrator layout.
