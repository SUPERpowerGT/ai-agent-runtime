# state/state.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from state.models import (
    AgentMemory,
    RuntimeMetrics,
    SecurityEvent,
    ToolCallRecord,
    TraceRecord,
)


@dataclass
class TaskState:
    """
    Agent Runtime 的共享状态对象（Blackboard）

    设计目标：
    1. 所有 agent 通过 state 共享信息
    2. BaseAgent 输入输出统一为 TaskState
    3. 支持 plan / routing / memory / tools / tracing / security
    4. 支持未来扩展成更复杂的 runtime
    """

    # --------------------------------------------------
    # Task Identity
    # --------------------------------------------------

    task_id: str
    user_request: str

    # --------------------------------------------------
    # Workflow Control
    # --------------------------------------------------

    plan: List[str] = field(default_factory=list)
    current_agent: Optional[str] = None
    next_agent: Optional[str] = None
    finished: bool = False

    # 当前执行步数 / 最大步数
    step_count: int = 0
    max_steps: int = 20

    # --------------------------------------------------
    # Core Outputs
    # --------------------------------------------------

    task_spec: Dict[str, Any] = field(default_factory=dict)
    retrieved_context: List[str] = field(default_factory=list)
    generated_code: str = ""
    test_result: str = ""
    security_report: str = ""

    # 更通用的 agent 输出池
    agent_outputs: Dict[str, Any] = field(default_factory=dict)

    # --------------------------------------------------
    # Memory
    # --------------------------------------------------

    # 全局短期 memory，适合 router / orchestrator / runtime 共用
    working_memory: Dict[str, Any] = field(default_factory=dict)

    # 全局长期历史
    history: List[Dict[str, Any]] = field(default_factory=list)

    # 每个 agent 的独立 memory
    agent_memories: Dict[str, AgentMemory] = field(default_factory=dict)

    # LLM / agent message 记录
    messages: List[Dict[str, Any]] = field(default_factory=list)

    # --------------------------------------------------
    # Tools / Artifacts
    # --------------------------------------------------

    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)

    # --------------------------------------------------
    # Error / Retry / Security
    # --------------------------------------------------

    error_log: List[str] = field(default_factory=list)
    retry_count: int = 0
    security_events: List[SecurityEvent] = field(default_factory=list)

    # --------------------------------------------------
    # Tracing / Metrics
    # --------------------------------------------------

    trace: List[TraceRecord] = field(default_factory=list)
    metrics: RuntimeMetrics = field(default_factory=RuntimeMetrics)

    # --------------------------------------------------
    # Helper Methods
    # --------------------------------------------------

    def add_trace(
        self,
        agent_name: str,
        stage: str,
        message: str,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        添加一条执行追踪记录
        """
        self.trace.append(
            TraceRecord(
                agent_name=agent_name,
                stage=stage,
                message=message,
                success=success,
                metadata=metadata or {},
            )
        )

    def add_error(self, message: str) -> None:
        """
        添加错误日志
        """
        self.error_log.append(message)

    def add_security_event(
        self,
        level: str,
        source: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        添加安全事件
        """
        self.security_events.append(
            SecurityEvent(
                level=level,
                source=source,
                message=message,
                metadata=metadata or {},
            )
        )

    def add_tool_call(
        self,
        agent_name: str,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
        tool_output: Any = None,
        success: bool = True,
        error: str = "",
    ) -> None:
        """
        记录一次工具调用
        """
        self.tool_calls.append(
            ToolCallRecord(
                agent_name=agent_name,
                tool_name=tool_name,
                tool_input=tool_input or {},
                tool_output=tool_output,
                success=success,
                error=error,
            )
        )
        self.metrics.tool_calls += 1

    def add_message(self, role: str, content: str, **metadata) -> None:
        """
        记录消息，适合 LLM 对话、agent reasoning 摘要等
        """
        self.messages.append({
            "role": role,
            "content": content,
            **metadata,
        })

    def remember(
        self,
        agent_name: str,
        key: str,
        value: Any,
        long_term: bool = False,
    ) -> None:
        """
        给指定 agent 写入 memory
        """
        if agent_name not in self.agent_memories:
            self.agent_memories[agent_name] = AgentMemory()

        memory = self.agent_memories[agent_name]

        if long_term:
            memory.long_term.append({key: value})
        else:
            memory.short_term[key] = value

    def recall(self, agent_name: str, key: str, default: Any = None) -> Any:
        """
        从指定 agent 的 short-term memory 读取值
        """
        if agent_name not in self.agent_memories:
            return default
        return self.agent_memories[agent_name].short_term.get(key, default)

    def record_agent_output(self, agent_name: str, output: Any) -> None:
        """
        记录某个 agent 的输出
        """
        self.agent_outputs[agent_name] = output

    def increment_agent_run(self, agent_name: str) -> None:
        """
        更新 metrics 中的 agent 执行次数
        """
        self.metrics.agent_runs[agent_name] = (
            self.metrics.agent_runs.get(agent_name, 0) + 1
        )

    def record_agent_duration(self, agent_name: str, duration_ms: float) -> None:
        """
        记录单个 agent 的累计耗时
        """
        self.metrics.agent_durations_ms[agent_name] = (
            self.metrics.agent_durations_ms.get(agent_name, 0.0) + duration_ms
        )

    def record_llm_call(self, agent_name: Optional[str], duration_ms: float) -> None:
        """
        记录一次 LLM 调用信息
        """
        self.metrics.llm_calls += 1
        self.metrics.llm_time_ms += duration_ms

        if agent_name:
            self.metrics.llm_calls_by_agent[agent_name] = (
                self.metrics.llm_calls_by_agent.get(agent_name, 0) + 1
            )
            self.metrics.llm_time_by_agent_ms[agent_name] = (
                self.metrics.llm_time_by_agent_ms.get(agent_name, 0.0) + duration_ms
            )

    def can_continue(self) -> bool:
        """
        runtime 是否还能继续执行
        """
        return (not self.finished) and (self.step_count < self.max_steps)
