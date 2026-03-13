from agents.orchestrator_agent import OrchestratorAgent
from agents.research_agent import ResearchAgent
from agents.coder_agent import CoderAgent
from agents.tester_agent import TesterAgent
from agents.fix_agent import FixAgent
from agents.security_agent import SecurityAgent

class AgentRuntime:

    def __init__(self, graph):
        self.graph = graph

    def run(self, state):

        current = self.graph.start_node
        step = 0
        MAX_STEPS = 50

        while current:

            step += 1
            if step > MAX_STEPS:
                print("Max steps reached, stopping.")
                break

            print(f"Running {current.name}")
            state.history.append(current.name)
            state = current.agent.run(state)

            next_node = None

            for condition, node in current.edges:
                if condition(state):
                    next_node = node
                    break

            current = next_node
        
        return state