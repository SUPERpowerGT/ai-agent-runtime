from dataclasses import dataclass, field
from typing import List

# 所有agent共享状态，驱动loops循环。
# 目前state安全性仍需要提升，和cmp架构state相比，仍然欠缺，state状态更新会出现锁问题

# dataclass声明注释，无需手动构造函数
@dataclass
class TaskState:

    task_id: str
    user_request: str

    plan: str = ""

    retrieved_context: List[str] = field(default_factory=list)

    generated_code: str = ""

    test_result: str = ""

    error_log: str = ""

    security_report: str = ""

    retry_count: int = 0

    finished: bool = False

    next_agent: str = ""

    history: List[str] = field(default_factory=list)