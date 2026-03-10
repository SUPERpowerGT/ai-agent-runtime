class OrchestratorAgent:
    #agent本质上是state转换器，根据结果来更新state
    def run(self, state):

        print("Orchestrator planning task...")

        state.plan = f"Plan to solve: {state.user_request}"

        return state