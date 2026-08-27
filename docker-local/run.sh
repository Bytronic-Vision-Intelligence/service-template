#!/usr/bin/env bash
#
# Run .github/workflows/ locally.
#
#   ./run.sh -l                 list jobs
#   ./run.sh --dryrun           show execution order without running anything
#   ./run.sh                    run the push event end to end
#   ./run.sh -j build           run one job
#   ./run.sh pull_request       run a different event
#   ./run.sh --fresh            wipe the toolcache first, resolve deps from scratch
#
# Every run is tee'd to logs/ — the container is --rm, so without this the
# output dies with it.
#
# windows-latest legs execute on a Linux image — ordering is real, the OS isn't.
#
# This folder is repo-agnostic: PROJECT_NAME is derived from the directory
# name, so it drops into any service repo unedited.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

REPO_ROOT="$(cd .. && pwd)"
export REPO_ROOT

PROJECT_NAME="$(basename "$REPO_ROOT")"
export PROJECT_NAME

if [ "${1:-}" = "--fresh" ]; then
  shift
  # act keeps /opt/hostedtoolcache in a named volume, and pip installs into it.
  # Without this, a run can pass on packages a previous run left behind.
  docker volume rm -f act-toolcache >/dev/null 2>&1 || true
  echo "==> wiped act-toolcache: this run resolves every dependency from scratch"
fi

mkdir -p artifacts logs

LOG="logs/act-$(date +%Y%m%d-%H%M%S).log"
ln -sf "$(basename "$LOG")" logs/latest.log

# Strip ANSI + CR so the saved log is greppable; the terminal still gets colour.
docker compose run --rm --build act "$@" 2>&1 \
  | tee >(perl -pe 's/\e\[[0-9;]*m//g; s/\r//g' > "$LOG")

exit "${PIPESTATUS[0]}"
