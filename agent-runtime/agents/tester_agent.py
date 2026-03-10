class TesterAgent:

    def run(self, state):

        print("Tester executing code...")

        if "hello" in state.generated_code:
            state.test_result = "PASS"
        else:
            state.test_result = "FAIL"
            state.error_log = "Output incorrect"

        return state