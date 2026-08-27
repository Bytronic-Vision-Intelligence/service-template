#!/usr/bin/env bash
#
# Thin wrapper around act. Everything after `run.sh` is passed straight through,
# so any act flag works: -l, --dryrun, -j <job>, -v, etc.

set -euo pipefail

WORKFLOWS="${WORKFLOWS_DIR:-.github/workflows}"

# windows-latest is mapped onto a Linux image so the job graph still resolves
# and you can watch the ordering. That leg does NOT prove anything about
# Windows — only GitHub's real runner does.
exec act \
  -W "$WORKFLOWS" \
  -P ubuntu-latest=catthehacker/ubuntu:act-latest \
  -P ubuntu-24.04=catthehacker/ubuntu:act-24.04 \
  -P ubuntu-22.04=catthehacker/ubuntu:act-22.04 \
  -P windows-latest=catthehacker/ubuntu:act-latest \
  --container-architecture linux/amd64 \
  --artifact-server-path /artifacts \
  --rm \
  "$@"
