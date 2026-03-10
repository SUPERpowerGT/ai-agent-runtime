class CoderAgent:

    def run(self, state):

        print("Coder generating code...")

        state.generated_code = """
def solution():
    return "hello world"
"""

        # 新代码生成后需要重新测试
        state.test_result = ""
        state.error_log = ""

        return state