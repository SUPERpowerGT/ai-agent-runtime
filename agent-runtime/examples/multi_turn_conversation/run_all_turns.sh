#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SESSION_DIR="$ROOT_DIR/.agent-runtime/example-sessions"
SESSION_FILE="$SESSION_DIR/multi-turn-demo.json"
REGISTRY_FILE="$SESSION_DIR/registry.json"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

mkdir -p "$SESSION_DIR"
rm -f "$SESSION_FILE"
rm -f "$REGISTRY_FILE"

echo "[multi-turn] running turn 1"
bash "$ROOT_DIR/agent-runtime/examples/multi_turn_conversation/run_turn1.sh"

echo "[multi-turn] running turn 2"
bash "$ROOT_DIR/agent-runtime/examples/multi_turn_conversation/run_turn2.sh"

echo "[multi-turn] running turn 3"
bash "$ROOT_DIR/agent-runtime/examples/multi_turn_conversation/run_turn3.sh"

echo "[multi-turn] inspecting saved session"
"$PYTHON_BIN" "$ROOT_DIR/agent-runtime/examples/multi_turn_conversation/inspect_session.py"
