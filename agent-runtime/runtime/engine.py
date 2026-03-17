from runtime.register_agents import registry
from state.state import TaskState


class AgentRuntime:
    """
    Multi-Agent Runtime Engine
    """

    def run(self, state: TaskState) -> TaskState:

        while state.can_continue():

            agent_name = state.next_agent

            if not agent_name:
                print("No next agent, stopping runtime.")
                break

            try:
                agent = registry.get(agent_name)

            except Exception:
                state.add_error(f"Agent not found: {agent_name}")
                break

            print(f"Running agent: {agent_name}")

            state = agent.run(state)

        return state