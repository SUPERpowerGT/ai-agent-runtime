from runtime.bootstrap.agents import registry
from runtime.services.logging import log_runtime
from state.state import TaskState


class AgentRuntime:
    """
    Multi-Agent Runtime Engine
    """

    def run(self, state: TaskState) -> TaskState:

        while state.can_continue():

            agent_name = state.next_agent

            if not agent_name:
                log_runtime("no next agent, stopping runtime")
                break

            try:
                agent = registry.get(agent_name)

            except Exception:
                state.add_error(f"Agent not found: {agent_name}")
                break

            log_runtime(f"dispatch -> {agent_name}")

            state = agent.run(state)

        return state
