# Application

`main.py` is the entrypoint. It loads the config selected by `--config` or
`--test`, connects to the broker, starts one subscriber thread per subscribed
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

- `config_path()` — resolves `--config <path>`, else `--test`, else exits
- `load_yaml(path)` — parses a YAML mapping; `{}` if missing, empty, or not a mapping
- `get_config()` — the resolved config; exits if the selected file is absent
- `return_config_value(key)` — one value; re-reads the file on each call

A missing `--config` file is a hard error rather than an empty dict, because
service-orchestrator passes a path it has just written — if it is not there,
the deployment is broken.

## Running

```bash
python app/main.py --config /path/to/config.yaml   # deployment
python app/main.py --test                          # bundled example config
```

See the repository [README](../Readme.md) for the orchestrator layout.
