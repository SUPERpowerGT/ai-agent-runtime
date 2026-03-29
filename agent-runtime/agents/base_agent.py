# agents/base_agent.py

import time
from observability.logging import log_agent
from state.read_context import StateReadPolicy
from state.state import TaskState


class BaseAgent:
    """
    BaseAgent 是所有 Agent 的统一模板（Agent Contract）。

    设计目标：
    1. Runtime 只需要调用 agent.run(state)
    2. Agent 只负责执行自己的逻辑，不负责系统调度
    3. 支持 LLM / ReAct / Tools / Memory 等能力扩展
    4. 提供基础安全控制（输出校验 / 错误保护）
    5. 保持结构简单，方便新增 Agent
    """

    # Agent unique name（必须唯一，用于 runtime / router 调度）
    name: str = "base"

    # Agent description（用于 planner 或 LLM 选择 agent）
    description: str = "Base agent"

    # 这些是 agent 自己声明的 workflow 元信息。
    # workflow 只读取这些声明来决定：
    # 1. 这个 agent 能不能出现在用户计划里
    # 2. 它是不是内部 agent
    # 3. 它会不会改代码
    # 4. 它执行完以后应该走哪类 transition
    workflow_plannable: bool = True
    workflow_internal_only: bool = False
    workflow_code_changing: bool = False
    workflow_transition: str = "plan_progress"

    # 统一的生命周期日志与 trace 文案。
    # 子类一般只改文案，不需要每次都重写 before_run / after_run。
    start_log_message: str | None = "starting"
    before_run_trace_message: str | None = None
    after_run_trace_message: str | None = None

    # agent 不应该无边界地直接读取整个 state。
    # 它先声明自己的读取策略，再由 state 产出裁剪过的 prompt 上下文。
    # allowed_skills 用来声明当前 agent 可以请求哪些能力。
    allowed_skills: list[str] = []
    skill_manager = None
    container = None
    state_read_policy: StateReadPolicy = StateReadPolicy()

    # Agent 内部最大执行次数配置（预留）
    max_steps: int = 5

    # --------------------------------------------------
    # Main execution entry
    # --------------------------------------------------

    def run(self, state: TaskState) -> TaskState:
        """
        Agent 统一执行入口。

        Runtime 调用方式：

            state = agent.run(state)

        Agent 内部执行流程：

            before_run   -> 执行前 hook
            perceive     -> 读取系统状态
            think        -> LLM 推理 / 决策
            validate     -> 输出校验
            act          -> 执行动作
            after_run    -> 执行后 hook
        """

        started_at = time.perf_counter()

        try:
            # 每次 agent 开始运行时，先清空默认 handoff。
            # 这样可以确保“下一步去谁”不是 agent 偷偷继承上一次结果，
            # 而是由 workflow 在本次执行完成后重新决定。
            state.current_agent = self.name
            state.next_agent = None

            # 记录 runtime step
            state.step_count += 1
            state.metrics.total_steps += 1
            state.increment_agent_run(self.name)

            state.add_trace(
                agent_name=self.name,
                stage="run",
                message="agent started",
            )

            # 执行前 hook
            self.before_run(state)

            # Step1: 观察当前环境（读取 state）
            observation = self.perceive(state)
            state.add_trace(
                agent_name=self.name,
                stage="perceive",
                message="perceive completed",
            )

            # Step2: Agent 思考（通常调用 LLM）
            decision = self.think(observation)
            state.add_trace(
                agent_name=self.name,
                stage="think",
                message="think completed",
            )

            # Step3: 校验 LLM 输出
            decision = self.validate_output(decision)
            state.add_trace(
                agent_name=self.name,
                stage="validate_output",
                message="validation completed",
            )

            # Step4: 执行动作（调用工具 / 修改 state）
            new_state = self.act(decision, state)
            state.add_trace(
                agent_name=self.name,
                stage="act",
                message="act completed",
            )

            # 执行后 hook
            self.after_run(new_state)

            duration_ms = (time.perf_counter() - started_at) * 1000
            new_state.record_agent_duration(self.name, duration_ms)
            new_state.add_trace(
                agent_name=self.name,
                stage="timing",
                message="agent finished",
                metadata={"duration_ms": round(duration_ms, 2)},
            )

            return new_state

        except Exception as e:
            error_message = f"{self.name} error: {str(e)}"

            state.add_error(error_message)
            state.add_trace(
                agent_name=self.name,
                stage="error",
                message=error_message,
                success=False,
            )
            state.add_security_event(
                level="warning",
                source="agent",
                message=f"{self.name} raised an exception",
                metadata={"error": str(e)},
            )
            duration_ms = (time.perf_counter() - started_at) * 1000
            state.record_agent_duration(self.name, duration_ms)
            # agent 未捕获异常时，直接终止当前 turn。
            # 这里故意走 fatal stop，避免 workflow 在损坏状态上继续推进。
            state.finished = True
            state.next_agent = None
            state.artifacts["fatal_error"] = error_message
            state.add_trace(
                agent_name=self.name,
                stage="fatal",
                message="runtime stopped after unhandled agent exception",
                success=False,
            )

            return state

    # --------------------------------------------------
    # Lifecycle Hooks
    # --------------------------------------------------

    def before_run(self, state: TaskState):
        """
        Agent 执行前的 Hook。

        可用于：
        - logging（日志记录）
        - tracing（调用链追踪）
        - metrics（监控统计）
        """
        if self.start_log_message:
            log_agent(self.name, self.start_log_message)

        state.add_trace(
            agent_name=self.name,
            stage="before_run",
            message=self.before_run_trace_message or f"{self.name} started",
        )

    def after_run(self, state: TaskState):
        """
        Agent 执行后的 Hook。

        可用于：
        - debug（调试）
        - state 检查
        - metrics 统计
        """
        state.add_trace(
            agent_name=self.name,
            stage="after_run",
            message=self.after_run_trace_message or f"{self.name} finished",
        )

    # --------------------------------------------------
    # Core Agent Stages
    # --------------------------------------------------

    def perceive(self, state: TaskState):
        """
        Perceive 阶段：读取系统状态。

        常见读取内容：
        - user_request（用户请求）
        - retrieved_context（检索内容）
        - generated_code（生成代码）
        - memory / history（历史记录）
        """
        return state

    def think(self, observation):
        """
        Think 阶段：Agent 思考。

        通常在这里：
        - 调用 LLM
        - 决定使用哪个工具
        - 生成任务计划
        """
        return observation

    def act(self, decision, state: TaskState) -> TaskState:
        """
        Act 阶段：执行动作。

        常见行为：
        - 调用工具（web_search / sandbox 等）
        - 更新 state
        - 写入 memory
        """
        return state

    # --------------------------------------------------
    # Output Validation
    # --------------------------------------------------

    def validate_output(self, decision):
        """
        对 Agent / LLM 的输出进行校验。

        用于防止：
        - hallucination
        - 非法 agent
        - 非法 tool 调用
        """
        return decision

    def use_skill(self, state: TaskState, skill_name: str, **kwargs):
        """
        Request a globally registered skill through the runtime container.
        runtime 负责权限校验、执行与记录。
        这样 agent 只声明“我要用什么能力”，而不是自己直接操作底层工具。
        """
        if self.container is None:
            raise ValueError("agent container is not attached")

        return self.container.execute_skill(
            state=state,
            agent=self,
            skill_name=skill_name,
            **kwargs,
        )

    def current_user_request(self, state: TaskState) -> str:
        """
        Return the effective request for the current turn.
        """
        return state.active_user_request()

    def recent_conversation_context(self, state: TaskState, *, limit: int = 6) -> str:
        """
        Return recent session history as a compact text block.
        """
        return state.recent_conversation_context(limit=limit)

    def conversation_log_context(self, state: TaskState, *, limit: int = 6) -> str:
        """
        Return recent conversation-log entries as a compact text block.
        """
        return state.conversation_log_context(limit=limit)

    def current_turn_context(self, state: TaskState):
        """
        Return the normalized current-turn state.
        """
        return state.current_turn_context()

    def workspace_context(self, state: TaskState):
        """
        Return the normalized live workspace view for the current run.
        """
        return state.workspace_context()

    def execution_flow_context(self, state: TaskState):
        """
        Return the normalized execution-flow state for the current run.
        """
        return state.execution_flow_context()

    def memory_context(self, state: TaskState) -> str:
        """
        Return prompt-friendly session memory.
        """
        return state.memory_context()

    def local_memory_context(self, state: TaskState, *, keys=(), max_items: int = 4, max_chars: int = 1200) -> str:
        """
        Return prompt-friendly workspace-local memory.
        """
        return state.filtered_local_memory_context(
            keys=keys,
            max_items=max_items,
            max_chars=max_chars,
        )

    def recent_history_context(self, state: TaskState, *, limit: int = 4) -> str:
        """
        Return archived turn summaries.
        """
        return state.recent_history_context(limit=limit)

    def build_state_read_context(self, state: TaskState):
        """
        Build a bounded, normalized read context from state for this agent.
        这是 agent 读取 prompt 上下文的主边界，用来保证读取范围稳定、可控。
        """
        return state.build_read_context(self.state_read_policy)

    def prompt_fields_from_state(self, state: TaskState) -> dict:
        """
        Return the normalized prompt-ready fields allowed by this agent's
        state read policy.
        """
        return self.build_state_read_context(state).to_prompt_fields()

    def build_prompt_observation(self, state: TaskState, **extra_fields) -> dict:
        """
        Build the standard observation payload passed from perceive() to think().
        子类只需要补充自己关心的字段，不必每次都重复组装公共 prompt 上下文。
        """
        return {
            "state": state,
            **self.prompt_fields_from_state(state),
            **extra_fields,
        }

    def strip_code_fences(self, text: str) -> str:
        """
        Normalize fenced code responses into plain source text.
        """
        cleaned = text.strip()
        if not cleaned.startswith("```"):
            return cleaned

        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]

        return "\n".join(lines).strip()
