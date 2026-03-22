# agents/orchestrator_agent.py

import re

from agents.base_agent import BaseAgent
from runtime.services.logging import log_agent
from runtime.services.llm import call_llm
from runtime.services.task_spec import build_task_spec
from runtime.policies.transitions import normalize_plan
from state.state import TaskState


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
        log_agent(self.name, "starting")

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
research → coder → tester

If the task is about fixing bugs:
research → fix → tester

If code is generated or modified:
tester must follow before the result is considered complete.

If the task is about security:
use security.

Hard rule:
If your plan includes coder or fix, it must also include tester after the last code-changing agent.

Return ONLY a comma-separated list of agent names.

Example:
research,coder,tester
research,fix,tester
coder,tester

User request:
{observation.user_request}
"""

        observation.add_message(
            role="system",
            content="orchestrator planning task",
        )

        response = call_llm(prompt, state=observation, agent_name=self.name)

        observation.add_message(
            role="assistant",
            content=response,
        )

        return response

    def act(self, decision, state: TaskState) -> TaskState:
        """
        写入执行计划
        """

        state.plan = decision
        state.task_spec = build_task_spec(state.user_request)

        if decision:
            state.next_agent = decision[0]

        state.record_agent_output(self.name, decision)

        state.add_trace(
            agent_name=self.name,
            stage="act",
            message="execution plan written",
            metadata={"plan": decision},
        )

        log_agent(self.name, f"plan={state.plan}")
        log_agent(self.name, f"task_spec={state.task_spec}")

        return state

    # --------------------------------------------------
    # Output Validation
    # --------------------------------------------------

    def validate_output(self, decision):
        """
        解析 LLM 输出并过滤非法 agent
        """
        plan = self._extract_plan_from_text(decision)

        if not plan:
            log_agent(self.name, "planner returned empty plan, using fallback")
            plan = ["research", "coder", "tester"]

        plan = normalize_plan(plan)

        return plan

    def _extract_plan_from_text(self, decision: str) -> list[str]:
        """
        从 planner 的回复中提取真正的 agent 序列，而不是说明文字里提到的所有 agent。
        """
        text = decision.lower()

        # 先优先找显式的逗号序列，例如 research,coder,tester
        csv_candidates = re.findall(
            r"(research|coder|tester|fix|security)(?:\s*,\s*(research|coder|tester|fix|security))+",
            text,
        )

        if csv_candidates:
            csv_strings = re.findall(
                r"(?:research|coder|tester|fix|security)(?:\s*,\s*(?:research|coder|tester|fix|security))+",
                text,
            )
            best_candidate = max(csv_strings, key=len)
            matches = re.findall(r"\b(research|coder|tester|fix|security)\b", best_candidate)
        else:
            # 再退而求其次，只看“plan/answer/sequence”后面的文本片段
            focused_match = re.search(
                r"(?:plan|answer|sequence)\s*[:\-]?\s*(.+)",
                text,
                flags=re.DOTALL,
            )
            focused_text = focused_match.group(1) if focused_match else text
            matches = re.findall(r"\b(research|coder|tester|fix|security)\b", focused_text)

        ordered_plan = []
        for agent_name in matches:
            if agent_name not in ordered_plan:
                ordered_plan.append(agent_name)

        return ordered_plan
