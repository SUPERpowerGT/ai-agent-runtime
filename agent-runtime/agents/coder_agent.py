from agents.base_agent import BaseAgent
from runtime.services.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from state.state import TaskState


class CoderAgent(BaseAgent):
    """
    CoderAgent 负责根据用户需求与 research 上下文生成代码。
    """

    name = "coder"
    description = "Generate code for the requested task"

    # --------------------------------------------------
    # Lifecycle Hooks
    # --------------------------------------------------

    def before_run(self, state: TaskState):
        log_agent(self.name, "starting")

        state.add_trace(
            agent_name=self.name,
            stage="before_run",
            message="coder started",
        )

    def after_run(self, state: TaskState):
        state.add_trace(
            agent_name=self.name,
            stage="after_run",
            message="coder finished",
        )

    # --------------------------------------------------
    # Core Agent Stages
    # --------------------------------------------------

    def perceive(self, state: TaskState):
        return {
            "state": state,
            "user_request": state.user_request,
            "task_spec": state.task_spec,
            "research_summary": state.working_memory.get("research", ""),
            "code_contracts": state.artifacts.get("code_contracts", []),
            "behavior_summaries": state.artifacts.get("behavior_summaries", []),
        }

    def think(self, observation):
        task_spec = observation["task_spec"]
        language = task_spec.get("language") or "the most appropriate language for the request"
        artifact_type = task_spec.get("artifact_type", "code")
        domain = task_spec.get("domain", "general")
        task_mode = task_spec.get("task_mode", "generate")
        constraints = task_spec.get("constraints", [])
        code_contracts = observation["code_contracts"]
        behavior_summaries = observation["behavior_summaries"]

        prompt = f"""
You are a coding agent in a multi-agent runtime.

Your role is ONLY to write code that satisfies the user request.
Use the research summary as background context, not as something to repeat.
Do NOT explain the code.
Do NOT evaluate whether the code is correct.
Do NOT include tests unless the user explicitly asked for them.
Prefer the smallest correct implementation.

Task specification:
- Language: {language}
- Artifact type: {artifact_type}
- Domain: {domain}
- Task mode: {task_mode}
- Constraints: {constraints or ["No additional constraints extracted."]}

You must follow the task specification exactly.
If the artifact type is function, return a function rather than a top-level script.
If the artifact type is class, return a class.
If the artifact type is api, return API-oriented code rather than a standalone helper.

Existing code contracts from uploaded files:
{code_contracts or "No existing code contracts provided."}

Existing behavior summaries from uploaded files:
{behavior_summaries or "No existing behavior summaries provided."}

If task mode is optimize:
- preserve existing function names
- preserve input parameter shapes
- preserve external behavior
- improve implementation quality without changing the public contract

If task mode is rewrite:
- preserve the behavior of the uploaded code
- translate to the requested language if one is specified

User request:
{observation["user_request"]}

Research summary:
{observation["research_summary"] or "No research context provided."}

Return ONLY valid {language} code.
Do not add markdown fences.
Do not add explanations.
"""

        response = call_llm(prompt, state=observation["state"], agent_name=self.name)

        log_agent(self.name, f"output={preview_text(response)}")

        return response

    def act(self, decision, state: TaskState) -> TaskState:
        state.generated_code = decision
        state.test_result = ""
        state.error_log.clear()
        state.record_agent_output(self.name, state.generated_code)
        self.advance_to_next_planned_agent(state)

        return state

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
            raise ValueError("coder returned empty code")

        return cleaned
