#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${TEENSY_IO_TEST_VENV:-/tmp/teensy-io-test-venv}"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/testing/requirements.txt"
cd "$ROOT_DIR"
"$VENV_DIR/bin/python" -m pytest "$@"
