CODE_CHANGING_AGENTS = {"coder", "fix"}


def normalize_plan(plan: list[str]) -> list[str]:
    """
    规范化 planner 输出，确保代码产出在交付前一定经过 tester。
    """
    normalized_plan = []

    for agent_name in plan:
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
        if state.retry_count < max_retries:
            state.next_agent = "fix"
            state.finished = False
        else:
            state.next_agent = None
            state.finished = True
        return state

    return set_next_planned_agent(state, "tester")


def route_after_fix(state):
    """
    fix 完成后统一返回 tester 重新验证。
    """
    state.next_agent = "tester"
    state.finished = False
    return state
