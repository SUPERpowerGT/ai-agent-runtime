# Multi-Agent Runtime Framework

A lightweight multi-agent runtime prototype for exploring task orchestration, shared state, retrieval, code generation, validation, and repair around an LLM-driven workflow.

## Overview

This project explores a runtime model where multiple agents collaborate over a shared `TaskState` blackboard instead of passing isolated prompts back and forth.

The current codebase already supports:

- a shared `TaskState` for workflow control, outputs, memory, artifacts, and tracing
- a unified `BaseAgent` lifecycle: `before_run -> perceive -> think -> validate_output -> act -> after_run`
- a runtime loop and registry-based dispatch
- local file RAG for uploaded documents
- web search via DuckDuckGo
- language-specific code analysis adapters
- a tester/fix validation loop for failed code generations
- runtime metrics, trace records, and structured logging

This is still a prototype framework, but it has moved beyond a bare skeleton. The runtime, research, coder, tester, and fix path are now wired together well enough for realistic experiments.

## Why This Project

LLM applications become hard to reason about when planning, retrieval, validation, repair, and safety all live inside one prompt loop.

This project separates those concerns into runtime-level abstractions so they can be:

- observed
- extended
- tested
- audited
- replaced independently

The design goals are:

- coordinate multiple agents through a shared state object
- standardize agent execution with a common contract
- keep retrieval, validation, repair, and routing explicit
- support future language adapters, sandboxes, and richer tools

## Architecture

### Core runtime pieces

- `TaskState`: shared blackboard for plan, next agent, outputs, artifacts, memories, errors, and trace data
- `BaseAgent`: common lifecycle contract for every agent
- `AgentRuntime`: dispatch loop that runs agents until completion or stop conditions
- `registry`: runtime registry used to look up agents by name
- `runtime/api.py`: reusable entry points such as `run_task(...)`

### Runtime layers

- `runtime/bootstrap/`: bootstrap wiring for agents and tools
- `runtime/services/`: LLM, logging, task-spec, retrieval, repair, and language analysis helpers
- `runtime/policies/`: execution and routing policies such as plan normalization and tester/fix transitions

### Current agent roles

- `OrchestratorAgent`: plans the main execution path
- `ResearchAgent`: retrieves local document context and web context, then summarizes it
- `CoderAgent`: generates or rewrites code from task spec + research context
- `TesterAgent`: validates code with a layered approach
- `FixAgent`: repairs code using a structured failure report and fix strategy
- `SecurityAgent`: placeholder for security-oriented validation

## Execution Model

The runtime centers around a shared `TaskState`.

1. The runtime reads `state.next_agent`
2. The registry resolves that agent
3. The agent reads from shared state during `perceive`
4. The agent reasons during `think`
5. The output is normalized in `validate_output`
6. The agent updates state in `act`
7. The runtime loops until `finished` or `max_steps`

For code-oriented tasks, the common happy path is:

```text
orchestrator -> research -> coder -> tester
```

If validation fails, the runtime can branch into:

```text
tester -> fix -> tester
```

The planner does not need to put `fix` into the main plan; that route is handled by runtime policy.

## Shared State

`TaskState` includes:

- workflow control: `plan`, `current_agent`, `next_agent`, `finished`, `step_count`
- task outputs: `task_spec`, `generated_code`, `test_result`, `security_report`
- retrieval state: `uploaded_files`, `retrieved_documents`, `rag_context`, `retrieved_context`
- memory: `working_memory`, `history`, `agent_memories`, `messages`
- artifacts: `tool_calls`, `artifacts`, `agent_outputs`
- resilience and safety: `error_log`, `retry_count`, `security_events`
- observability: `trace`, `metrics`

This makes the runtime behave more like a small agent operating system than a thin prompt wrapper.

## Agent Lifecycle

Every agent built on `BaseAgent` follows the same structure:

```text
before_run
  -> perceive
  -> think
  -> validate_output
  -> act
  -> after_run
```

This keeps reasoning, validation, and mutation separate and makes it easier to add:

- output guards
- trace hooks
- metrics
- tool logging
- policy-driven routing

## Retrieval and RAG

The runtime supports a lightweight local-document RAG flow.

### What it can read

Current supported uploaded file types:

- `.txt`
- `.md`
- `.py`
- `.json`
- `.yaml`
- `.yml`

### Current retrieval flow

- files are loaded from `--file <path>`
- documents are chunked
- relevant chunks are selected with a lightweight keyword-based retriever
- `ResearchAgent` uses those chunks plus web search results
- extracted code contracts and behavior summaries are written back into `TaskState`

This is intentionally a lightweight MVP. It is not yet an embedding/vector-store setup.

## Language Adapters

Language-specific code understanding now lives behind adapters in:

- `agent-runtime/runtime/services/languages/`

The current active adapter is:

- `python.py`

It provides:

- code contract extraction
- behavior summary extraction
- static consistency checks

The adapter registry is defined in:

- [agent-runtime/runtime/services/languages/__init__.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/services/languages/__init__.py)

### Adding a new language

