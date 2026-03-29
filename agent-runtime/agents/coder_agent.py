from agents.base_agent import BaseAgent
from agents.prompts import render_prompt
from observability.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from state.read_context import StateReadPolicy
from state.state import TaskState


class CoderAgent(BaseAgent):
    """
    CoderAgent 负责根据用户需求与 research 上下文生成代码。
    """

    name = "coder"
    description = "Generate code for the requested task"
    workflow_code_changing = True
    before_run_trace_message = "coder started"
    after_run_trace_message = "coder finished"
    state_read_policy = StateReadPolicy(
        conversation_message_limit=3,
        history_limit=3,
        memory_keys=("user_id", "conversation_id", "session_summary", "preference", "last_success_summary", "uploaded_files"),
        memory_max_items=6,
        memory_max_chars=600,
        local_memory_keys=("research",),
        local_memory_max_items=2,
        local_memory_max_chars=1000,
    )

    def perceive(self, state: TaskState):
        # coder 只补充“生成代码真正需要的上下文”：
        # task_spec、research 摘要、已有合同与行为摘要。
        # 公共 prompt 字段已经由 BaseAgent 统一组装。
        return self.build_prompt_observation(
            state,
            task_spec=state.task_spec,
            research_summary=state.local_memory.get("research", ""),
            code_contracts=state.artifacts.get("code_contracts", []),
            behavior_summaries=state.artifacts.get("behavior_summaries", []),
        )

    def think(self, observation):
        task_spec = observation["task_spec"]
        language = task_spec.get("language") or "the most appropriate language for the request"
        artifact_type = task_spec.get("artifact_type", "code")
        domain = task_spec.get("domain", "general")
        task_mode = task_spec.get("task_mode", "generate")
        constraints = task_spec.get("constraints", [])
        code_contracts = observation["code_contracts"]
        behavior_summaries = observation["behavior_summaries"]
        # 把已有公共 API 合同转成更直接的 prompt 片段，提醒模型“保留旧接口，再扩展新能力”。
        expected_api = [
            f'- {contract["name"]} with {contract["arity"]} parameter(s)'
            for contract in code_contracts
        ]

        prompt = render_prompt(
            "coder_generate",
            language=language,
            artifact_type=artifact_type,
            domain=domain,
            task_mode=task_mode,
            constraints=constraints or ["No additional constraints extracted."],
            code_contracts=code_contracts or "No existing code contracts provided.",
            expected_api=expected_api or ["No existing public API contracts provided."],
            behavior_summaries=behavior_summaries or "No existing behavior summaries provided.",
            user_request=observation["user_request"],
            latest_user_message=observation["latest_user_message"],
            conversation_context=observation["conversation_context"] or "No prior conversation context.",
            history_context=observation["history_context"] or "No archived turn history.",
            memory_context=observation["memory_context"] or "No session memory.",
            research_summary=observation["research_summary"] or "No research context provided.",
        )

        response = call_llm(prompt, state=observation["state"], agent_name=self.name)

        log_agent(self.name, f"output={preview_text(response)}")

        return response

    def act(self, decision, state: TaskState) -> TaskState:
        # coder 的职责很单纯：写入新代码，并清空上一次验证残留。
        state.generated_code = decision
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
            raise ValueError("coder returned empty code")

        return cleaned
