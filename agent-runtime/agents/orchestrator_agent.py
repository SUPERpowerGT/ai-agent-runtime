# agents/orchestrator_agent.py
#orchestrator_agent本身是规划用户行为
#预设默认的router路径
#世纪汇根据state动态调整plan

# 导入任务状态结构
from state.state import TaskState

# 导入 LLM 调用封装
from infra.llm_client import call_llm


# 系统允许使用的 agent 列表
# 用于过滤 LLM 输出，避免出现不存在的 agent
VALID_AGENTS = {"research", "coder", "tester", "fix", "security"}


class OrchestratorAgent:

    # agent 名称（用于 runtime 调度）
    name = "orchestrator"

    def run(self, state: TaskState) -> TaskState:
        """
        OrchestratorAgent 的核心职责：

        1. 读取用户请求
        2. 使用 LLM 进行任务规划
        3. 生成 agent 执行计划（plan）
        4. 写入 TaskState
        """

        print("Running orchestrator")

        # Planner Prompt
        # 这里告诉 LLM：
        # - 有哪些 agent
        # - 每个 agent 的能力
        # - 规划规则
        prompt = f"""
You are the planner of a multi-agent system.

Your job is to decide which agents should run to complete the user request.

Available agents:

research
- gather information
- read documentation
- understand context

coder
- implement new functionality
- write code

fix
- debug and repair existing code

tester
- validate generated code

security
- analyze security vulnerabilities

Planning guidelines:

If the task is about implementing something:
research → coder

If the task is about fixing bugs:
research → fix

If code is generated or modified:
tester should usually follow.

If the task is about security:
use security.

Return ONLY a comma-separated list of agent names.

Example:
research,coder,tester
research,fix,tester

User request:
{state.user_request}
"""

        # 调用 LLM
        response = call_llm(prompt)

        print("LLM plan raw:", response)

        # -------------------------------
        # 解析 LLM 输出
        # -------------------------------

        # 将换行替换为空格
        tokens = response.replace("\n", " ").split(",")

        # 过滤非法 agent
        plan = [
            token.strip().lower()
            for token in tokens
            if token.strip().lower() in VALID_AGENTS
        ]

        # -------------------------------
        # Fallback 机制
        # 如果 LLM 返回异常，给一个默认 pipeline
        # -------------------------------
        if not plan:
            print("Planner returned empty plan, using fallback plan")
            plan = ["research", "coder", "tester"]

        # -------------------------------
        # 写入 state
        # -------------------------------
        state.plan = plan

        # 设置下一步 agent
        if plan:
            state.next_agent = plan[0]

        print("Parsed plan:", state.plan)

        return state