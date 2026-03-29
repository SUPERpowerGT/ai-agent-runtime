# state/state.py

from dataclasses import asdict, dataclass, field
import time
from typing import Any, Dict, List, Optional

from state.models import (
    RuntimeMetrics,
    SecurityEvent,
    ToolCallRecord,
    TraceRecord,
)
from state.read_context import StateReadContext, StateReadPolicy


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
    user_id: str = "user_1"
    conversation_id: str = "conversation_1"
    turn_id: int = 1
    latest_user_message: str = ""
    submitted_at: float = field(default_factory=time.time)

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
    uploaded_files: List[str] = field(default_factory=list)
    retrieved_documents: List[Dict[str, Any]] = field(default_factory=list)
    rag_context: List[str] = field(default_factory=list)
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
    local_memory: Dict[str, Any] = field(default_factory=dict)

    # 当前轮上下文，适合所有 agent 读取“这一次在做什么”
    current_turn: Dict[str, Any] = field(default_factory=dict)

    # 会话级 memory，适合长期保存用户偏好、已确认约束、稳定上下文
    memory: Dict[str, Any] = field(default_factory=dict)

    # 全局长期历史
    history: List[Dict[str, Any]] = field(default_factory=list)

    # LLM / agent message 记录
    conversation_log: List[Dict[str, Any]] = field(default_factory=list)

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
        self.conversation_log.append({
            "role": role,
            "content": content,
            **metadata,
        })

    def append_user_message(self, content: str, **metadata) -> None:
        """
        在单会话模式下追加一轮新的用户输入。
        """
        self.turn_id += 1
        self.user_request = content
        self.latest_user_message = content
        self.current_turn = {
            "turn_id": self.turn_id,
            "user_message": content,
            "status": "active",
            "uploaded_files": list(self.uploaded_files),
        }
        self.add_message(
            "user",
            content,
            conversation_id=self.conversation_id,
            user_id=self.user_id,
            turn_id=self.turn_id,
            **metadata,
        )

    def sync_current_turn_uploads(self) -> None:
        """
        Keep the current-turn view aligned with the canonical uploaded-files list.
        """
        if not self.current_turn:
            return
        self.current_turn["uploaded_files"] = list(self.uploaded_files)

    def active_user_request(self) -> str:
        """
        Return the current turn's effective user request.
        """
        return self.latest_user_message or self.user_request

    def current_turn_context(self) -> Dict[str, Any]:
        """
        Return the normalized current-turn view for all agents.
        """
        if self.current_turn:
            return dict(self.current_turn)
        return {
            "turn_id": self.turn_id,
            "user_message": self.active_user_request(),
            "status": "active",
            "uploaded_files": list(self.uploaded_files),
        }

    def execution_flow_context(self) -> Dict[str, Any]:
        """
        Return the current execution-flow view for the active run.
        """
        return {
            "plan": list(self.plan),
            "current_agent": self.current_agent,
            "next_agent": self.next_agent,
            "finished": self.finished,
            "step_count": self.step_count,
            "max_steps": self.max_steps,
        }

    def conversation_log_context(self, *, limit: int = 6) -> str:
        """
        Return recent conversation-log entries for the active window.
        """
        return self.recent_conversation_context(limit=limit)

    def _ensure_memory_buckets(self) -> None:
        """
        Normalize memory into profile / episodic / vector buckets.
        """
        if not isinstance(self.memory, dict):
            self.memory = {}

        profile = self.memory.get("profile_memory")
        episodic = self.memory.get("episodic_memory")
        vector = self.memory.get("vector_memory")

        if not isinstance(profile, dict):
            legacy_profile = {
                key: value
                for key, value in self.memory.items()
                if key not in {"profile_memory", "episodic_memory", "vector_memory"}
            }
            profile = legacy_profile
        if not isinstance(episodic, list):
            episodic = []
        if not isinstance(vector, list):
            vector = []

        self.memory = {
            "profile_memory": profile,
            "episodic_memory": episodic,
            "vector_memory": vector,
        }

    def profile_memory(self) -> Dict[str, Any]:
        self._ensure_memory_buckets()
        return self.memory["profile_memory"]

    def episodic_memory(self) -> List[Dict[str, Any]]:
        self._ensure_memory_buckets()
        return self.memory["episodic_memory"]

    def vector_memory(self) -> List[Dict[str, Any]]:
        self._ensure_memory_buckets()
        return self.memory["vector_memory"]

    def _flatten_memory_view(self) -> Dict[str, Any]:
        """
        Build a prompt-friendly flattened memory view over the structured buckets.
        """
        self._ensure_memory_buckets()
        flattened = dict(self.profile_memory())
        episodes = self.episodic_memory()
        if episodes:
            flattened["episodic_count"] = len(episodes)
            latest = episodes[-1]
            if latest.get("summary"):
                flattened["latest_episode_summary"] = latest["summary"]
        vectors = self.vector_memory()
        if vectors:
            flattened["vector_memory_count"] = len(vectors)
        return flattened

    def workspace_context(self) -> Dict[str, Any]:
        """
        Return the normalized live workspace view for the current run.
        """
        return {
            "current_turn": self.current_turn_context(),
            "execution_flow": self.execution_flow_context(),
            "generated_code": bool(self.generated_code),
            "test_result": self.test_result,
            "local_memory_keys": sorted(self.local_memory.keys()),
            "tool_call_count": len(self.tool_calls),
            "artifact_keys": sorted(self.artifacts.keys()),
            "error_count": len(self.error_log),
            "conversation_log_count": len(self.conversation_log),
            "trace_count": len(self.trace),
        }

    def session_context(self) -> Dict[str, Any]:
        """
        Return the compact session-level view used across turns.
        """
        flattened_memory = self._flatten_memory_view()
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "profile_memory_keys": sorted(self.profile_memory().keys()),
            "episodic_memory_count": len(self.episodic_memory()),
            "vector_memory_count": len(self.vector_memory()),
            "memory_keys": sorted(flattened_memory.keys()),
            "history_count": len(self.history),
            "conversation_log_count": len(self.conversation_log),
        }

    def recent_conversation_context(self, *, limit: int = 6) -> str:
        """
        Render recent conversation turns into a compact plain-text block.
        """
        if not self.conversation_log:
            return ""

        selected = self.conversation_log[-limit:]
        lines = []
        for message in selected:
            role = message.get("role", "unknown")
            content = (message.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def recent_history_context(self, *, limit: int = 4) -> str:
        """
        Render compact turn summaries from archived history.
        """
        if not self.history:
            return ""

        lines = []
        for item in self.history[-limit:]:
            turn_id = item.get("turn_id", "?")
            user_message = (item.get("user_message") or "").strip()
            summary = (item.get("summary") or "").strip()
            if summary:
                lines.append(f"turn {turn_id}: {user_message} -> {summary}")
            elif user_message:
                lines.append(f"turn {turn_id}: {user_message}")
        return "\n".join(lines)

    def remember_memory(self, key: str, value: Any) -> None:
        """
        Persist stable session-level context across turns.
        """
        self.profile_memory()[key] = value

    def recall_memory(self, key: str, default: Any = None) -> Any:
        """
        Read stable session-level context.
        """
        return self._flatten_memory_view().get(key, default)

    def remember_episode(self, *, summary: str, status: str, turn_id: int | None = None) -> None:
        """
        Persist one episodic memory record for the session.
        """
        episodes = self.episodic_memory()
        episode_turn_id = turn_id if turn_id is not None else self.current_turn_id()
        if episodes and episodes[-1].get("turn_id") == episode_turn_id:
            episodes[-1].update({"summary": summary, "status": status})
            return
        episodes.append({
            "turn_id": episode_turn_id,
            "summary": summary,
            "status": status,
        })

    def remember_vector_memory(self, record: Dict[str, Any]) -> None:
        """
        Placeholder hook for vector-memory style recall records.
        """
        self.vector_memory().append(dict(record))

    def memory_context(self) -> str:
        """
        Render session memory into a compact prompt-friendly block.
        """
        return self.filtered_memory_context()

    def filtered_memory_context(
        self,
        *,
        keys: tuple[str, ...] = (),
        max_items: int = 8,
        max_chars: int = 800,
    ) -> str:
        """
        Render a bounded subset of session memory.
        """
        if not self.memory:
            return ""

        lines = []
        flattened = self._flatten_memory_view()
        items = flattened.items()
        if keys:
            items = [(key, flattened[key]) for key in keys if key in flattened]

        for key, value in list(items)[:max_items]:
            lines.append(f"{key}: {value}")
        content = "\n".join(lines)
        return content[:max_chars].strip()

    def filtered_local_memory_context(
        self,
        *,
        keys: tuple[str, ...] = (),
        max_items: int = 4,
        max_chars: int = 1200,
    ) -> str:
        """
        Render a bounded subset of turn-local working memory.
        """
        if not self.local_memory:
            return ""

        lines = []
        items = self.local_memory.items()
        if keys:
            items = [(key, self.local_memory[key]) for key in keys if key in self.local_memory]

        for key, value in list(items)[:max_items]:
            lines.append(f"{key}: {value}")
        content = "\n".join(lines)
        return content[:max_chars].strip()

    def build_read_context(self, policy: StateReadPolicy) -> StateReadContext:
        """
        Build a normalized, bounded read view for agents.
        """
        return StateReadContext(
            user_request=self.user_request,
            latest_user_message=self.active_user_request(),
            current_turn=self.current_turn_context(),
            conversation_context=self.recent_conversation_context(limit=policy.conversation_message_limit),
            history_context=self.recent_history_context(limit=policy.history_limit),
            memory_context=self.filtered_memory_context(
                keys=policy.memory_keys,
                max_items=policy.memory_max_items,
                max_chars=policy.memory_max_chars,
            ),
            local_memory=self.filtered_local_memory_context(
                keys=policy.local_memory_keys,
                max_items=policy.local_memory_max_items,
                max_chars=policy.local_memory_max_chars,
            ),
        )

    def clear_transient_task_state(self) -> None:
        """
        Clear transient per-task workspace fields before the next turn starts.
        """
        self.plan = []
        self.current_agent = None
        self.next_agent = None
        self.finished = False
        self.step_count = 0
        self.task_spec = {}
        self.retrieved_documents = []
        self.rag_context = []
        self.retrieved_context = []
        self.generated_code = ""
        self.test_result = ""
        self.security_report = ""
        self.agent_outputs = {}
        self.local_memory = {}
        self.tool_calls = []
        self.artifacts = {}
        self.error_log = []
        self.retry_count = 0
        self.security_events = []
        self.trace = []
        self.metrics = RuntimeMetrics()

    def current_turn_id(self) -> int:
        turn = self.current_turn_context()
        return int(turn.get("turn_id", self.turn_id))

    def is_current_turn_archived(self) -> bool:
        if not self.history:
            return False
        return self.history[-1].get("turn_id") == self.current_turn_id()

    def mark_current_turn_finished(
        self,
        *,
        status: str,
        summary: str,
    ) -> None:
        """
        Mark the live current turn with a finalized status and summary.
        """
        turn = self.current_turn_context()
        turn["status"] = status
        turn["summary"] = summary
        self.current_turn = turn

    def archive_current_turn(self, *, summary: str | None = None) -> None:
        """
        Archive the current turn into conversation history before the next turn starts.
        """
        turn = self.current_turn_context()
        if not turn:
            return

        if self.is_current_turn_archived():
            return

        turn_summary = summary or self._build_turn_summary()
        self.history.append({
            "turn_id": turn.get("turn_id", self.turn_id),
            "user_message": turn.get("user_message", self.active_user_request()),
            "summary": turn_summary,
            "plan": list(self.plan),
            "task_spec": dict(self.task_spec),
            "test_result": self.test_result,
            "current_agent": self.current_agent,
            "finished": self.finished,
        })

    def _build_turn_summary(self) -> str:
        if self.test_result:
            return f"test_result={self.test_result}"
        if self.generated_code:
            return "generated code available"
        if self.local_memory.get("research"):
            return "research summary available"
        if self.plan:
            return f"plan={self.plan}"
        return "turn completed"

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

    def record_dispatch(self) -> None:
        """
        记录一次 runtime dispatch。
        """
        self.metrics.dispatch_count += 1

    def record_queue_wait(self, duration_ms: float) -> None:
        """
        记录任务在调度队列中的等待时间。
        """
        self.metrics.queue_wait_ms = round(duration_ms, 2)

    def record_runtime_duration(self, duration_ms: float) -> None:
        """
        记录单次任务运行总耗时。
        """
        self.metrics.runtime_duration_ms = round(duration_ms, 2)

    def record_cold_start(self, duration_ms: float) -> None:
        """
        记录 runtime/container 的冷启动耗时。
        """
        self.metrics.cold_start_ms = round(duration_ms, 2)

    def record_execution_call(self, duration_ms: float, *, success: bool) -> None:
        """
        记录一次执行后端调用的耗时和结果。
        """
        self.metrics.execution_calls += 1
        self.metrics.execution_time_ms += duration_ms
        if not success:
            self.metrics.execution_failures += 1

    def can_continue(self) -> bool:
        """
        runtime 是否还能继续执行
        """
        return (not self.finished) and (self.step_count < self.max_steps)

    def to_snapshot(self) -> Dict[str, Any]:
        """
        Serialize the full session state into a JSON-friendly snapshot.
        """
        return asdict(self)

    @classmethod
    def from_snapshot(cls, payload: Dict[str, Any]) -> "TaskState":
        """
        Rehydrate a TaskState from a previously saved snapshot.
        """
        trace = [
            TraceRecord(**item)
            for item in payload.get("trace", [])
        ]
        tool_calls = [
            ToolCallRecord(**item)
            for item in payload.get("tool_calls", [])
        ]
        security_events = [
            SecurityEvent(**item)
            for item in payload.get("security_events", [])
        ]
        metrics = RuntimeMetrics(**payload.get("metrics", {}))

        return cls(
            task_id=payload["task_id"],
            user_request=payload["user_request"],
            user_id=payload.get("user_id", "user_1"),
            conversation_id=payload.get("conversation_id", "conversation_1"),
            turn_id=payload.get("turn_id", 1),
            latest_user_message=payload.get("latest_user_message", ""),
            submitted_at=payload.get("submitted_at", time.time()),
            plan=payload.get("plan", []),
            current_agent=payload.get("current_agent"),
            next_agent=payload.get("next_agent"),
            finished=payload.get("finished", False),
            step_count=payload.get("step_count", 0),
            max_steps=payload.get("max_steps", 20),
            task_spec=payload.get("task_spec", {}),
            uploaded_files=payload.get("uploaded_files", []),
            retrieved_documents=payload.get("retrieved_documents", []),
            rag_context=payload.get("rag_context", []),
            retrieved_context=payload.get("retrieved_context", []),
            generated_code=payload.get("generated_code", ""),
            test_result=payload.get("test_result", ""),
            security_report=payload.get("security_report", ""),
            agent_outputs=payload.get("agent_outputs", {}),
            local_memory=payload.get("local_memory", {}),
            current_turn=payload.get("current_turn", {}),
            memory=payload.get("memory", {}),
            history=payload.get("history", []),
            conversation_log=payload.get("conversation_log", []),
            tool_calls=tool_calls,
            artifacts=payload.get("artifacts", {}),
            error_log=payload.get("error_log", []),
            retry_count=payload.get("retry_count", 0),
            security_events=security_events,
            trace=trace,
            metrics=metrics,
        )
