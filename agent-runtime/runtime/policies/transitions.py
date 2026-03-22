CODE_CHANGING_AGENTS = {"coder", "fix"}
PLANNER_ALLOWED_AGENTS = {"research", "coder", "tester", "security"}


def normalize_plan(plan: list[str]) -> list[str]:
    """
    规范化 planner 输出，确保代码产出在交付前一定经过 tester。
    """
    normalized_plan = []

    for agent_name in plan:
        if agent_name not in PLANNER_ALLOWED_AGENTS:
            continue
        if agent_name not in normalized_plan:
            normalized_plan.append(agent_name)

    last_code_agent_index = -1
    for index, agent_name in enumerate(normalized_plan):
        if agent_name in CODE_CHANGING_AGENTS:
            last_code_agent_index = index

    if last_code_agent_index == -1:
        return normalized_plan

    if "tester" not in normalized_plan:
        normalized_plan.append("tester")
        return normalized_plan

    tester_index = normalized_plan.index("tester")
    if tester_index < last_code_agent_index:
        normalized_plan.pop(tester_index)
        normalized_plan.append("tester")

    return normalized_plan


def set_next_planned_agent(state, current_agent_name: str):
    """
    根据当前 plan 推进到下一个 agent。
    """
    if current_agent_name not in state.plan:
        state.finished = True
        state.next_agent = None
        return state

    index = state.plan.index(current_agent_name)

    if index + 1 < len(state.plan):
        state.next_agent = state.plan[index + 1]
        state.finished = False
    else:
        state.finished = True
        state.next_agent = None

    return state


def handle_test_outcome(state, *, max_retries: int):
    """
    根据 tester 结果决定是否进入 fix 闭环。
    """
    if state.test_result == "FAIL":
        failure_history = state.artifacts.setdefault("failure_history", [])
        failure_report = state.artifacts.get("failure_report", {})
        failure_entry = {
            "summary": failure_report.get("summary", state.error_log[-1] if state.error_log else ""),
            "code": (state.generated_code or "").strip(),
        }
        failure_history.append(failure_entry)

        if should_stop_retry_loop(failure_history):
            state.add_error("Stopping retry loop early because repeated validation failures show no progress.")
            state.next_agent = None
            state.finished = True
            return state

        if state.retry_count < max_retries:
            state.next_agent = "fix"
            state.finished = False
        else:
            state.next_agent = None
            state.finished = True
        return state

    state.artifacts.pop("failure_history", None)
    return set_next_planned_agent(state, "tester")


def route_after_fix(state):
    """
    fix 完成后统一返回 tester 重新验证。
    """
    state.next_agent = "tester"
    state.finished = False
    return state


def should_stop_retry_loop(failure_history: list[dict]) -> bool:
    """
    Stop retrying when failures repeat without meaningful progress.
    """
    if len(failure_history) < 2:
        return False

    latest = failure_history[-1]
    previous = failure_history[-2]

    same_summary = latest["summary"] == previous["summary"]
    same_code = latest["code"] == previous["code"]

    if same_summary and same_code:
        return True

    if len(failure_history) >= 3:
        last_three = failure_history[-3:]
        summaries = {entry["summary"] for entry in last_three}
        if len(summaries) == 1:
            return True

    return False
