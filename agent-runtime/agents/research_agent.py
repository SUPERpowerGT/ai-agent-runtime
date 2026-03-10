class ResearchAgent:

    def run(self, state):

        print("Research agent retrieving knowledge...")

        state.retrieved_context = [
            "Example Python function",
            "Algorithm template"
        ]

        return state