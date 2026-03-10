class SecurityAgent:

    def run(self, state):

        print("Security scan...")

        state.security_report = "No issues"

        state.finished = True

        return state