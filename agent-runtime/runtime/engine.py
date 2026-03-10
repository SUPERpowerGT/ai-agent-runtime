from agents.orchestrator import OrchestratorAgent
from agents.research_agent import ResearchAgent
from agents.coder_agent import CoderAgent
from agents.tester_agent import TesterAgent
from agents.fix_agent import FixAgent
from agents.security_agent import SecurityAgent
#控制agent的流程
#目前demo阶段可以，但是仍有很多问题
#runtime不知道当前agent的stage状态，不知道系统状态，当前只是顺序执行，无法做到根据代码重新生成plan
#系统无法扩展，while true不要用，是不可控制循环
#当前系统无法输出执行状态

class AgentRuntime:

    def __init__(self):
        # 规划任务执行流程，写入state.plan
        self.orchestrator = OrchestratorAgent()
        # 知识检索，检索相关信息丛本地或互联网，然后写入state.retrieved_context
        self.research = ResearchAgent()
        # 代码生成，根据用户输入，plan，retrieved_context，作为agent的输入，写入state.generated_code
        self.coder = CoderAgent()
        # 测试循环，根据测试结果写入state.test_result，如果有error更新state.error_log
        self.tester = TesterAgent()
        # 代码修复，根据test_result和error_log修复代码，写入state.generated_code并更新retry_count
        self.fix = FixAgent()
        # 安全扫描，生成security_report
        self.security = SecurityAgent()

    def run(self, state):

        state = self.orchestrator.run(state)

        state = self.research.run(state)

        state = self.coder.run(state)

        while True:

            state = self.tester.run(state)

            if state.test_result == "PASS":
                break
            #防止死循环
            if state.retry_count >= 3:
                break

            state = self.fix.run(state)

        state = self.security.run(state)

        return state