# Bytronic microservice template

A minimal Python MQTT worker template. Clone it to start a new service, then
replace `worker_process_function` in `app/main.py` with your own work.

## Prerequisites

- Python 3.10 or newer
- An MQTT broker, normally at `localhost:1883`

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run standalone against the bundled example config:

```bash
python app/main.py --test
```

Run the tests:

```bash
python -m pytest test
```

## Configuration

The service takes its config from a file and will not start without one:

| Invocation | Config used |
|---|---|
| `python app/main.py --config <path>` | the supplied file — how deployment works |
| `python app/main.py --test` | `app/dependencies/config.yaml`, the bundled example |
| `python app/main.py` | none; exits with an error |

`app/dependencies/loadConfig.py` exposes `get_config()` and
`return_config_value(key)`. Prefer a single `get_config()` call — the accessor
re-reads the file each time.

Required top-level keys are `broker_details` (`mqtt_ip`, `mqtt_port`) and
`topics`. Each topic entry carries `is_subscribe` (this service listens on it)
and `is_trigger` (a message here starts a unit of work).

### Running under service-orchestrator

In deployment, [service-orchestrator](https://github.com/Bytronic-Vision-Intelligence/service-orchestrator)
owns configuration. It writes each section of its own `config.yaml` into the
service directory and launches the service with that path:

```
service-orchestrator/
├── config.yaml          # section per service instance
├── service-template/    # this repo, cloned
│   ├── .venv/
│   ├── config.yaml      # written by the orchestrator, never committed
│   └── app/main.py
```

To take part, a service must:

1. Accept `--config <path>` on `app/main.py`
2. Keep its entrypoint at `app/main.py`
3. Carry its own virtualenv at `.venv/`
4. Use a directory name matching its config section, minus any `-2`/`-3`
   instance suffix — instances share one directory and get `config.yaml`,
   `config-2.yaml`, and so on
5. Leave `/config.yaml` and `/config-*.yaml` gitignored

## Running CI locally

`docker-local/` runs `.github/workflows/` on your machine through
[nektos/act](https://github.com/nektos/act), so you can check a workflow before
opening a PR. It needs Docker running, and is not tracked in git.

```bash
./docker-local/run.sh -l          # list jobs
./docker-local/run.sh --dryrun    # execution order only
./docker-local/run.sh             # full push event
./docker-local/run.sh -j build    # a single job
./docker-local/run.sh --fresh     # wipe the toolcache first
```

Every run is tee'd to `docker-local/logs/`, with `latest.log` symlinked to the
most recent.

Two caveats. The `windows-latest` leg runs on a Linux image, so it proves job
ordering, not Windows behaviour. And act bind-mounts your working tree instead
of doing a fresh checkout, so anything that depends on what git actually
committed — a file renamed only by case, for instance — can pass locally and
still fail on GitHub.

## Project layout

- `app/` — application code
  - `main.py` — entrypoint; edit `worker_process_function`
  - `dependencies/loadConfig.py` — config resolution and access
  - `dependencies/mqtt_functions.py` — subscriber threads
  - `dependencies/config.yaml` — bundled example config
- `docs/` — documentation and licence
- `test/` — pytest suite
- `tools/` — helper scripts

License: see `docs/LISENCE`.
