from agents.base_agent import BaseAgent
from agents.prompts import render_prompt
from observability.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from state.read_context import StateReadPolicy
from state.state import TaskState


class FixAgent(BaseAgent):
    """
    FixAgent 负责根据测试失败信息修复已有代码。
    """

    name = "fix"
    description = "Repair generated code after failed validation"
    workflow_plannable = False
    workflow_internal_only = True
    workflow_code_changing = True
    workflow_transition = "after_fix"
    before_run_trace_message = "fix agent started"
    after_run_trace_message = "fix agent finished"
    state_read_policy = StateReadPolicy(
        conversation_message_limit=3,
        history_limit=4,
        memory_keys=("user_id", "conversation_id", "session_summary", "preference", "last_success_summary", "uploaded_files"),
        memory_max_items=6,
        memory_max_chars=600,
        local_memory_keys=("research",),
        local_memory_max_items=2,
        local_memory_max_chars=1000,
    )

    def perceive(self, state: TaskState):
        latest_error = state.error_log[-1] if state.error_log else ""
        return self.build_prompt_observation(
            state,
            task_spec=state.task_spec,
            generated_code=state.generated_code,
            errors=list(state.error_log),
            latest_error=latest_error,
            code_contracts=state.task_spec.get("code_contracts", []),
            requested_public_api=state.task_spec.get("requested_public_api", []),
            behavior_summaries=state.task_spec.get("behavior_summaries", []),
            failure_report=state.artifacts.get("failure_report", {}),
            fix_strategy=state.artifacts.get("fix_strategy", {}),
            sandbox_execution=state.artifacts.get("sandbox_execution", {}),
            sandbox_execution_error=state.artifacts.get("sandbox_execution_error", ""),
        )

    def think(self, observation):
        task_spec = observation["task_spec"]
        language = task_spec.get("language") or "the language implied by the request"
        artifact_type = task_spec.get("artifact_type", "code")
        latest_error = observation["latest_error"] or "No explicit errors recorded."
        code_contracts = observation["code_contracts"]
        requested_public_api = observation["requested_public_api"]
        behavior_summaries = observation["behavior_summaries"]
        failure_report = observation["failure_report"]
        fix_strategy = observation["fix_strategy"]
        sandbox_execution = observation["sandbox_execution"]
        sandbox_execution_error = observation["sandbox_execution_error"] or "No sandbox error recorded."
        expected_api = [
            f'- {contract["name"]} with {contract["arity"]} parameter(s)'
            for contract in code_contracts
        ]
        requested_api = [
            f'- {item["name"]} with {item.get("arity", 0)} parameter(s)'
            for item in requested_public_api
            if item.get("kind") == "function"
        ]

        prompt = render_prompt(
            "fix_repair",
            language=language,
            artifact_type=artifact_type,
            domain=task_spec.get("domain", "general"),
            task_mode=task_spec.get("task_mode", "generate"),
            constraints=task_spec.get("constraints", []) or ["No additional constraints extracted."],
            user_request=observation["user_request"],
            latest_user_message=observation["latest_user_message"],
            conversation_context=observation["conversation_context"] or "No prior conversation context.",
            history_context=observation["history_context"] or "No archived turn history.",
            memory_context=observation["memory_context"] or "No session memory.",
            generated_code=observation["generated_code"],
            latest_error=latest_error,
            errors=observation["errors"] or ["No explicit errors recorded."],
            failure_report=failure_report or {"status": "FAIL", "summary": latest_error},
            fix_strategy=fix_strategy or {"goal": "Address the latest validation failure."},
            sandbox_execution=sandbox_execution or {"status": "not available"},
            sandbox_execution_error=sandbox_execution_error,
            code_contracts=code_contracts or ["No code contracts provided."],
            expected_api=expected_api or ["No existing public API contracts provided."],
            requested_public_api=requested_public_api or ["No newly requested public API provided."],
            requested_api=requested_api or ["No newly requested public API provided."],
            behavior_summaries=behavior_summaries or ["No behavior summaries provided."],
        )

        response = call_llm(prompt, state=observation["state"], agent_name=self.name)

        log_agent(self.name, f"output={preview_text(response)}")

        return response

    def act(self, decision, state: TaskState) -> TaskState:
        state.generated_code = decision
        state.retry_count += 1
        state.test_result = ""
        state.error_log.clear()
        state.record_agent_output(self.name, state.generated_code)
        return state

    # --------------------------------------------------
    # Output Validation
    # --------------------------------------------------

    def validate_output(self, decision):
        cleaned = self.strip_code_fences(decision)

        if not cleaned:
            raise ValueError("fix agent returned empty code")

        return cleaned
