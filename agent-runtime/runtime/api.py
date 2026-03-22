from state.state import TaskState
from runtime.engine import AgentRuntime


def create_task_state(
    user_request: str,
    *,
    task_id: str = "task_1",
    next_agent: str = "orchestrator",
    max_steps: int = 20,
) -> TaskState:
    """
    Create a fresh TaskState for a single runtime execution.
    """
    return TaskState(
        task_id=task_id,
        user_request=user_request,
        next_agent=next_agent,
        max_steps=max_steps,
    )


def run_task(
    user_request: str,
    *,
    task_id: str = "task_1",
    next_agent: str = "orchestrator",
    max_steps: int = 20,
    runtime: AgentRuntime | None = None,
) -> TaskState:
    """
    Run a single user request through the multi-agent runtime.
    """
    runtime = runtime or AgentRuntime()
    state = create_task_state(
        user_request,
        task_id=task_id,
        next_agent=next_agent,
        max_steps=max_steps,
    )
    return runtime.run(state)
