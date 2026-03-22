from agents.base_agent import BaseAgent

from runtime.services.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from runtime.services.languages import check_language_static_consistency
from runtime.policies.transitions import handle_test_outcome
from runtime.services.repair import build_failure_report, build_fix_strategy, summarize_findings
from state.state import TaskState


class TesterAgent(BaseAgent):
    """
    TesterAgent 负责做通用验证编排：
    - contract checks
    - language-specific static checks
    - LLM semantic judgment
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
        code_contracts = task_spec.get("code_contracts", [])
        behavior_summaries = task_spec.get("behavior_summaries", [])

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
- Task mode: {task_spec.get("task_mode", "generate")}
- Constraints: {task_spec.get("constraints", []) or ["No additional constraints extracted."]}

Existing code contracts:
{code_contracts or "No existing code contracts provided."}

Existing behavior summaries:
{behavior_summaries or "No existing behavior summaries provided."}

User request:
{observation["user_request"]}

Generated code:
{observation["generated_code"]}

Return ONLY one line in this exact format:
PASS|short reason
or
FAIL|short reason

Keep the reason short and concrete.

For optimize or rewrite tasks, fail the result if function behavior or returned data shape changes in a meaningful way.
"""

        response = call_llm(prompt, state=observation["state"], agent_name=self.name)

        log_agent(self.name, f"llm_verdict={preview_text(response)}")

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
        llm_result = decision["test_result"]
        llm_error = decision["error"]
        findings = []

        contract_failure = self.check_contract(state.task_spec, state.generated_code)
        if contract_failure:
            findings.append(self._make_finding("contract_violation", contract_failure))

        static_failure = self.check_static_consistency(state.task_spec, state.generated_code)
        if static_failure:
            findings.append(self._make_finding("static_consistency", static_failure))

        if llm_result == "FAIL":
            findings.append(self._make_finding("semantic_validation", llm_error or "LLM validation failed"))

        if findings:
            decision = {
                "test_result": "FAIL",
                "error": summarize_findings(findings),
            }

            failure_report = build_failure_report(
                task_spec=state.task_spec,
                llm_result=llm_result,
                llm_error=llm_error,
                findings=findings,
            )
            fix_strategy = build_fix_strategy(
                task_spec=state.task_spec,
                failure_report=failure_report,
            )
            state.artifacts["failure_report"] = failure_report
            state.artifacts["fix_strategy"] = fix_strategy
        else:
            state.artifacts.pop("failure_report", None)
            state.artifacts.pop("fix_strategy", None)

        state.test_result = decision["test_result"]

        if decision["error"]:
            state.add_error(decision["error"])

        log_agent(
            self.name,
            (
                f"final_verdict={decision['test_result']} "
                f"(llm={llm_result}, reason={preview_text(decision['error'] or llm_error or 'no error')})"
            ),
        )

        state.add_trace(
            agent_name=self.name,
            stage="final_verdict",
            message=f"final verdict: {decision['test_result']}",
            success=decision["test_result"] == "PASS",
            metadata={
                "llm_result": llm_result,
                "llm_error": llm_error,
                "final_error": decision["error"],
                "findings": findings,
            },
        )

        state.record_agent_output(self.name, state.test_result)
        return handle_test_outcome(state, max_retries=self.max_steps)

    def check_contract(self, task_spec: dict, code: str) -> str | None:
        """
        Deterministic contract checks:
        - artifact shape
        - basic language/form checks
        - uploaded code signature preservation
        """
        artifact_type = task_spec.get("artifact_type")
        language = task_spec.get("language")
        task_mode = task_spec.get("task_mode", "generate")
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

        if task_mode in {"optimize", "rewrite"}:
            contract_failure = self._enforce_code_contracts(
                state_contracts=task_spec.get("code_contracts", []),
                code=code,
            )
            if contract_failure:
                return contract_failure

        return None

    def check_static_consistency(self, task_spec: dict, code: str) -> str | None:
        """
        Delegate static consistency checks to the registered language adapter.
        """
        return check_language_static_consistency(task_spec, code)

    def judge_with_llm(self, observation):
        """
        LLM-based semantic judgment layer.
        """
        return self.think(observation)

    def _enforce_code_contracts(self, state_contracts: list[dict], code: str) -> str | None:
        if not state_contracts:
            return None

        extracted_names = set()
        extracted_signatures = {}

        for line in code.splitlines():
            stripped = line.strip()
            if not stripped.startswith("def "):
                continue

            name_part = stripped[4:].split("(", 1)[0].strip()
            params_part = stripped.split("(", 1)[1].rsplit(")", 1)[0]
            params = [param.strip() for param in params_part.split(",") if param.strip()]

            extracted_names.add(name_part)
            extracted_signatures[name_part] = len(params)

        expected_names = {contract["name"] for contract in state_contracts}
        missing_names = expected_names - extracted_names
        if missing_names:
            return f"Missing expected functions: {sorted(missing_names)}"

        for contract in state_contracts:
            name = contract["name"]
            expected_arity = contract["arity"]
            actual_arity = extracted_signatures.get(name)
            if actual_arity != expected_arity:
                return f"Function signature mismatch for {name}: expected {expected_arity} params"

        return None

    def _make_finding(self, finding_type: str, message: str) -> dict:
        return {
            "type": finding_type,
            "message": message,
            "severity": "high",
            "source": self.name,
        }
