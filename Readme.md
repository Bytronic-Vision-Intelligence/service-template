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

Run it, with a `config.yaml` in the repository root:

```bash
cp app/dependencies/config.yaml ./config.yaml   # a starting point
python app/main.py
```

Run the tests:

```bash
python -m pytest test
```

## Configuration

**A service reads `config.yaml` from the directory it runs from, and nowhere
else.** There is no `--config` flag, because there is nothing to choose
between: service-orchestrator writes that file from its own config, which is
the single source of truth.

| | Where `config.yaml` is read from |
|---|---|
| deployed | beside the binary, in the service's own directory |
| from source | the repository root |
| missing | the service refuses to start, naming the directory it looked in |

Starting unconfigured would be worse than not starting: the service would come
up subscribed to nothing, publishing nowhere, and look healthy to anything
watching it.

`app/dependencies/config.yaml` is **not** deployment config. It documents the
shape of a section, and the release package ships a copy beside the binary as a
starting point which the orchestrator then overwrites.

Finding "beside the binary" is the one subtle part: once frozen, `__file__`
points inside PyInstaller's temporary extraction directory, so a config
resolved from it is neither the operator's file nor present after the process
exits. `service_root()` uses `sys.executable` instead.

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

1. Read `config.yaml` from its own directory (`loadConfig.get_config()`)
2. Keep its entrypoint at `app/main.py`
3. Carry its own virtualenv at `.venv/`
4. Use a directory name matching its config section, minus any `-2`/`-3`
   instance suffix — instances share one directory and get `config.yaml`,
   `config-2.yaml`, and so on
5. Leave `/config.yaml` and `/config-*.yaml` gitignored

## Releasing

`.github/workflows/release-pipeline.yml` builds a binary for Linux, Windows and
macOS, packages each with `config.yaml` and a `logs/` folder, signs every zip
with the shared SERVICE key and publishes them as a GitHub release.

**It triggers on a push to `prod`, and `prod` must contain the workflow file.**

GitHub runs a branch-triggered workflow as it exists *on the branch that was
pushed*. A `prod` branch created before this pipeline existed does not contain
it, so pushing to `prod` runs whatever workflows that branch does have and this
one never fires -- no error, no run, no release, nothing to notice. That is the
entire reason two finished pipelines in this organisation have never produced a
release. Keep `prod` current with `main`.

Two things must be set before a release can succeed:

- `SERVICE_SIGNING_KEY` -- a repository secret holding the private half of the
  shared SERVICE signing key. It is a repository secret rather than an
  organisation one because the service repositories are a mix of public and
  private, and on the current plan an organisation secret reaches only the
  public ones -- silently covering three of eight.
- `EXPECTED_PUBLIC_KEY` in `scripts/sign.py` -- the matching public half,
  committed in the open.

Signing refuses to run unless both are present and they agree. A secret pasted
from the wrong place is otherwise invisible: it produces perfectly valid
signatures that the orchestrator refuses months later, on a customer machine,
naming a binary that was never at fault.

Dependencies are split so that none of this reaches a customer:
`requirements.txt` is runtime-only and is what gets built into the binary,
`requirements-dev.txt` adds the test tooling, and `requirements-signing.txt` is
installed only by the release job.

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
