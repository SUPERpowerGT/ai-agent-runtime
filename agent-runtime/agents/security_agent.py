class SecurityAgent:

    def run(self, state):

        print("Security scan...")

        code = state.generated_code

        if "eval(" in code or "os.system" in code:
            state.security_report = "unsafe"
        else:
            state.security_report = "No issues"

        return state