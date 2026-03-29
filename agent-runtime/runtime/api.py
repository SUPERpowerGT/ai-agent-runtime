from __future__ import annotations

from runtime.scheduler import InMemoryTaskScheduler
from state.state import TaskState
from runtime.container import build_runtime_container
from runtime.engine import AgentRuntime
from runtime.services.memory import finalize_turn_state


def create_task_state(
    user_request: str,
    *,
    task_id: str = "task_1",
    user_id: str = "user_1",
    conversation_id: str = "conversation_1",
    turn_id: int = 1,
    next_agent: str = "orchestrator",
    max_steps: int = 20,
    uploaded_files: list[str] | None = None,
    retrieved_documents: list[dict] | None = None,
    rag_context: list[str] | None = None,
) -> TaskState:
    """
    Create a fresh TaskState for a single runtime execution.
    """
    return TaskState(
        task_id=task_id,
        user_request=user_request,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        latest_user_message=user_request,
        next_agent=next_agent,
        max_steps=max_steps,
        uploaded_files=uploaded_files or [],
        retrieved_documents=retrieved_documents or [],
        rag_context=rag_context or [],
        current_turn={
            "turn_id": turn_id,
            "user_message": user_request,
            "status": "active",
            "uploaded_files": list(uploaded_files or []),
        },
        memory={
            "profile_memory": {
                "user_id": user_id,
                "conversation_id": conversation_id,
            },
            "episodic_memory": [],
            "vector_memory": [],
        },
        conversation_log=[
            {
                "role": "user",
                "content": user_request,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "turn_id": turn_id,
            }
        ],
    )


def run_task(
    user_request: str,
    *,
    task_id: str = "task_1",
    user_id: str = "user_1",
    conversation_id: str = "conversation_1",
    turn_id: int = 1,
    next_agent: str = "orchestrator",
    max_steps: int = 20,
    uploaded_files: list[str] | None = None,
    retrieved_documents: list[dict] | None = None,
    rag_context: list[str] | None = None,
    runtime: AgentRuntime | None = None,
) -> TaskState:
    """
    Run a single user request through the multi-agent runtime.
    """
    runtime = runtime or AgentRuntime(container=build_runtime_container())
    state = create_task_state(
        user_request,
        task_id=task_id,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        next_agent=next_agent,
        max_steps=max_steps,
        uploaded_files=uploaded_files,
        retrieved_documents=retrieved_documents,
        rag_context=rag_context,
    )
    return runtime.run(state)


def run_queued_tasks(
    requests: list[dict],
    *,
    runtime: AgentRuntime | None = None,
    scheduler: InMemoryTaskScheduler | None = None,
) -> list[TaskState]:
    """
    Run a batch of requests through an in-memory scheduler to surface queueing
    and cold-start metrics as first-class runtime concepts.
    """
    runtime = runtime or AgentRuntime(container=build_runtime_container())
    scheduler = scheduler or InMemoryTaskScheduler()

    for request in requests:
        state = create_task_state(
            request["user_request"],
            task_id=request.get("task_id", "task_1"),
            user_id=request.get("user_id", "user_1"),
            conversation_id=request.get("conversation_id", "conversation_1"),
            turn_id=request.get("turn_id", 1),
            next_agent=request.get("next_agent", "orchestrator"),
            max_steps=request.get("max_steps", 20),
            uploaded_files=request.get("uploaded_files"),
            retrieved_documents=request.get("retrieved_documents"),
            rag_context=request.get("rag_context"),
        )
        scheduler.submit(state, priority=request.get("priority", 0))

    results: list[TaskState] = []
    while scheduler.queue_depth():
        result = scheduler.run_next(runtime)
        if result is not None:
            results.append(result)

    return results


def resume_conversation(
    state: TaskState,
    user_message: str,
    *,
    next_agent: str = "orchestrator",
) -> TaskState:
    """
    Resume a single-session conversation by updating the existing state in place.
    """
    finalize_turn_state(state)
    state.append_user_message(user_message)
    state.next_agent = next_agent
    state.current_agent = None
    state.task_id = f"{state.conversation_id}:turn-{state.turn_id}"
    return state


def run_conversation_turn(
    user_message: str,
    *,
    state: TaskState | None = None,
    user_id: str = "user_1",
    conversation_id: str = "conversation_1",
    turn_id: int = 1,
    next_agent: str = "orchestrator",
    max_steps: int = 20,
    uploaded_files: list[str] | None = None,
    retrieved_documents: list[dict] | None = None,
    rag_context: list[str] | None = None,
    runtime: AgentRuntime | None = None,
) -> TaskState:
    """
    Run a fresh turn or resume an existing single-session conversation.
    """
    runtime = runtime or AgentRuntime(container=build_runtime_container())

    if state is None:
        state = create_task_state(
            user_message,
            task_id=f"{conversation_id}:turn-{turn_id}",
            user_id=user_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            next_agent=next_agent,
            max_steps=max_steps,
            uploaded_files=uploaded_files,
            retrieved_documents=retrieved_documents,
            rag_context=rag_context,
        )
    else:
        if uploaded_files is not None:
            state.uploaded_files = uploaded_files
        state = resume_conversation(state, user_message, next_agent=next_agent)
        if uploaded_files is not None:
            state.sync_current_turn_uploads()
        if retrieved_documents is not None:
            state.retrieved_documents = retrieved_documents
        if rag_context is not None:
            state.rag_context = rag_context

    return runtime.run(state)
