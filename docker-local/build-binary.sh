#!/usr/bin/env bash
#
# Build the service binary and smoke-test it, the way the release pipeline does.
#
#   ./build-binary.sh
#
# Why this exists separately from run.sh:
#
# act cannot execute the release pipeline's build. The espressif action runs a
# nested Docker step that expects its own files at /github/action/, which act
# does not mount, so a local act run dies with "setup_environment.sh: No such
# file or directory" long before anything is built. See readme.md.
#
# So this reproduces the build directly instead: same Python, same PyInstaller,
# same flags the workflow passes, same `--help` smoke test the action runs.
# That is the check that matters, because the failure mode is a binary that
# BUILDS perfectly and dies on its first import - unit tests cannot see it, and
# neither can anything that only inspects the workflow file.
#
# Runs against a clean copy of the TRACKED tree, so an uncommitted .venv or a
# stale dist/ cannot change the result, and nothing is written to your
# working tree.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

REPO_ROOT="$(cd .. && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/release-pipeline.yml"
PYTHON_VERSION="${PYTHON_VERSION:-3.10}"

# The flags come out of the workflow rather than being repeated here, so this
# tracks what CI actually passes instead of drifting away from it.
SCRIPT_PATH=$(awk -F'"' '/^ *scripts:/ {print $2; exit}' "$WORKFLOW")
EXTRA_ARGS=$(awk -F': ' '/^ *additional-args:/ {sub(/^ +/,"",$2); print $2; exit}' "$WORKFLOW")
# Strip surrounding quotes: `additional-args: ""` must mean no arguments, not a
# literal empty string, which PyInstaller would take as the script name.
EXTRA_ARGS="${EXTRA_ARGS%\"}"; EXTRA_ARGS="${EXTRA_ARGS#\"}"
EXTRA_ARGS="${EXTRA_ARGS%\'}"; EXTRA_ARGS="${EXTRA_ARGS#\'}"
: "${SCRIPT_PATH:?could not read \`scripts:\` from $WORKFLOW}"

echo "==> script:          $SCRIPT_PATH"
echo "==> additional-args: ${EXTRA_ARGS:-(none)}"

TREE="$PWD/.tree"
rm -rf "$TREE"; mkdir -p "$TREE"
(cd "$REPO_ROOT" && git ls-files -z | xargs -0 tar -cf -) | tar -xf - -C "$TREE"

untracked=$(cd "$REPO_ROOT" && git ls-files --others --exclude-standard | wc -l | tr -d ' ')
[ "$untracked" -gt 0 ] && echo "==> note: $untracked untracked file(s) excluded, as CI would"

cat > "$TREE/.build.sh" <<INNER
set -eu
apt-get update -qq && apt-get install -y -qq binutils >/dev/null 2>&1
cd /work
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q pyinstaller
pyinstaller --onefile --distpath=./dist/local ${EXTRA_ARGS} \
  --add-data "./app/dependencies:./app/dependencies" ${SCRIPT_PATH}
INNER

echo "==> building in python:${PYTHON_VERSION}-slim"
# Not piped: a pipeline would report tail's exit status, and a build that died
# would look like a pass. The log is kept and shown only if something fails.
BUILD_LOG="$TREE/.build.log"
if docker run --rm -v "$TREE:/work" "python:${PYTHON_VERSION}-slim" \
     bash /work/.build.sh >"$BUILD_LOG" 2>&1; then
  grep -E "Build complete" "$BUILD_LOG" | tail -1
else
  echo "==> FAIL: PyInstaller did not complete"
  tail -15 "$BUILD_LOG"
  exit 1
fi

BINARY="$TREE/dist/local/$(basename "$SCRIPT_PATH" .py)"
[ -x "$BINARY" ] || { echo "==> FAIL: no binary produced at $BINARY"; exit 1; }
echo "==> built $(du -h "$BINARY" | cut -f1)"

# The action's own smoke test, verbatim: test_executables.sh runs the binary
# with --help and fails the build on a non-zero exit. There is no input to
# change that argument, so a service that cannot answer --help cannot ship.
echo "==> smoke test: --help"
if docker run --rm -v "$TREE:/work" "python:${PYTHON_VERSION}-slim" \
     /work/dist/local/"$(basename "$SCRIPT_PATH" .py)" --help; then
  echo "==> PASS: the binary runs and answers --help"
else
  echo "==> FAIL: the binary was built but does not run. This is exactly what"
  echo "    breaks a release: the build succeeds and only running it shows."
  exit 1
fi
