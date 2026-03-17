# agents/orchestrator_agent.py

from agents.base_agent import BaseAgent
from state.state import TaskState
from infra.llm_client import call_llm


VALID_AGENTS = {"research", "coder", "tester", "fix", "security"}


class OrchestratorAgent(BaseAgent):
    """
    OrchestratorAgent 负责规划整个任务流程。

    职责：
    1. 读取用户请求
    2. 使用 LLM 生成 agent 执行计划
    3. 写入 state.plan
    4. 设置 state.next_agent
    """

    name = "orchestrator"
    description = "Plan which agents should execute the task"

    # --------------------------------------------------
    # Lifecycle Hooks
    # --------------------------------------------------

    def before_run(self, state: TaskState):
        """
        Agent 执行前 Hook
        """
        print("Running orchestrator")

        state.add_trace(
            agent_name=self.name,
            stage="before_run",
            message="orchestrator started",
        )

    def after_run(self, state: TaskState):
        """
        Agent 执行后 Hook
        """
        state.add_trace(
            agent_name=self.name,
            stage="after_run",
            message="orchestrator finished",
        )

    # --------------------------------------------------
    # Core Agent Stages
    # --------------------------------------------------

    def perceive(self, state: TaskState):
        """
        读取系统状态
        """

        state.add_trace(
            agent_name=self.name,
            stage="perceive",
            message="reading user request",
        )

        return state

    def think(self, observation: TaskState):
        """
        调用 LLM 生成执行计划
        """

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
{observation.user_request}
"""

        observation.add_message(
            role="system",
            content="orchestrator planning task",
        )

        response = call_llm(prompt)

        observation.add_message(
            role="assistant",
            content=response,
        )

        print("LLM plan raw:", response)

        return response

    def act(self, decision, state: TaskState) -> TaskState:
        """
        写入执行计划
        """

        state.plan = decision

        if decision:
            state.next_agent = decision[0]

        state.record_agent_output(self.name, decision)

        state.add_trace(
            agent_name=self.name,
            stage="act",
            message="execution plan written",
            metadata={"plan": decision},
        )

        print("Parsed plan:", state.plan)

        return state

    # --------------------------------------------------
    # Output Validation
    # --------------------------------------------------

    def validate_output(self, decision):
        """
        解析 LLM 输出并过滤非法 agent
        """

        tokens = decision.replace("\n", " ").split(",")

        plan = [
            token.strip().lower()
            for token in tokens
            if token.strip().lower() in VALID_AGENTS
        ]

        if not plan:
            print("Planner returned empty plan, using fallback plan")
            plan = ["research", "coder", "tester"]

        return plan