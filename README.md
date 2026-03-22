# Multi-Agent Runtime Framework

A lightweight multi-agent runtime prototype for exploring task orchestration, shared state management, tool use, tracing, and security-aware execution for LLM applications.

## Overview

This project explores how multiple agents can collaborate over a shared runtime state instead of passing isolated prompts back and forth. The current codebase focuses on the runtime skeleton:

- a shared `TaskState` blackboard for cross-agent coordination
- a unified `BaseAgent` lifecycle (`perceive -> think -> validate -> act`)
- an `AgentRegistry` for runtime dispatch
- tool integration for web search
- trace, metrics, memory, and security-event recording

The repository is intentionally structured as a prototype framework rather than a polished production system. Some components are fully modeled, while others are still evolving.

## Why This Project

LLM applications quickly become hard to control when planning, tool calls, memory, and safety logic are mixed together inside one large prompt loop. This project separates those concerns into runtime-level abstractions so they can be inspected, extended, and audited more clearly.

The design goals are:

- coordinate multiple agents through a shared state object
- standardize agent execution with a common contract
- support memory, tools, tracing, and security events in one runtime
- leave room for future planner / coder / tester / security pipelines

## Architecture

### Core runtime pieces

- `TaskState`: shared blackboard for task identity, plan, outputs, memories, tool calls, errors, trace records, and metrics
- `BaseAgent`: common execution template with lifecycle hooks and output validation
- `AgentRegistry`: runtime registry for agent discovery and instantiation
- `AgentRuntime`: loop that dispatches the next agent until completion or step limit

### Current agent roles

- `OrchestratorAgent`: uses the LLM to generate an execution plan
- `ResearchAgent`: performs web search and summarizes retrieved context
- `CoderAgent`: scaffolded code generation role
- `TesterAgent`: scaffolded validation role
- `FixAgent`: scaffolded repair role
- `SecurityAgent`: scaffolded security scan role

### Tools and infrastructure

- `WebSearchTool`: web search abstraction backed by DuckDuckGo
- `ToolRegistry`: runtime tool lookup
- `runtime/services/llm.py`: OpenAI-compatible LLM service currently configured for local Ollama

## Repository Layout

```text
agent-runtime/
├── agents/          # Agent implementations and BaseAgent
├── infra/           # Config and compatibility shims
├── knowledge/       # Knowledge sources / placeholders
├── memory/          # Memory-related modules
├── runtime/
│   ├── bootstrap/   # Agent/tool bootstrap and registry wiring
│   ├── policies/    # Transition and routing policies
│   ├── services/    # Logging, LLM, task-spec services
│   ├── engine.py    # Runtime loop
│   └── registry.py  # Agent registry
├── state/           # Shared TaskState and record models
├── tools/           # Tool abstractions and providers
├── main.py          # Entry point prototype
└── test_*.py        # Small local scripts for manual testing
```

## Execution Model

The runtime centers around a shared `TaskState` object.

1. The runtime selects `state.next_agent`
2. The selected agent reads from shared state
3. The agent performs planning, retrieval, or action
4. The agent updates shared state
5. The runtime continues until `finished` or `max_steps` is reached

This makes it easier to observe:

- what each agent saw
- what each agent changed
- which tools were called
- what errors or security events occurred

## Shared State Design

`TaskState` is the main blackboard object and includes:

- workflow fields: `plan`, `current_agent`, `next_agent`, `finished`, `step_count`
- output fields: `retrieved_context`, `generated_code`, `test_result`, `security_report`
- memory fields: `working_memory`, `history`, `agent_memories`, `messages`
- observability fields: `trace`, `metrics`, `tool_calls`
- resilience and safety fields: `error_log`, `retry_count`, `security_events`

This lets the runtime behave more like a small agent operating system than a single prompt wrapper.

## Agent Lifecycle

Agents that inherit from `BaseAgent` follow a consistent flow:

```text
before_run
  -> perceive
  -> think
  -> validate_output
  -> act
  -> after_run
```

This design keeps planning, reasoning, validation, and mutation separate and makes it easier to add:

- output guards
- audit hooks
- memory writes
- tool call logging
- future policy layers

## Observability and Safety

The runtime already models several important audit primitives:

- trace records for each execution stage
- tool call records with inputs / outputs / success flags
- per-agent run counters and global step metrics
- security event recording for suspicious or failed execution
- centralized error logging

These pieces are useful for debugging agent behavior and provide a good base for later prompt-injection defense, action policy, or guardrail work.

## LLM and Tooling Setup

The current default config uses an OpenAI-compatible endpoint pointing to local Ollama:

```python
BASE_URL = "http://127.0.0.1:11434/v1"
API_KEY = "ollama"
MODEL = "llama3"
```

Web search is implemented through DuckDuckGo via `ddgs`.

## Getting Started

### 1. Install dependencies

Using `uv`:

```bash
uv sync
```

Or install from `pyproject.toml` with your preferred Python environment.

### 2. Start an OpenAI-compatible local model endpoint

The default config expects Ollama on:

```text
http://127.0.0.1:11434/v1
```

If needed, update `agent-runtime/infra/config.py`.

### 3. Run a small local script

The repository currently includes small script-style entry points for manual testing:

```bash
python agent-runtime/test.py
python agent-runtime/test_research_agent.py
```

These scripts are the most reliable starting point for exploring the current prototype.

## Current Status

Implemented well enough to explore:

- shared runtime state modeling
- agent registry and dispatch concepts
- orchestrator planning flow
- research agent + web search integration
- tracing, metrics, error, and security-event data structures

Still being refined:

- end-to-end runtime entry flow in `main.py`
- full multi-agent pipeline wiring
- consistent dependency injection across all agents
- richer coder / tester / fix / security behaviors
- automated tests and polished examples

## Example Use Cases

This framework is useful as a base for experiments such as:

- planner -> researcher -> coder pipelines
- agent memory and state-sharing experiments
- tool-augmented LLM workflows
- runtime tracing and audit logging research
- security-aware agent execution prototypes

## Roadmap

Planned or natural next steps include:

- unify all agents under the `BaseAgent` contract
- continue refining runtime service and policy boundaries
- add guardrails and action-policy enforcement
- improve test coverage for runtime state transitions
- support richer tools and artifact handling
- add better demos and reproducible end-to-end examples

## Notes

This repository is best understood as an evolving systems prototype. The most complete parts today are the runtime abstractions, shared state model, and the initial orchestration / research flow.

## License

Add a project license here if you plan to distribute or open-source the framework publicly.
