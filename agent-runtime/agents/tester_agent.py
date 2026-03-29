from agents.base_agent import BaseAgent
import ast
import re
import shutil

from agents.prompts import render_prompt
from observability.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from runtime.services.languages import check_language_static_consistency
from runtime.services.repair import build_failure_report, build_fix_strategy, summarize_findings
from runtime.services.transforms import apply_contract_transformations
from infrastructure.execution.sandbox.workspace import create_sandbox_workspace
from state.read_context import StateReadPolicy
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
    allowed_skills = ["sandbox_execute"]
    workflow_transition = "test_outcome"
    before_run_trace_message = "tester started"
    after_run_trace_message = "tester finished"
    state_read_policy = StateReadPolicy(
        conversation_message_limit=2,
        history_limit=2,
        memory_keys=("user_id", "conversation_id", "session_summary"),
        memory_max_items=4,
        memory_max_chars=300,
        local_memory_keys=(),
        local_memory_max_items=0,
        local_memory_max_chars=0,
    )

    def perceive(self, state: TaskState):
        original_code = state.generated_code
        normalized_code = apply_contract_transformations(state.task_spec, original_code)
        code_was_normalized = normalized_code != original_code

        # tester 在真正验证前，先做一次合同归一化。
        # 这一步的目标不是“替模型修代码”，而是把可机械修正的接口形态先对齐。
        state.generated_code = normalized_code
        state.artifacts["normalized_code"] = normalized_code
        state.artifacts["normalization_applied"] = code_was_normalized

        if code_was_normalized:
            state.add_trace(
                agent_name=self.name,
                stage="normalization",
                message="applied pre-test contract normalization",
                metadata={
                    "original_length": len(original_code),
                    "normalized_length": len(normalized_code),
                },
            )
            log_agent(self.name, "applied pre-test contract normalization")

        return self.build_prompt_observation(
            state,
            task_spec=state.task_spec,
            generated_code=normalized_code,
        )

    def think(self, observation):
        task_spec = observation["task_spec"]
        code_contracts = task_spec.get("code_contracts", [])
        behavior_summaries = task_spec.get("behavior_summaries", [])

        prompt = render_prompt(
            "tester_judge",
            language=task_spec.get("language") or "unspecified",
            artifact_type=task_spec.get("artifact_type", "code"),
            domain=task_spec.get("domain", "general"),
            task_mode=task_spec.get("task_mode", "generate"),
            constraints=task_spec.get("constraints", []) or ["No additional constraints extracted."],
            code_contracts=code_contracts or "No existing code contracts provided.",
            behavior_summaries=behavior_summaries or "No existing behavior summaries provided.",
            user_request=observation["user_request"],
            latest_user_message=observation["latest_user_message"],
            conversation_context=observation["conversation_context"] or "No prior conversation context.",
            history_context=observation["history_context"] or "No archived turn history.",
            memory_context=observation["memory_context"] or "No session memory.",
            generated_code=observation["generated_code"],
        )

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

        # tester 的最终判定不是只信 LLM。
        # 它会把合同校验、静态检查、执行检查和 LLM 语义判断合并成一个最终结论。
        contract_failure = self.check_contract(state.task_spec, state.generated_code)
        if contract_failure:
            findings.append(self._make_finding("contract_violation", contract_failure))

        static_failure = self.check_static_consistency(state.task_spec, state.generated_code)
        if static_failure:
            findings.append(self._make_finding("static_consistency", static_failure))

        execution_failure = self.check_execution(state)
        if execution_failure:
            findings.append(self._make_finding("execution_validation", execution_failure))

        if llm_result == "FAIL":
            findings.append(self._make_finding("semantic_validation", llm_error or "LLM validation failed"))

        if findings:
            # 只要存在结构化 findings，就把它们整理成 fix 可消费的 failure_report / fix_strategy。
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
        return state

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
        code_contracts = task_spec.get("code_contracts", [])
        behavior_summaries = task_spec.get("behavior_summaries", [])
        requested_public_api = task_spec.get("requested_public_api", [])
        constraints = task_spec.get("constraints", [])

        if artifact_type == "function":
            if language == "python" and "def " not in normalized_code:
                return "Expected a Python function definition"
            if language in {"javascript", "typescript"}:
                if "function " not in normalized_code and "=>" not in normalized_code:
                    return f"Expected a {language} function definition"

        if artifact_type == "class":
            if "class " not in normalized_code:
                return "Expected a class definition"

        if task_mode in {"extend", "optimize", "rewrite"}:
            if not code_contracts and not behavior_summaries:
                return "Missing uploaded-code context for optimize/rewrite validation"

            contract_failure = self._enforce_code_contracts(
                state_contracts=code_contracts,
                target_language=language,
                code=code,
            )
            if contract_failure:
                return contract_failure

        requested_api_failure = self._enforce_requested_public_api(
            requested_public_api=requested_public_api,
            target_language=language,
            code=code,
        )
        if requested_api_failure:
            return requested_api_failure

        literal_constraint_failure = self._enforce_literal_constraints(
            constraints=constraints,
            code=code,
        )
        if literal_constraint_failure:
            return literal_constraint_failure

        return None

    def check_static_consistency(self, task_spec: dict, code: str) -> str | None:
        """
        Delegate static consistency checks to the registered language adapter.
        """
        return check_language_static_consistency(task_spec, code)

    def check_execution(self, state: TaskState) -> str | None:
        """
        Execute a lightweight smoke test inside a restricted workspace when the
        language/runtime is supported.
        """
        # 这一步是“硬验证”，用来兜住纯 LLM 判断可能漏掉的行为错误。
        if self.container is None:
            return "sandbox execution unavailable: runtime container not attached"

        language = state.task_spec.get("language")
        if language != "python":
            runtime_name = self._runtime_name_for_language(language)
            if runtime_name and shutil.which(runtime_name) is None:
                state.add_trace(
                    agent_name=self.name,
                    stage="sandbox_skip",
                    message=f"skipped execution smoke test: missing {runtime_name} runtime",
                )
                return None
            return None

        try:
            with create_sandbox_workspace(
                language=language,
                code=state.generated_code,
                task_spec=state.task_spec,
                uploaded_files=state.uploaded_files,
            ) as workspace:
                result = self.use_skill(
                    state,
                    "sandbox_execute",
                    command=workspace.command,
                    cwd=workspace.root,
                    timeout_seconds=5,
                    policy_mode="restricted",
                    allowed_cwds=[workspace.root],
                    allowed_env_keys=[],
                )
        except Exception as exc:
            return f"sandbox execution failed: {exc}"

        state.artifacts["sandbox_execution"] = {
            "command": result.get("command"),
            "cwd": result.get("cwd"),
            "exit_code": result.get("exit_code"),
            "timed_out": result.get("timed_out", False),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "policy": result.get("policy", {}),
        }

        if result.get("timed_out"):
            return "sandbox execution timed out"
        if result.get("exit_code") != 0:
            stderr = (result.get("stderr") or result.get("stdout") or "").strip()
            parsed_error = self._summarize_sandbox_error(stderr)
            state.artifacts["sandbox_execution_error"] = parsed_error or stderr
            if stderr:
                return f"sandbox execution failed: {parsed_error or stderr}"
            return f"sandbox execution failed with exit_code={result.get('exit_code')}"

        state.add_trace(
            agent_name=self.name,
            stage="sandbox_execution",
            message="sandbox smoke test passed",
            metadata={
                "entrypoint": workspace.entrypoint,
                "exit_code": result.get("exit_code"),
                "original_available": workspace.original_available,
            },
        )
        log_agent(self.name, "sandbox smoke test passed")
        return None

    def judge_with_llm(self, observation):
        """
        LLM-based semantic judgment layer.
        """
        return self.think(observation)

    def _enforce_code_contracts(
        self,
        state_contracts: list[dict],
        target_language: str | None,
        code: str,
    ) -> str | None:
        if not state_contracts:
            return None

        extracted_signatures = self._extract_function_signatures(
            code=code,
            language=target_language,
        )
        extracted_names = set(extracted_signatures)

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

        extracted_signature_details = self._extract_function_signature_details(
            code=code,
            language=target_language,
        )
        for contract in state_contracts:
            expected_params = [
                self._normalize_param_name(param)
                for param in contract.get("params", [])
            ]
            if not expected_params:
                continue

            actual_params = extracted_signature_details.get(contract["name"])
            if not actual_params:
                continue

            if actual_params != expected_params:
                return (
                    f"Function parameter mismatch for {contract['name']}: "
                    f"expected {expected_params}, got {actual_params}"
                )

        return None

    def _enforce_requested_public_api(
        self,
        *,
        requested_public_api: list[dict],
        target_language: str | None,
        code: str,
    ) -> str | None:
        if not requested_public_api:
            return None

        function_expectations = [
            item for item in requested_public_api if item.get("kind") == "function"
        ]
        if function_expectations:
            extracted_signatures = self._extract_function_signatures(
                code=code,
                language=target_language,
            )
            missing_function_names = sorted(
                item["name"]
                for item in function_expectations
                if item.get("name") not in extracted_signatures
            )
            if missing_function_names:
                return f"Missing requested function(s): {missing_function_names}"

            extracted_signature_details = self._extract_function_signature_details(
                code=code,
                language=target_language,
            )
            for item in function_expectations:
                expected_params = [
                    self._normalize_param_name(param)
                    for param in item.get("params", [])
                ]
                if not expected_params:
                    continue

                actual_params = extracted_signature_details.get(item["name"])
                if actual_params is None:
                    continue

                if actual_params != expected_params:
                    return (
                        f"Requested function signature mismatch for {item['name']}: "
                        f"expected {expected_params}, got {actual_params}"
                    )

        class_expectations = [
            item["name"]
            for item in requested_public_api
            if item.get("kind") == "class" and item.get("name")
        ]
        if class_expectations:
            extracted_classes = self._extract_python_classes(code) if target_language == "python" else set()
            missing_classes = sorted(name for name in class_expectations if name not in extracted_classes)
            if missing_classes:
                return f"Missing requested class(es): {missing_classes}"

        return None

    def _extract_function_signatures(self, code: str, language: str | None) -> dict[str, int]:
        details = self._extract_function_signature_details(code=code, language=language)
        return {
            name: len(params)
            for name, params in details.items()
        }

    def _extract_function_signature_details(self, code: str, language: str | None) -> dict[str, list[str]]:
        if language == "python":
            return self._extract_python_signature_details(code)
        if language in {"javascript", "typescript"}:
            return self._extract_javascript_signature_details(code)

        signatures = self._extract_python_signature_details(code)
        if signatures:
            return signatures
        return self._extract_javascript_signature_details(code)

    def _extract_python_signature_details(self, code: str) -> dict[str, list[str]]:
        signatures: dict[str, list[str]] = {}

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return signatures

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                signatures[node.name] = self._extract_python_ast_params(node)

        return signatures

    def _extract_python_signatures(self, code: str) -> dict[str, int]:
        return {
            name: len(params)
            for name, params in self._extract_python_signature_details(code).items()
        }

    def _extract_python_ast_params(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        params = [arg.arg for arg in node.args.posonlyargs]
        params.extend(arg.arg for arg in node.args.args)
        if node.args.vararg:
            params.append(node.args.vararg.arg)
        params.extend(arg.arg for arg in node.args.kwonlyargs)
        if node.args.kwarg:
            params.append(node.args.kwarg.arg)
        return params

    def _count_python_ast_params(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        return len(self._extract_python_ast_params(node))

    def _extract_javascript_signature_details(self, code: str) -> dict[str, list[str]]:
        signatures: dict[str, list[str]] = {}
        patterns = [
            re.compile(r"\b(?:async\s+)?function\s+([a-zA-Z_$][\w$]*)\s*\((.*?)\)", re.DOTALL),
            re.compile(r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>", re.DOTALL),
            re.compile(r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s*)?function\s*\((.*?)\)", re.DOTALL),
        ]

        for pattern in patterns:
            for match in pattern.finditer(code):
                signatures[match.group(1)] = [
                    self._normalize_param_name(param)
                    for param in self._split_params(match.group(2))
                ]

        return signatures

    def _extract_javascript_signatures(self, code: str) -> dict[str, int]:
        return {
            name: len(params)
            for name, params in self._extract_javascript_signature_details(code).items()
        }

    def _extract_python_classes(self, code: str) -> set[str]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return set()
        return {
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }

    def _split_params(self, raw_params: str) -> list[str]:
        raw_params = raw_params.strip()
        if not raw_params:
            return []

        params = []
        current = []
        bracket_depth = 0

        for char in raw_params:
            if char in "([{":
                bracket_depth += 1
            elif char in ")]}":
                bracket_depth = max(0, bracket_depth - 1)

            if char == "," and bracket_depth == 0:
                param = "".join(current).strip()
                if param:
                    params.append(param)
                current = []
                continue

            current.append(char)

        tail = "".join(current).strip()
        if tail:
            params.append(tail)

        return params

    def _count_params(self, raw_params: str) -> int:
        return len(self._split_params(raw_params))

    def _normalize_param_name(self, raw_param: str) -> str:
        value = raw_param.strip()
        if not value:
            return value

        value = value.split(":", 1)[0].strip()
        value = value.split("=", 1)[0].strip()
        return value.lstrip("*")

    def _enforce_literal_constraints(self, *, constraints: list[str], code: str) -> str | None:
        for constraint in constraints:
            prefix = 'preserve requested literal: "'
            if not constraint.startswith(prefix) or not constraint.endswith('"'):
                continue
            literal = constraint[len(prefix):-1]
            if literal and literal not in code:
                return f'Requested literal not preserved in generated code: "{literal}"'
        return None

    def _make_finding(self, finding_type: str, message: str) -> dict:
        return {
            "type": finding_type,
            "message": message,
            "severity": "high",
            "source": self.name,
        }

    def _runtime_name_for_language(self, language: str | None) -> str | None:
        if language in {"javascript", "typescript"}:
            return "node"
        if language == "python":
            return "python"
        return None

    def _summarize_sandbox_error(self, error_text: str) -> str:
        if not error_text:
            return ""

        for line in reversed(error_text.splitlines()):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("AssertionError:"):
                return stripped.replace("AssertionError:", "", 1).strip()
            if stripped.startswith(("SyntaxError:", "TypeError:", "ValueError:", "NameError:", "KeyError:")):
                return stripped

        return error_text.strip()
