#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SESSION_DIR="$ROOT_DIR/.agent-runtime/example-sessions"
CONVERSATION_ID="multi-turn-demo"
USER_ID="demo-user"
QUESTION_FILE="$ROOT_DIR/agent-runtime/examples/multi_turn_conversation/questions/turn1.txt"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

mkdir -p "$SESSION_DIR"

"$PYTHON_BIN" "$ROOT_DIR/agent-runtime/main.py" \
  --user-id "$USER_ID" \
  --conversation-id "$CONVERSATION_ID" \
  --turn-id 1 \
  --session-dir "$SESSION_DIR" \
  "$(cat "$QUESTION_FILE")"
