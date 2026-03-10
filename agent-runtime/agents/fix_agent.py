class FixAgent:

    def run(self, state):

        print("Fixing code...")

        state.generated_code = """
def solution():
    return "hello"
"""

        state.retry_count += 1

        # 修复后需要重新测试
        state.test_result = ""
        state.error_log = ""

        return state