from agents.base_agent import BaseAgent
from agents.prompts import render_prompt
from observability.logging import log_agent
import re
from runtime.services.llm import call_llm
from state.read_context import StateReadPolicy
from state.state import TaskState
from workflow import (
    build_task_spec,
    normalize_plan,
)

SECURITY_KEYWORDS = {
    "security", "secure", "vulnerability", "vulnerabilities", "auth", "authentication",
    "authorization", "permission", "permissions", "xss", "csrf", "injection",
    "owasp", "secret", "secrets", "exploit",
}
RESEARCH_HINT_KEYWORDS = {
    "api", "sdk", "framework", "library", "docs", "documentation", "database",
    "sql", "react", "fastapi", "django", "flask", "node", "typescript",
    "javascript", "deployment", "architecture",
}


class OrchestratorAgent(BaseAgent):
    """
    OrchestratorAgent 负责规划整个任务流程。

    职责：
    1. 读取用户请求
    2. 使用 LLM 生成 agent 执行计划
    3. 写入 state.plan
    4. 产出执行计划，交给 workflow 决定下一步
    """

    name = "orchestrator"
    description = "Plan which agents should execute the task"
    workflow_plannable = False
    workflow_internal_only = True
    workflow_transition = "start_plan"
    before_run_trace_message = "orchestrator started"
    after_run_trace_message = "orchestrator finished"
    state_read_policy = StateReadPolicy(
        conversation_message_limit=4,
        history_limit=4,
        memory_keys=("user_id", "conversation_id", "session_summary"),
        memory_max_items=6,
        memory_max_chars=500,
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
        read_context = self.build_state_read_context(observation)
        active_request = read_context.latest_user_message
        conversation_context = read_context.conversation_context
        history_context = read_context.history_context
        memory_context = read_context.memory_context
        allowed_agents, code_changing_agents = self._planning_metadata()

        # 第一步先把用户请求压成结构化 task_spec。
        # 后面的 routing / heuristic / planner 都基于这个统一输入工作。
        task_spec = build_task_spec(active_request)
        routed_plan = self.container.resolve_route(
            task_spec=task_spec,
            uploaded_files=observation.uploaded_files,
            user_request=active_request,
        )

        if routed_plan:
            # 已知任务模板优先，避免简单稳定任务还走一次 LLM 规划。
            log_agent(self.name, f"route_selected={routed_plan.name}")
            return self._build_routed_planning_decision(
                task_spec=task_spec,
                routed_plan=routed_plan,
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            )

        heuristic_plan = self._build_heuristic_plan(
            task_spec=task_spec,
            user_request=active_request,
            uploaded_files=observation.uploaded_files,
            allowed_agents=allowed_agents,
            code_changing_agents=code_changing_agents,
        )
        if heuristic_plan:
            # 第二层是确定性 heuristic 规划。
            # 这层适合简单代码任务，成本比 LLM 规划更低。
            log_agent(self.name, "route_selected=heuristic")
            return self._build_heuristic_planning_decision(
                task_spec=task_spec,
                heuristic_plan=heuristic_plan,
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            )

        # 只有前两层都无法给出稳定结果时，才退回到 LLM planner。
        prompt = render_prompt(
            "orchestrator_plan",
            user_request=active_request,
            latest_user_message=active_request,
            conversation_context=conversation_context or "No prior conversation context.",
            history_context=history_context or "No archived turn history.",
            memory_context=memory_context or "No session memory.",
        )

        observation.add_message(
            role="system",
            content="orchestrator planning task",
        )

        response = call_llm(prompt, state=observation, agent_name=self.name)

        observation.add_message(
            role="assistant",
            content=response,
        )

        return self._build_llm_planning_decision(task_spec=task_spec, raw_response=response)

    def act(self, decision, state: TaskState) -> TaskState:
        """
        写入执行计划
        """
        # orchestrator 不直接决定下一跳，只负责把规划结果落到 state。
        # 真正的 transition 仍然交给 workflow manager。
        state = self._apply_planning_decision(state=state, decision=decision)

        state.add_trace(
            agent_name=self.name,
            stage="act",
            message="execution plan written",
            metadata={"plan": state.plan},
        )

        route_plan = decision.get("route_plan")
        plan_source = decision.get("plan_source", "llm")
        log_agent(self.name, f"plan={state.plan}")
        log_agent(self.name, f"plan_source={plan_source}")
        log_agent(self.name, f"task_spec={state.task_spec}")
        if route_plan:
            log_agent(self.name, f"route={route_plan['route_name']}")
        else:
            log_agent(self.name, "route=none (llm planner fallback)")

        return state

    # --------------------------------------------------
    # Output Validation
    # --------------------------------------------------

    def validate_output(self, decision):
        """
        解析 LLM 输出并过滤非法 agent
        """
        validated = self._validate_planning_decision(
            decision,
            allowed_agents=self._planning_metadata()[0],
            code_changing_agents=self._planning_metadata()[1],
        )
        if validated["plan_source"] == "llm" and not validated["plan"]:
            log_agent(self.name, "planner returned empty plan, using fallback")
        return validated

    def _planning_metadata(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        # 这里读取的是 agent registry 暴露出来的元信息，而不是把 agent 名单写死在 orchestrator。
        # 这样新增 agent 时，主要修改面会停留在 agent 声明和 workflow。
        registry = None
        if self.container is not None:
            registry = getattr(self.container, "agent_registry", None)

        if registry is None:
            from runtime.agents import build_agent_registry

            registry = build_agent_registry()

        return (
            tuple(registry.list_plannable_agents()),
            tuple(registry.list_code_changing_agents()),
        )

    def _merge_session_code_expectations(self, state, task_spec: dict) -> dict:
        """
        如果当前任务是在上一轮代码基础上继续修改，就把稳定下来的
        接口约束和行为摘要补回当前 task_spec。
        """
        merged = dict(task_spec)
        if merged.get("task_mode") not in {"extend", "rewrite", "optimize"}:
            return merged

        language = merged.get("language")
        if not merged.get("code_contracts"):
            previous_contracts = state.recall_memory("last_code_contracts", []) or []
            filtered_contracts = [
                contract
                for contract in previous_contracts
                if not language or contract.get("language") in {None, language}
            ]
            if filtered_contracts:
                merged["code_contracts"] = filtered_contracts

        if not merged.get("behavior_summaries"):
            previous_behaviors = state.recall_memory("last_behavior_summaries", []) or []
            filtered_behaviors = [
                summary
                for summary in previous_behaviors
                if not language or summary.get("language") in {None, language}
            ]
            if filtered_behaviors:
                merged["behavior_summaries"] = filtered_behaviors

        return merged

    def _build_heuristic_plan(
        self,
        *,
        task_spec: dict,
        user_request: str,
        uploaded_files: list[str],
        allowed_agents: tuple[str, ...] | list[str] | set[str] | None = None,
        code_changing_agents: tuple[str, ...] | list[str] | set[str] | None = None,
    ) -> list[str] | None:
        """
        用 orchestrator 自己的启发式规则直接生成计划。
        这属于 agent 的规划能力，不属于 workflow 骨架。
        """
        request_lower = user_request.lower()

        if any(keyword in request_lower for keyword in SECURITY_KEYWORDS):
            return normalize_plan(
                ["research", "security"],
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            )

        is_code_task = task_spec.get("artifact_type") in {
            "code", "function", "class", "module", "script", "api"
        }
        if not is_code_task:
            return normalize_plan(
                ["research"],
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            )

        if uploaded_files:
            return normalize_plan(
                ["research", "coder", "tester"],
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            )

        needs_research = any(keyword in request_lower for keyword in RESEARCH_HINT_KEYWORDS)
        if task_spec.get("task_mode") in {"rewrite", "optimize", "extend"}:
            return normalize_plan(
                ["research", "coder", "tester"] if needs_research else ["coder", "tester"],
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            )

        if needs_research:
            return normalize_plan(
                ["research", "coder", "tester"],
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            )

        return normalize_plan(
            ["coder", "tester"],
            allowed_agents=allowed_agents,
            code_changing_agents=code_changing_agents,
        )

    def _extract_plan_from_text(
        self,
        decision: str,
        *,
        allowed_agents: tuple[str, ...] | list[str] | set[str] | None = None,
        code_changing_agents: tuple[str, ...] | list[str] | set[str] | None = None,
    ) -> list[str]:
        """
        从 LLM 返回的自然语言里尽量抽出一个 agent 顺序列表。
        """
        candidates = tuple(allowed_agents or ())
        if not candidates:
            return []
        agent_pattern = "|".join(re.escape(agent_name) for agent_name in candidates)
        text = decision.lower()

        csv_candidates = re.findall(
            rf"({agent_pattern})(?:\s*,\s*({agent_pattern}))+",
            text,
        )

        if csv_candidates:
            csv_strings = re.findall(
                rf"(?:{agent_pattern})(?:\s*,\s*(?:{agent_pattern}))+",
                text,
            )
            best_candidate = max(csv_strings, key=len) if csv_strings else ""
            matches = re.findall(rf"\b({agent_pattern})\b", best_candidate)
        else:
            focused_match = re.search(
                r"(?:plan|answer|sequence)\s*[:\-]?\s*(.+)",
                text,
                flags=re.DOTALL,
            )
            focused_text = focused_match.group(1) if focused_match else text
            matches = re.findall(rf"\b({agent_pattern})\b", focused_text)

        ordered_plan = []
        for agent_name in matches:
            if agent_name not in ordered_plan:
                ordered_plan.append(agent_name)

        return normalize_plan(
            ordered_plan,
            allowed_agents=allowed_agents,
            code_changing_agents=code_changing_agents,
        )

    def _build_routed_planning_decision(
        self,
        *,
        task_spec: dict,
        routed_plan,
        allowed_agents: tuple[str, ...] | list[str] | set[str] | None = None,
        code_changing_agents: tuple[str, ...] | list[str] | set[str] | None = None,
    ) -> dict:
        """
        把 routing 的结果包装成 orchestrator 内部统一使用的规划决策结构。
        """
        return {
            "source": "routing",
            "plan": normalize_plan(
                routed_plan.recommended_plan,
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            ),
            "task_spec": task_spec,
            "route_plan": {
                "route_name": routed_plan.name,
                "recommended_plan": routed_plan.recommended_plan,
                "metadata": routed_plan.metadata,
            },
        }

    def _build_heuristic_planning_decision(
        self,
        *,
        task_spec: dict,
        heuristic_plan: list[str],
        allowed_agents: tuple[str, ...] | list[str] | set[str] | None = None,
        code_changing_agents: tuple[str, ...] | list[str] | set[str] | None = None,
    ) -> dict:
        """
        把启发式计划包装成 orchestrator 内部统一使用的规划决策结构。
        """
        return {
            "source": "heuristic",
            "plan": normalize_plan(
                heuristic_plan,
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            ),
            "task_spec": task_spec,
            "route_plan": {
                "route_name": "heuristic_plan",
                "recommended_plan": heuristic_plan,
                "metadata": {
                    "strategy": "heuristic",
                    "reason": "deterministic plan selected without LLM fallback",
                },
            },
        }

    def _build_llm_planning_decision(self, *, task_spec: dict, raw_response: str) -> dict:
        """
        把原始 LLM 输出包装成待校验的规划决策。
        """
        return {
            "source": "planner",
            "raw_response": raw_response,
            "task_spec": task_spec,
            "route_plan": None,
        }

    def _validate_planning_decision(
        self,
        decision: dict,
        *,
        allowed_agents: tuple[str, ...] | list[str] | set[str] | None = None,
        code_changing_agents: tuple[str, ...] | list[str] | set[str] | None = None,
    ) -> dict:
        """
        校验并标准化 orchestrator 自己产出的规划决策。
        """
        if not isinstance(decision, dict):
            raise ValueError("orchestrator decision must be a dict")

        source = decision.get("source")
        task_spec = decision.get("task_spec")
        route_plan = decision.get("route_plan")

        if not task_spec:
            raise ValueError("orchestrator decision missing task_spec")

        if source in {"routing", "heuristic"}:
            plan = normalize_plan(
                decision.get("plan", []),
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            )
            if not plan:
                raise ValueError("routing decision missing recommended plan")
            return {
                "plan": plan,
                "task_spec": task_spec,
                "route_plan": route_plan,
                "planner_response": None,
                "plan_source": source,
            }

        raw_response = decision.get("raw_response", "")
        plan = self._extract_plan_from_text(
            raw_response,
            allowed_agents=allowed_agents,
            code_changing_agents=code_changing_agents,
        )
        if not plan:
            plan = ["research", "coder", "tester"]

        return {
            "plan": normalize_plan(
                plan,
                allowed_agents=allowed_agents,
                code_changing_agents=code_changing_agents,
            ),
            "task_spec": task_spec,
            "route_plan": route_plan,
            "planner_response": raw_response,
            "plan_source": "llm",
        }

    def _apply_planning_decision(self, *, state, decision: dict) -> object:
        """
        把已经校验好的规划结果正式写回 state。
        """
        state.task_spec = self._merge_session_code_expectations(state, decision["task_spec"])
        state.plan = decision["plan"]

        route_plan = decision.get("route_plan")
        plan_source = decision.get("plan_source", "llm")

        if route_plan:
            state.artifacts["route_plan"] = route_plan
        else:
            state.artifacts.pop("route_plan", None)

        if state.task_spec.get("code_contracts"):
            state.artifacts["code_contracts"] = state.task_spec["code_contracts"]
        if state.task_spec.get("behavior_summaries"):
            state.artifacts["behavior_summaries"] = state.task_spec["behavior_summaries"]

        state.artifacts["plan_source"] = plan_source
        if route_plan and route_plan.get("metadata", {}).get("reason"):
            state.artifacts["plan_reason"] = route_plan["metadata"]["reason"]
        elif plan_source == "llm":
            state.artifacts["plan_reason"] = "llm planner fallback"
        else:
            state.artifacts.pop("plan_reason", None)

        if decision.get("planner_response"):
            state.artifacts["planner_response"] = decision["planner_response"]

        state.record_agent_output("orchestrator", state.plan)
        return state
