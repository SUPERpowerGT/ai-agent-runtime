"""
runtime 对外公共接口。

这里是系统执行内核的门面层。
如果外部代码想把 agent-runtime 当成一个可调用库来使用，优先从这里导入：

- create_task_state
- run_task
- run_queued_tasks
- run_conversation_turn
- build_runtime_container

这样外部调用方不需要直接依赖更深层的实现文件路径。
"""

def create_task_state(*args, **kwargs):
    from runtime.api import create_task_state as _create_task_state
    return _create_task_state(*args, **kwargs)


def run_task(*args, **kwargs):
    from runtime.api import run_task as _run_task
    return _run_task(*args, **kwargs)


def build_runtime_container(*args, **kwargs):
    from runtime.container import build_runtime_container as _build_runtime_container
    return _build_runtime_container(*args, **kwargs)


def run_queued_tasks(*args, **kwargs):
    from runtime.api import run_queued_tasks as _run_queued_tasks
    return _run_queued_tasks(*args, **kwargs)


def run_conversation_turn(*args, **kwargs):
    from runtime.api import run_conversation_turn as _run_conversation_turn
    return _run_conversation_turn(*args, **kwargs)


__all__ = [
    "create_task_state",
    "run_task",
    "run_queued_tasks",
    "run_conversation_turn",
    "build_runtime_container",
]
