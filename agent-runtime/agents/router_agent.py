class RouterAgent:

    def run(self, state):

        # 先做 research
        if state.retrieved_context == []:
            state.next_agent = "research"

        elif state.generated_code == "":
            state.next_agent = "coder"

        elif state.test_result == "":
            state.next_agent = "tester"

        elif state.test_result == "FAIL":

            if state.retry_count < 3:
                state.next_agent = "fix"
            else:
                state.next_agent = "security"

        elif state.test_result == "PASS" and state.security_report == "":
            state.next_agent = "security"

        elif state.security_report == "No issues":
            state.next_agent = "finish"
            state.finished = True

        else:
            state.next_agent = "finish"

        return state