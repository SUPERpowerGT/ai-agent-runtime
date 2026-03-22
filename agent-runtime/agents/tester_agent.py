from agents.base_agent import BaseAgent
from runtime.services.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from runtime.policies.transitions import handle_test_outcome
from state.state import TaskState


class TesterAgent(BaseAgent):
    """
    TesterAgent 负责对生成代码做基础测试判断并输出测试结论。
    """

    name = "tester"
    description = "Run simple validation against generated code"

    # --------------------------------------------------
    # Lifecycle Hooks
    # --------------------------------------------------

    def before_run(self, state: TaskState):
        log_agent(self.name, "starting")

        state.add_trace(
            agent_name=self.name,
            stage="before_run",
            message="tester started",
        )

    def after_run(self, state: TaskState):
        state.add_trace(
            agent_name=self.name,
            stage="after_run",
            message="tester finished",
        )

    # --------------------------------------------------
    # Core Agent Stages
    # --------------------------------------------------

    def perceive(self, state: TaskState):
        return {
            "state": state,
            "user_request": state.user_request,
            "task_spec": state.task_spec,
            "generated_code": state.generated_code,
        }

    def think(self, observation):
        task_spec = observation["task_spec"]

        prompt = f"""
You are a testing agent in a multi-agent runtime.

Your role is ONLY to evaluate whether the generated code satisfies the user request and task specification.
Do NOT rewrite the code.
Do NOT suggest improvements unless they are the reason for failure.
Judge the code as PASS only if the request is actually satisfied.
If the code is missing a required behavior, return FAIL.

Task specification:
- Language: {task_spec.get("language") or "unspecified"}
- Artifact type: {task_spec.get("artifact_type", "code")}
- Domain: {task_spec.get("domain", "general")}
- Constraints: {task_spec.get("constraints", []) or ["No additional constraints extracted."]}

User request:
{observation["user_request"]}

Generated code:
{observation["generated_code"]}

Return ONLY one line in this exact format:
PASS|short reason
or
FAIL|short reason

Keep the reason short and concrete.
"""

        response = call_llm(prompt, state=observation["state"], agent_name=self.name)

        log_agent(self.name, f"output={preview_text(response)}")

        return response

    # --------------------------------------------------
    # Output Validation
    # --------------------------------------------------

    def validate_output(self, decision):
        cleaned = decision.strip()
        status, _, reason = cleaned.partition("|")
        status = status.strip().upper()
        reason = reason.strip() or "No reason provided"

        if status not in {"PASS", "FAIL"}:
            if "PASS" in cleaned.upper():
                status = "PASS"
            elif "FAIL" in cleaned.upper():
                status = "FAIL"
            else:
                status = "FAIL"
                reason = f"Invalid tester output: {cleaned}"

        return {
            "test_result": status,
            "error": None if status == "PASS" else reason,
        }

    def act(self, decision, state: TaskState) -> TaskState:
        task_spec = state.task_spec
        code = state.generated_code

        enforced_failure_reason = self._enforce_task_spec(task_spec, code)
        if enforced_failure_reason:
            decision = {
                "test_result": "FAIL",
                "error": enforced_failure_reason,
            }

        state.test_result = decision["test_result"]

        if decision["error"]:
            state.add_error(decision["error"])

        state.record_agent_output(self.name, state.test_result)
        return handle_test_outcome(state, max_retries=self.max_steps)

    def _enforce_task_spec(self, task_spec: dict, code: str) -> str | None:
        artifact_type = task_spec.get("artifact_type")
        language = task_spec.get("language")
        normalized_code = code.lower()

        if artifact_type == "function":
            if language == "python" and "def " not in normalized_code:
                return "Expected a Python function definition"
            if language in {"javascript", "typescript"}:
                if "function " not in normalized_code and "=>" not in normalized_code:
                    return f"Expected a {language} function definition"

        if artifact_type == "class":
            if "class " not in normalized_code:
                return "Expected a class definition"

        return None
