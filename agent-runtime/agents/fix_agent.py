from agents.base_agent import BaseAgent
from runtime.services.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from runtime.policies.transitions import route_after_fix
from state.state import TaskState


class FixAgent(BaseAgent):
    """
    FixAgent 负责根据测试失败信息修复已有代码。
    """

    name = "fix"
    description = "Repair generated code after failed validation"

    # --------------------------------------------------
    # Lifecycle Hooks
    # --------------------------------------------------

    def before_run(self, state: TaskState):
        log_agent(self.name, "starting")

        state.add_trace(
            agent_name=self.name,
            stage="before_run",
            message="fix agent started",
        )

    def after_run(self, state: TaskState):
        state.add_trace(
            agent_name=self.name,
            stage="after_run",
            message="fix agent finished",
        )

    # --------------------------------------------------
    # Core Agent Stages
    # --------------------------------------------------

    def perceive(self, state: TaskState):
        latest_error = state.error_log[-1] if state.error_log else ""

        return {
            "state": state,
            "user_request": state.user_request,
            "task_spec": state.task_spec,
            "generated_code": state.generated_code,
            "errors": list(state.error_log),
            "latest_error": latest_error,
            "code_contracts": state.task_spec.get("code_contracts", []),
            "behavior_summaries": state.task_spec.get("behavior_summaries", []),
            "failure_report": state.artifacts.get("failure_report", {}),
            "fix_strategy": state.artifacts.get("fix_strategy", {}),
        }

    def think(self, observation):
        task_spec = observation["task_spec"]
        language = task_spec.get("language") or "the language implied by the request"
        artifact_type = task_spec.get("artifact_type", "code")
        latest_error = observation["latest_error"] or "No explicit errors recorded."
        code_contracts = observation["code_contracts"]
        behavior_summaries = observation["behavior_summaries"]
        failure_report = observation["failure_report"]
        fix_strategy = observation["fix_strategy"]

        prompt = f"""
You are a fix agent in a multi-agent runtime.

Your role is ONLY to repair the existing code.
Keep as much of the original structure as possible unless a larger change is necessary.
Address the reported errors and make the code satisfy the user request.
Use the provided validation report and fix strategy to decide what to change.
Do NOT explain the fix.
Do NOT include markdown fences.

Task specification:
- Language: {language}
- Artifact type: {artifact_type}
- Domain: {task_spec.get("domain", "general")}
- Constraints: {task_spec.get("constraints", []) or ["No additional constraints extracted."]}

User request:
{observation["user_request"]}

Current code:
{observation["generated_code"]}

Latest validation failure:
{latest_error}

Errors:
{observation["errors"] or ["No explicit errors recorded."]}

Structured failure report:
{failure_report or {"status": "FAIL", "summary": latest_error}}

Fix strategy:
{fix_strategy or {"goal": "Address the latest validation failure."}}

Existing code contracts:
{code_contracts or ["No code contracts provided."]}

Existing behavior summaries:
{behavior_summaries or ["No behavior summaries provided."]}

Return ONLY valid {language} code.
Do not add markdown fences.
Do not add explanations.
"""

        response = call_llm(prompt, state=observation["state"], agent_name=self.name)

        log_agent(self.name, f"output={preview_text(response)}")

        return response

    def act(self, decision, state: TaskState) -> TaskState:
        state.generated_code = decision
        state.retry_count += 1
        state.test_result = ""
        state.error_log.clear()
        state.record_agent_output(self.name, state.generated_code)
        return route_after_fix(state)

    # --------------------------------------------------
    # Output Validation
    # --------------------------------------------------

    def validate_output(self, decision):
        cleaned = decision.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        if not cleaned:
            raise ValueError("fix agent returned empty code")

        return cleaned
