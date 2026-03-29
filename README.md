# Agent Runtime

[中文](README.zh-CN.md) | **English**

---

An experimental multi-agent runtime for code-oriented workflows.

The project is organized into explicit layers:

- `app`: CLI entry and output rendering
- `runtime`: execution kernel and public integration APIs
- `workflow`: agent-to-agent flow skeleton
- `agents`: role-specific reasoning and actions
- `state`: session, memory, history, and runtime state
- `observability`: logs, metrics, and trace output

You can use it in two ways:

- run it directly from the command line
- import it as a Python runtime library

## Project Layout

Core code lives in:

- [agent-runtime/](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime)

Most important entry points:

- CLI entry: [agent-runtime/main.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/main.py)
- Public runtime facade: [agent-runtime/runtime/__init__.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/__init__.py)
- Runtime implementation: [agent-runtime/runtime/api.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/api.py)
- Multi-turn example: [agent-runtime/examples/multi_turn_conversation/run_all_turns.sh](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/examples/multi_turn_conversation/run_all_turns.sh)

## Direct Usage

### 1. CLI

Basic usage:

```bash
python agent-runtime/main.py "write a python function called greet_user(name) that returns Hello, {name}!"
```

With explicit session identity:

```bash
python agent-runtime/main.py \
  --user-id demo-user \
  --conversation-id demo-conversation \
  "write a python function called greet_user(name) that returns Hello, {name}!"
```

Resume the same conversation:

```bash
python agent-runtime/main.py \
  --resume \
  --conversation-id demo-conversation \
  "keep greet_user and add greet_formally(name, title)"
```

With uploaded files:

```bash
python agent-runtime/main.py \
  --file path/to/input.py \
  "optimize this uploaded python code"
```

The CLI will:

- parse arguments
- restore or create a session
- call the runtime
- persist the session
- print generated code, runtime summary, and trace summary

### 2. Example Scenario

Run the bundled multi-turn example:

```bash
bash agent-runtime/examples/multi_turn_conversation/run_all_turns.sh
```

This demonstrates:

- turn 1 session creation
- turn 2 resume
- turn 3 resume
- final session inspection

Related example docs:

- [agent-runtime/examples/multi_turn_conversation/README.md](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/examples/multi_turn_conversation/README.md)

## Public Runtime API

If you want to integrate this project as a Python library, import from:

- [agent-runtime/runtime/__init__.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/__init__.py)

Current public entry points:

- `create_task_state(...)`
- `run_task(...)`
- `run_queued_tasks(...)`
- `run_conversation_turn(...)`
- `build_runtime_container(...)`

The underlying implementations live in:

- [agent-runtime/runtime/api.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/api.py)
- [agent-runtime/runtime/container.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/container.py)

### Single Turn

```python
from runtime import run_task

state = run_task(
    "write a python function called greet_user(name) that returns Hello, {name}!",
    user_id="demo-user",
    conversation_id="demo-conversation",
    turn_id=1,
)

print(state.generated_code)
print(state.test_result)
```

### Multi-Turn Conversation

```python
from runtime import run_conversation_turn

state = run_conversation_turn(
    "write a python function called greet_user(name) that returns Hello, {name}!",
    user_id="demo-user",
    conversation_id="demo-conversation",
    turn_id=1,
)

state = run_conversation_turn(
    "keep greet_user and add greet_formally(name, title)",
    state=state,
)

print(state.generated_code)
print(state.test_result)
```

### Queued Batch Execution

Use this when you want to submit multiple independent tasks at once and let the
runtime execute them through its in-memory queue.

This is useful for:

- quick batch experiments
- queue and dispatch testing
- measuring runtime-level scheduling behavior

This is not the right API for multi-turn conversation continuation. For
multi-turn conversation, use `run_conversation_turn(...)` instead.

```python
from runtime import run_queued_tasks

results = run_queued_tasks([
    {"user_request": "write a python clamp function", "task_id": "task-1"},
    {"user_request": "write a python slugify function", "task_id": "task-2"},
])

for state in results:
    print(state.task_id, state.test_result)
```

What happens here:

1. each dictionary becomes one independent task request
2. the runtime pushes them into an in-memory queue
3. the scheduler runs them one by one
4. the function returns a list of final `TaskState` objects

So `results` is a list of task results, not a conversation history.

### Custom Runtime Container

If you want to replace pieces such as:

- agent registry
- tool registry
- skill manager
- workflow manager

build a custom container first, then pass it into `AgentRuntime` or the `run_*`
APIs.

Entry point:

- [agent-runtime/runtime/container.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/container.py)

## Execution Path

Current main path:

```text
main.py
-> app/cli.py
-> runtime/api.py
-> runtime/engine.py
-> runtime/container.py
-> agent.run(state)
-> workflow.resolve_next(...)
-> loop until completion
```

More concretely:

1. `main.py` forwards to the CLI
2. the CLI parses input and restores session state
3. `runtime/api.py` creates or resumes `TaskState`
4. `runtime/engine.py` starts the agent loop
5. `orchestrator` owns task understanding and planning
6. `workflow` owns agent-to-agent transitions
7. `runtime` owns execution, dispatch, wiring, and cleanup

## Design Boundary

The current intended boundary is:

- `agents` keep their own reasoning
- `workflow` keeps only the flow skeleton
- `runtime` keeps execution management and public APIs

So when adding a new agent, the normal change surface should mainly be:

1. the agent implementation in `agents/`
2. registry registration in `runtime`
3. workflow integration in `workflow`

You should not need to redesign runtime execution flow for each new agent.

## Current Status

The project already supports:

- multi-agent coordination
- shared `TaskState`
- single-turn and multi-turn sessions
- session persistence and resume
- runtime metrics and traces
- a basic research / coder / tester / fix loop
- constrained sandbox execution

It is still a prototype, but it is already usable for realistic multi-turn code workflow experiments.

## Known Limitations

This project is now in a good place to wrap up as an architecture and runtime
prototype, but there are still some known limitations:

- the `runtime`, `workflow`, session persistence, and agent dispatch layers are
  already structured and usable
- the `tester -> fix -> tester` quality loop is still evolving, and some
  multi-turn code tasks may still fail to repair cleanly
- scripts in `examples/` are best treated as runnable demos and flow examples,
  not as strict benchmarks for final code quality
- some validation still depends on a mix of rule-based checks and LLM
  judgment, so behavior-level correctness is not fully deterministic yet

In short:

- the architecture is stable enough to present and extend
- the code-generation and auto-repair quality chain is still the main area for
  future improvement
