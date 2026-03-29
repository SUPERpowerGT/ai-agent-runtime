from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def normalize_plan(
    plan: list[str],
    *,
    allowed_agents: tuple[str, ...] | list[str] | set[str] | None = None,
    code_changing_agents: tuple[str, ...] | list[str] | set[str] | None = None,
) -> list[str]:
    """
    规范化计划。
    目标是过滤非法 agent、去重，并确保改代码的流程最终会经过 tester。
    """
    allowed_agents = set(allowed_agents or plan)
    code_changing_agents = set(code_changing_agents or ())
    normalized_plan = []

    for agent_name in plan:
        if agent_name not in allowed_agents:
            continue
        if agent_name not in normalized_plan:
            normalized_plan.append(agent_name)

    last_code_agent_index = -1
    for index, agent_name in enumerate(normalized_plan):
        if agent_name in code_changing_agents:
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
    按当前 state.plan 推进到下一个 agent。
    这是最基础的顺序执行流转。
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


def handle_test_outcome(state, *, max_retries: int, apply_fallback=None):
    """
    处理 tester 结束后的流转规则。
    它会根据测试结果决定：结束、进入 fix、或触发 fallback / 提前停止。
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
            if callable(apply_fallback) and apply_fallback(
                state,
                reason="repeated validation failures show no progress",
            ):
                return state
            state.add_error("Stopping retry loop early because repeated validation failures show no progress.")
            state.next_agent = None
            state.finished = True
            return state

        if state.retry_count < max_retries:
            state.next_agent = "fix"
            state.finished = False
        else:
            if callable(apply_fallback) and apply_fallback(
                state,
                reason="repair retry budget exhausted",
            ):
                return state
            state.next_agent = None
            state.finished = True
        return state

    state.artifacts.pop("failure_history", None)
    return set_next_planned_agent(state, "tester")


def route_after_fix(state):
    """
    fix 完成后固定回到 tester，形成修复闭环。
    """
    state.next_agent = "tester"
    state.finished = False
    return state


def should_stop_retry_loop(failure_history: list[dict]) -> bool:
    """
    判断修复循环是否已经没有进展，避免 fix/tester 无限来回。
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


@dataclass(frozen=True)
class RouteContext:
    task_spec: dict[str, Any]
    uploaded_files: list[str]
    user_request: str


@dataclass(frozen=True)
class RouteTemplate:
    name: str
    recommended_plan: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseRouteTemplate:
    name: str = "base"

    def supports(self, context: RouteContext) -> bool:
        raise NotImplementedError

    def build(self, context: RouteContext) -> RouteTemplate:
        raise NotImplementedError


class RouteRegistry:
    """
    可复用的 workflow 路由模板注册表。
    """

    def __init__(self):
        self._templates: list[BaseRouteTemplate] = []

    def register(self, template: BaseRouteTemplate) -> None:
        """
        注册一个可复用的路由模板。
        """
        self._templates.append(template)

    def resolve(self, *, context: RouteContext) -> RouteTemplate | None:
        """
        按注册顺序匹配第一个可用的路由模板，并返回构建后的路由结果。
        """
        for template in self._templates:
            if template.supports(context):
                return template.build(context)
        return None


class RoutingManager:
    """
    面向 workflow 的路由选择门面。
    """

    def __init__(self, registry: RouteRegistry):
        self.registry = registry

    def resolve_route(
        self,
        *,
        task_spec: dict,
        uploaded_files: list[str] | None,
        user_request: str,
    ) -> RouteTemplate | None:
        """
        对外提供统一的路由入口，把原始输入先整理成 RouteContext 再交给 registry。
        """
        context = RouteContext(
            task_spec=task_spec,
            uploaded_files=uploaded_files or [],
            user_request=user_request,
        )
        return self.registry.resolve(context=context)


class UploadedCodeRewriteTemplate(BaseRouteTemplate):
    name = "uploaded_code_rewrite"

    def supports(self, context: RouteContext) -> bool:
        """
        判断当前任务是否属于“带上传文件的重写”模板。
        """
        return (
            bool(context.uploaded_files)
            and context.task_spec.get("task_mode") == "rewrite"
        )

    def build(self, context: RouteContext) -> RouteTemplate:
        """
        为重写模板生成推荐计划和附加元信息。
        """
        return RouteTemplate(
            name=self.name,
            recommended_plan=["research", "coder", "tester"],
            metadata={
                "reason": "rewrite task with uploaded files requires retrieval before code generation",
                "task_mode": "rewrite",
            },
        )


class UploadedCodeOptimizeTemplate(BaseRouteTemplate):
    name = "uploaded_code_optimize"

    def supports(self, context: RouteContext) -> bool:
        """
        判断当前任务是否属于“带上传文件的优化”模板。
        """
        return (
            bool(context.uploaded_files)
            and context.task_spec.get("task_mode") == "optimize"
        )

    def build(self, context: RouteContext) -> RouteTemplate:
        """
        为优化模板生成推荐计划和附加元信息。
        """
        return RouteTemplate(
            name=self.name,
            recommended_plan=["research", "coder", "tester"],
            metadata={
                "reason": "optimize task with uploaded files requires retrieval before code generation",
                "task_mode": "optimize",
            },
        )


def build_route_registry() -> RouteRegistry:
    """
    构建默认的 workflow 路由注册表，并注册内置模板。
    """
    registry = RouteRegistry()
    registry.register(UploadedCodeRewriteTemplate())
    registry.register(UploadedCodeOptimizeTemplate())
    return registry


def build_routing_manager(*, route_registry=None) -> RoutingManager:
    """
    构建路由管理器；如果没有显式传入 registry，则使用默认内置 registry。
    """
    return RoutingManager(route_registry or build_route_registry())


class WorkflowManager:
    """
    workflow 的中心流转控制器。

    agent 负责写出自己的结果和判定，workflow manager 根据这些结果
    决定当前 turn 下一步应该运行哪个 agent。
    """

    def resolve_next(self, *, state, agent, apply_fallback=None) -> object:
        """
        workflow 的统一流转入口。
        它读取 agent 声明的 workflow_transition，再决定当前 turn 下一步该去哪里。
        """
        if state.artifacts.get("fatal_error"):
            return state

        transition = getattr(agent, "workflow_transition", "plan_progress")
        agent_name = getattr(agent, "name", None)

        if transition == "start_plan":
            if state.plan:
                state.next_agent = state.plan[0]
                state.finished = False
            else:
                state.next_agent = None
                state.finished = True
            return state

        if transition == "test_outcome":
            return handle_test_outcome(
                state,
                max_retries=getattr(agent, "max_steps", 0),
                apply_fallback=apply_fallback,
            )

        if transition == "after_fix":
            return route_after_fix(state)

        if not agent_name:
            return state

        return set_next_planned_agent(state, agent_name)


def build_workflow_manager() -> WorkflowManager:
    """
    构建默认的 workflow manager。
    """
    return WorkflowManager()
