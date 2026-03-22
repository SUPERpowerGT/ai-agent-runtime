from agents.base_agent import BaseAgent
from state.state import TaskState


class RouterAgent(BaseAgent):

    name = "router"
    description = "Route execution to the next agent based on current state"

    def perceive(self, state: TaskState):
        return state

    def think(self, observation: TaskState):
        # 先做 research
        if observation.retrieved_context == []:
            return "research"

        if observation.generated_code == "":
            return "coder"

        if observation.test_result == "":
            return "tester"

        if observation.test_result == "FAIL":

            if observation.retry_count < 3:
                return "fix"
            return "security"

        if observation.test_result == "PASS" and observation.security_report == "":
            return "security"

        if observation.security_report == "No issues":
            return None

        return None

    def act(self, decision, state: TaskState) -> TaskState:
        if decision is None:
            state.finished = True
            state.next_agent = None
        else:
            state.next_agent = decision
        return state
