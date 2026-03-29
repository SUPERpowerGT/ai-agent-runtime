from agents.base_agent import BaseAgent
from observability.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from state.read_context import StateReadPolicy
from state.state import TaskState


class SecurityAgent(BaseAgent):
    """
    SecurityAgent 负责对生成代码做基础安全审查。
    """

    name = "security"
    description = "Perform a simple security scan over generated code"
    before_run_trace_message = "security agent started"
    after_run_trace_message = "security agent finished"
    state_read_policy = StateReadPolicy(
        conversation_message_limit=2,
        history_limit=2,
        memory_keys=("user_id", "conversation_id", "session_summary"),
        memory_max_items=4,
        memory_max_chars=300,
    )

    # --------------------------------------------------
    # Core Agent Stages
    # --------------------------------------------------

    def perceive(self, state: TaskState):
        return self.build_prompt_observation(
            state,
            generated_code=state.generated_code,
        )

    def think(self, observation):
        prompt = f"""
You are a security review agent in a multi-agent runtime.

Your role is ONLY to assess obvious security risks in the generated Python code.
Do NOT rewrite the code.
Do NOT comment on style or correctness unless it affects security.
Mark code as UNSAFE only if there is a clear security concern.

User request:
{observation["user_request"]}

Latest user message:
{observation["latest_user_message"]}

Recent conversation context:
{observation["conversation_context"]}

Archived turn history:
{observation["history_context"]}

Session memory:
{observation["memory_context"]}

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
