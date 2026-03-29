from __future__ import annotations

from typing import Any


def fail_turn(
    state,
    *,
    code: str,
    message: str,
    stage: str,
    metadata: dict[str, Any] | None = None,
):
    """
    统一处理 runtime 调度层的不可恢复失败。

    这里兜底的是“系统已经没法继续调度”的情况，例如：
    - next_agent 丢失
    - agent 未注册
    - workflow transition 非法
    - runtime 自身异常
    """
    state.add_error(message)
    state.finished = True
    state.next_agent = None
    state.test_result = state.test_result or "FAIL"
    state.artifacts["runtime_failure"] = {
        "code": code,
        "stage": stage,
        "message": message,
        "metadata": metadata or {},
    }
    state.add_trace(
        agent_name="runtime",
        stage=stage,
        message=message,
        success=False,
        metadata={
            "code": code,
            **(metadata or {}),
        },
    )
    state.mark_current_turn_finished(
        status="failed",
        summary=f"runtime_failure={code}",
    )
    return state
