from dataclasses import dataclass, field
from typing import List

# 所有agent共享状态，驱动loops循环。
# 目前state安全性仍需要提升，和cmp架构state相比，仍然欠缺，state状态更新会出现锁问题

# dataclass声明注释，无需手动构造函数
@dataclass
class TaskState:
    
    # 任务id，追踪任务序列（分布式）
    task_id: str
    # 用户输入。一切的起点
    user_request: str
    
    # agent生成的计划（LLM思考结果）
    plan: str = ""
    
    # RAG检索的知识
    retrieved_context: List[str] = field(default_factory=list)
    
    # Coder agent的输出：生成的代码
    generated_code: str = ""
    
    # Test agent的输出：测试的结果
    test_result: str = ""

    # error 日志
    error_log: str = ""

    # 安全扫描结果
    security_report: str = ""

    # 循环控制，agent修改代码重试次数
    retry_count: int = 0
    
    finished: bool = False