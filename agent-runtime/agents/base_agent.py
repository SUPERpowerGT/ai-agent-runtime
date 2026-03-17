# agents/base_agent.py

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

    # Allowed tools（声明当前 agent 可以调用的工具）
    tools: list[str] = []

    # Allowed state fields（限制 agent 可以修改的 state 字段）
    allowed_state_fields: list[str] = []

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

        try:
            # 记录当前 agent
            state.current_agent = self.name

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
        pass

    def after_run(self, state: TaskState):
        """
        Agent 执行后的 Hook。

        可用于：
        - debug（调试）
        - state 检查
        - metrics 统计
        """
        pass

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