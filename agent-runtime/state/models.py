# state/models.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceRecord:
    """
    单次 agent 执行记录，用于调试、追踪、审计
    """
    agent_name: str
    stage: str
    message: str
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallRecord:
    """
    工具调用记录，用于审计和调试
    """
    agent_name: str
    tool_name: str
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_output: Any = None
    success: bool = True
    error: str = ""


@dataclass
class SecurityEvent:
    """
    安全事件记录
    """
    level: str   # info / warning / error / critical
    source: str  # agent / runtime / tool
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMemory:
    """
    给单个 agent 使用的局部 memory
    """
    short_term: Dict[str, Any] = field(default_factory=dict)
    long_term: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RuntimeMetrics:
    """
    运行时统计信息
    """
    total_steps: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    agent_runs: Dict[str, int] = field(default_factory=dict)
    agent_durations_ms: Dict[str, float] = field(default_factory=dict)
    llm_time_ms: float = 0.0
    llm_calls_by_agent: Dict[str, int] = field(default_factory=dict)
    llm_time_by_agent_ms: Dict[str, float] = field(default_factory=dict)
