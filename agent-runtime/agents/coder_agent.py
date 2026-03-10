class CoderAgent:
    #agent本质上是state转换器，根据结果来更新state
    def run(self, state):
        #打印日志
        print("Coder generating code...")
        #读取用户请求生成任务计划
        state.generated_code = """
def solution():
    return "hello world"
"""

        return state