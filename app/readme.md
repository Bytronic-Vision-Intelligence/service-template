# Application

`main.py` is the entrypoint. It runs the config named by `--config`, which is
required, connects to the broker, starts one subscriber thread per subscribed
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

- `resolve_config_path(supplied)` — the path from `--config`. Empty or missing
  is refused, never defaulted
- `config_path()` — the file in use, for error messages
- `load_yaml(path)` — parses a YAML mapping; `{}` if missing, empty, or not a mapping
- `get_config(supplied)` — the config; exits if none was named or the file is absent
- `return_config_value(key)` — one value, from the file the service started with
- `parse_cli(argv)` — `--config PATH` (required) and `--help`

There is no fallback, and that is the point. A service that found a config
beside itself would start whenever one happened to be there — a stale copy from
a previous deployment, the packaged example, or another instance's file in a
shared directory — and would be the wrong service while looking healthy.

A missing config is likewise a hard error rather than an empty dict: the
orchestrator writes that file when it launches a service, so its absence means
the deployment is broken.

## Running

```bash
python main.py --config ../config.yaml
```

See the repository [README](../Readme.md) for the orchestrator layout.