1. Create `runtime/services/languages/<language>.py`
2. Implement:
   - `extract_code_contracts`
   - `extract_behavior_summaries`
   - `check_static_consistency`
3. Register a `LanguageAdapter` in `runtime/services/languages/__init__.py`

A starter template already exists for JavaScript:

- [agent-runtime/runtime/services/languages/javascript.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/services/languages/javascript.py)

## Tester and Fix Loop

The validation path is intentionally layered.

### Tester responsibilities

`TesterAgent` is a validator, not a code generator.

It currently combines:

- contract checks
- language-specific static consistency checks
- LLM semantic judgment

When validation fails, it produces:

- a structured `failure_report`
- a derived `fix_strategy`

These are written into runtime artifacts and consumed by `FixAgent`.

### Fix responsibilities

`FixAgent` does not invent its own repair policy. It consumes:

- the latest validation failure
- the structured failure report
- the fix strategy
- extracted code contracts
- extracted behavior summaries

This keeps repair logic more general and less tied to one specific bug pattern.

### Retry stopping

The runtime now includes an early-stop rule for retry loops.

If failures repeat without meaningful progress, the runtime stops retrying instead of always using the full retry budget.

## Observability

The runtime records:

- per-stage trace entries
- per-agent run counts
- per-agent durations
- total LLM calls
- LLM time by agent
- tool calls
- errors and security events

Console logs are intentionally structured:

- `[runtime] ...`
- `[agent:<name>] ...`
- `[tool:<name>] ...`
- `[llm:<name>] ...`

This makes it easier to distinguish dispatch, tool usage, and model latency.

## Repository Layout

```text
agent-runtime/
├── agents/                    # Agent implementations and BaseAgent
├── examples/
│   └── uploads/               # Sample uploaded files for RAG/manual tests
├── infra/                     # Config and compatibility shims
├── runtime/
│   ├── bootstrap/             # Agent/tool bootstrap wiring
│   ├── legacy/                # Older runtime leftovers kept for reference
│   ├── policies/              # Routing and transition policies
│   ├── services/              # LLM, logging, retrieval, repair, language adapters
│   ├── api.py                 # Reusable runtime entry points
│   ├── engine.py              # Runtime loop
│   └── registry.py            # Agent registry
├── state/                     # TaskState and record models
├── tools/                     # Tool abstractions and providers
└── main.py                    # CLI-style demo runner
```

## Running the Project

### 1. Install dependencies

Using `uv`:

```bash
uv sync
```

Or install with your preferred Python environment from `pyproject.toml`.

### 2. Start a local OpenAI-compatible model endpoint

The default config expects Ollama on:

```text
http://127.0.0.1:11434/v1
```

Current defaults:

```python
BASE_URL = "http://127.0.0.1:11434/v1"
API_KEY = "ollama"
MODEL = "llama3"
```

Update `agent-runtime/infra/config.py` if needed.

### 3. Run the demo runner

Without uploaded files:

```bash
python agent-runtime/main.py
```

With an explicit request:

```bash
python agent-runtime/main.py "write a python function called is_even(n) that returns True for even numbers and False for odd numbers"
```

With uploaded files:

```bash
python agent-runtime/main.py \
  --file agent-runtime/examples/uploads/test1.py \
  --file agent-runtime/examples/uploads/test2.py \
  --file agent-runtime/examples/uploads/context.md \
  "optimize the uploaded python code and keep the same behavior"
```

## Using the Runtime as an API

You can call the runtime directly from Python instead of using `main.py`.

```python
from runtime import run_task

result = run_task(
    "write a python function called is_even(n) that returns True for even numbers and False for odd numbers"
)

print(result.generated_code)
print(result.test_result)
```

With uploaded files:

```python
from runtime import run_task

result = run_task(
    "optimize the uploaded python code and keep the same behavior",
    uploaded_files=[
        "agent-runtime/examples/uploads/test1.py",
        "agent-runtime/examples/uploads/test2.py",
        "agent-runtime/examples/uploads/context.md",
    ],
)
```

## Good Manual Test Cases

Useful requests for exploring the current prototype:

- `write a python function that returns "hello world" without printing anything`
- `write a python function called is_even(n) that returns True for even numbers and False for odd numbers`
- `write a python function called clamp(value, min_value, max_value) that returns min_value if value is too small, max_value if value is too large, otherwise return value. do not use min() or max()`
- `optimize the uploaded python code and keep the same behavior`
- `rewrite the uploaded order calculation code in javascript`

## Current Status

Working well enough to explore:

- shared runtime state
- planner/research/coder/tester/fix flow
- local uploaded-file RAG
- language adapter structure
- structured validation and repair handoff
- tracing, timing, and logging

Still evolving:

- richer non-Python language adapters
- Python sandbox execution for real runtime tests
- stronger semantic validation beyond heuristic behavior checks
- broader automated test coverage
- more polished CLI / demo UX

## Notes

This repository is best understood as an evolving systems prototype. The runtime abstractions, shared state model, RAG path, and validation/repair pipeline are currently the most mature parts.

## License

Add a project license here if you plan to distribute or open-source the framework publicly.
