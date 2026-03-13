from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class TaskState:
    """
    Agent Runtime 的共享状态对象（Blackboard）
    所有 agent 都通过这个 state 读写信息
    """

    task_id: str
    user_request: str

    # orchestrator 生成的执行计划
    plan: List[str] = field(default_factory=list)

    # research agent 检索到的信息
    retrieved_context: List[str] = field(default_factory=list)

    # coder agent 生成代码
    generated_code: str = ""

    # tester 结果
    test_result: str = ""

    # security 报告
    security_report: str = ""

    # 错误日志
    error_log: List[str] = field(default_factory=list)

    # retry 次数
    retry_count: int = 0

    # runtime 是否结束
    finished: bool = False

    # 下一个 agent
    next_agent: Optional[str] = None

    # agent 执行历史
    history: List[Dict[str, Any]] = field(default_factory=list)

    # 原始 artifacts
    artifacts: Dict[str, Any] = field(default_factory=dict)

    # 短期 working memory
    working_memory: Dict[str, Any] = field(default_factory=dict)