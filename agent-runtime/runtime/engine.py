import time

from runtime.container import build_runtime_container
from observability.logging import log_runtime
from runtime.services.fallback import fail_turn
from runtime.services.memory import persist_turn_memory_and_history
from state.state import TaskState


class AgentRuntime:
    """
    Multi-Agent Runtime Engine
    """

    def __init__(self, *, container=None):
        started_at = time.perf_counter()
        self.container = container or build_runtime_container()
        self.cold_start_ms = round((time.perf_counter() - started_at) * 1000, 2)
        self._cold_start_recorded = False

    def run(self, state: TaskState) -> TaskState:
        runtime_started_at = time.perf_counter()

        if not self._cold_start_recorded:
            state.record_cold_start(self.cold_start_ms)
            self._cold_start_recorded = True

        while state.can_continue():

            agent_name = state.next_agent

            if not agent_name:
                log_runtime("no next agent, stopping runtime")
                state = fail_turn(
                    state,
                    code="missing_next_agent",
                    message="runtime stopped because next_agent is empty",
                    stage="dispatch",
                )
                break

            try:
                agent = self.container.resolve_agent(agent_name)

            except Exception as exc:
                state = fail_turn(
                    state,
                    code="unknown_agent",
                    message=f"Agent not found: {agent_name}",
                    stage="resolve_agent",
                    metadata={"agent_name": agent_name, "error": str(exc)},
                )
                break

            log_runtime(f"dispatch -> {agent_name}")
            state.record_dispatch()

            try:
                state = agent.run(state)
                state = self.container.resolve_next_transition(state=state, agent=agent)
            except Exception as exc:
                state = fail_turn(
                    state,
                    code="runtime_exception",
                    message=f"runtime failed while dispatching {agent_name}: {exc}",
                    stage="runtime_loop",
                    metadata={"agent_name": agent_name, "error": str(exc)},
                )
                break

        if not state.finished and state.step_count >= state.max_steps:
            state = fail_turn(
                state,
                code="max_steps_exceeded",
                message=(
                    f"runtime stopped because max_steps was reached "
                    f"({state.step_count}/{state.max_steps})"
                ),
                stage="runtime_loop",
                metadata={
                    "step_count": state.step_count,
                    "max_steps": state.max_steps,
                },
            )

        duration_ms = (time.perf_counter() - runtime_started_at) * 1000
        persist_turn_memory_and_history(state)
        state.record_runtime_duration(duration_ms)
        return state
