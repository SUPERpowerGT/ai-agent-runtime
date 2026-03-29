from __future__ import annotations

from state.state import TaskState


def summarize_mcp_transports(result: TaskState) -> str:
    seen: list[str] = []
    for call in result.tool_calls:
        output = call.tool_output if isinstance(call.tool_output, dict) else {}
        metadata = output.get("metadata", {}) if isinstance(output, dict) else {}
        transport = metadata.get("transport")
        endpoint = metadata.get("endpoint")
        if not transport:
            continue
        label = transport if not endpoint else f"{transport}({endpoint})"
        if label not in seen:
            seen.append(label)
    return ", ".join(seen)


def print_runtime_summary(result: TaskState) -> None:
    fallback_result = result.artifacts.get("fallback_result")
    plan_source = result.artifacts.get("plan_source", "unknown")
    plan_reason = result.artifacts.get("plan_reason")
    workspace = result.workspace_context()
    session = result.session_context()

    print(f"User: {session['user_id']}")
    print(f"Conversation: {session['conversation_id']}")
    print(f"Turn: {session['turn_id']}")
    print(f"Current turn status: {workspace['current_turn'].get('status', 'unknown')}")
    if workspace["current_turn"].get("summary"):
        print(f"Current turn summary: {workspace['current_turn'].get('summary')}")
    print(f"Plan: {workspace['execution_flow']['plan']}")
    print(f"Plan source: {plan_source}")
    if plan_reason:
        print(f"Plan reason: {plan_reason}")
    print(f"Task spec: {result.task_spec}")
    print(f"Uploaded files: {result.uploaded_files}")
    print(f"Retrieved docs: {len(result.retrieved_documents)}")
    print(f"Finished: {workspace['execution_flow']['finished']}")
    print(f"Current agent: {workspace['execution_flow']['current_agent']}")
    print(f"Step count: {workspace['execution_flow']['step_count']}")
    print(f"Retry count: {result.retry_count}")
    print(f"Dispatch count: {result.metrics.dispatch_count}")
    print(f"Agent runs: {result.metrics.agent_runs}")
    print(f"Total LLM calls: {result.metrics.llm_calls}")
    print(f"Total LLM time: {result.metrics.llm_time_ms:.2f} ms")
    print(f"Queue wait: {result.metrics.queue_wait_ms:.2f} ms")
    print(f"Cold start: {result.metrics.cold_start_ms:.2f} ms")
    print(f"Runtime duration: {result.metrics.runtime_duration_ms:.2f} ms")
    print(f"Execution calls: {result.metrics.execution_calls}")
    print(f"Execution failures: {result.metrics.execution_failures}")
    print(f"Execution time: {result.metrics.execution_time_ms:.2f} ms")
    print(f"Workspace local memory keys: {workspace['local_memory_keys']}")
    print(f"Profile memory keys: {session['profile_memory_keys']}")
    print(f"Episodic memory count: {session['episodic_memory_count']}")
    print(f"Vector memory count: {session['vector_memory_count']}")
    print(f"History count: {session['history_count']}")
    print(f"Conversation log count: {session['conversation_log_count']}")
    mcp_transports = summarize_mcp_transports(result)
    if mcp_transports:
        print(f"MCP transports: {mcp_transports}")
    print(f"Fallback used: {'yes' if fallback_result else 'no'}")
    if fallback_result:
        print(f"Fallback mode: {fallback_result.get('mode', 'unknown')}")
        print(f"Fallback reason: {fallback_result.get('reason', 'unspecified')}")

    profile_memory = result.memory.get("profile_memory", {})
    if profile_memory.get("session_summary"):
        print("Session summary:")
        for line in str(profile_memory["session_summary"]).splitlines():
            print(f"  {line}")

    print("Agent durations:")
    for agent_name, duration_ms in result.metrics.agent_durations_ms.items():
        runs = result.metrics.agent_runs.get(agent_name, 0)
        avg_ms = duration_ms / runs if runs else duration_ms
        print(f"  {agent_name}: total={duration_ms:.2f} ms avg={avg_ms:.2f} ms runs={runs}")

    print("LLM time by agent:")
    for agent_name, duration_ms in result.metrics.llm_time_by_agent_ms.items():
        calls = result.metrics.llm_calls_by_agent.get(agent_name, 0)
        avg_ms = duration_ms / calls if calls else duration_ms
        print(f"  {agent_name}: total={duration_ms:.2f} ms avg={avg_ms:.2f} ms calls={calls}")
