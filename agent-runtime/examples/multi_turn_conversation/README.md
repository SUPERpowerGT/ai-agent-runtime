# Multi-Turn Conversation Example

[中文](README.zh-CN.md) | **English**

---

This folder contains a runnable three-turn example for the current
single-user, single-conversation runtime.

It is mainly useful for demonstrating:

- the same `conversation_id` can be resumed across turns
- the session file is persisted and updated in place
- `turn_id` advances correctly
- previous turns are archived into `history`
- the latest user message becomes the active request for the current turn

This folder is better understood as:

- a runnable end-to-end demo
- a session continuity example
- a lightweight smoke scenario for the current runtime

What it does not fully guarantee yet:

- perfect code quality across all multi-turn generation cases
- fully deterministic repair quality in the `tester -> fix -> tester` loop
- automatic long-term preference extraction into `memory`
- sophisticated session summarization beyond the current archived turn summary

## Files

- `questions/turn1.txt`
- `questions/turn2.txt`
- `questions/turn3.txt`
- `run_turn1.sh`
- `run_turn2.sh`
- `run_turn3.sh`
- `run_all_turns.sh`
- `inspect_session.py`

## Quick Start

From the repository root:

```bash
bash agent-runtime/examples/multi_turn_conversation/run_all_turns.sh
```

This will:

1. create or reset a dedicated example session directory
2. run turn 1
3. resume turn 2
4. resume turn 3
5. inspect the final saved session

## Expected Outcome

At the end of the flow, the inspector should show:

- `turn_id = 3`
- `history_count >= 2`
- `latest_user_message` equals the turn-3 question
- the same `conversation_id` throughout

The generated code itself may still vary between runs because some behavior
depends on LLM output. The more important expectation here is that the runtime
flow, session persistence, and turn continuity remain intact.

## Manual Step-by-Step Run

```bash
bash agent-runtime/examples/multi_turn_conversation/run_turn1.sh
bash agent-runtime/examples/multi_turn_conversation/run_turn2.sh
bash agent-runtime/examples/multi_turn_conversation/run_turn3.sh
python agent-runtime/examples/multi_turn_conversation/inspect_session.py
```
