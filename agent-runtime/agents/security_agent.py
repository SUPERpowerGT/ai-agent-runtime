from agents.base_agent import BaseAgent
from runtime.services.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from state.state import TaskState


class SecurityAgent(BaseAgent):
    """
    SecurityAgent 负责对生成代码做基础安全审查。
    """

    name = "security"
    description = "Perform a simple security scan over generated code"

    # --------------------------------------------------
    # Lifecycle Hooks
    # --------------------------------------------------

    def before_run(self, state: TaskState):
        log_agent(self.name, "starting")

        state.add_trace(
            agent_name=self.name,
            stage="before_run",
            message="security agent started",
        )

    def after_run(self, state: TaskState):
        state.add_trace(
            agent_name=self.name,
            stage="after_run",
            message="security agent finished",
        )

    # --------------------------------------------------
    # Core Agent Stages
    # --------------------------------------------------

    def perceive(self, state: TaskState):
        return {
            "state": state,
            "user_request": state.user_request,
            "generated_code": state.generated_code,
        }

    def think(self, observation):
        prompt = f"""
You are a security review agent in a multi-agent runtime.

Your role is ONLY to assess obvious security risks in the generated Python code.
Do NOT rewrite the code.
Do NOT comment on style or correctness unless it affects security.
Mark code as UNSAFE only if there is a clear security concern.

User request:
{observation["user_request"]}

Generated code:
{observation["generated_code"]}

Return ONLY one line in this exact format:
SAFE|short reason
or
UNSAFE|short reason

Keep the reason short and security-specific.
"""

        response = call_llm(prompt, state=observation["state"], agent_name=self.name)

        log_agent(self.name, f"output={preview_text(response)}")

        return response

    def act(self, decision, state: TaskState) -> TaskState:
        state.security_report = decision["report"]
        state.record_agent_output(self.name, state.security_report)
        self.advance_to_next_planned_agent(state)

        return state

    # --------------------------------------------------
    # Output Validation
    # --------------------------------------------------

    def validate_output(self, decision):
        cleaned = decision.strip()
        status, _, reason = cleaned.partition("|")
        status = status.strip().upper()
        reason = reason.strip() or "No reason provided"

        if status == "SAFE":
            return {"report": f"No issues: {reason}"}

        if status == "UNSAFE":
            return {"report": f"unsafe: {reason}"}

        if "UNSAFE" in cleaned.upper():
            return {"report": f"unsafe: {reason}"}

        return {"report": f"No issues: {reason}"}
