class FixAgent:

    def run(self, state):

        print("Fixing code...")

        state.generated_code = """
def solution():
    return "hello"
"""

        state.retry_count += 1

        return state