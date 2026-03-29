from __future__ import annotations

from runtime.agents import build_agent_registry
from runtime.services.repair import apply_uploaded_code_fallback
from runtime.skills import build_skill_manager, build_skill_registry
from runtime.tools import init_tools
from workflow import (
    build_route_registry,
    build_routing_manager,
    build_workflow_manager,
)


class RuntimeContainer:
    """
    runtime 依赖装配容器。

    它统一持有 agent、tool、skill 和 workflow 相关的注册表与管理器，
    让执行循环只关心“怎么跑”，不用关心对象该怎么拼起来。
    """

    def __init__(
        self,
        *,
        agent_registry=None,
        tool_registry=None,
        skill_registry=None,
        skill_manager=None,
        route_registry=None,
        routing_manager=None,
        workflow_manager=None,
    ):
        self.agent_registry = agent_registry or build_agent_registry()
        self.tool_registry = tool_registry or init_tools()
        self.skill_registry = skill_registry or build_skill_registry(
            tool_registry=self.tool_registry,
        )
        self.skill_manager = skill_manager or build_skill_manager(
            skill_registry=self.skill_registry,
        )
        self.route_registry = route_registry or build_route_registry()
        self.routing_manager = routing_manager or build_routing_manager(
            route_registry=self.route_registry,
        )
        self.workflow_manager = workflow_manager or build_workflow_manager()

    def resolve_agent(self, name: str):
        return self.agent_registry.create(name, container=self)

    def execute_skill(self, *, state, agent, skill_name: str, **kwargs):
        return self.skill_manager.execute_skill(
            state=state,
            agent=agent,
            skill_name=skill_name,
            skill_input=kwargs,
        )

    def resolve_route(self, *, task_spec: dict, uploaded_files: list[str] | None, user_request: str):
        # runtime 通过这个入口向 workflow 请求“有没有已知模板路由”。
        return self.routing_manager.resolve_route(
            task_spec=task_spec,
            uploaded_files=uploaded_files,
            user_request=user_request,
        )

    def resolve_next_transition(self, *, state, agent):
        # runtime 不自己写跳转规则，只把当前状态交给 workflow 决定下一步。
        return self.workflow_manager.resolve_next(
            state=state,
            agent=agent,
            apply_fallback=apply_uploaded_code_fallback,
        )

    def list_plannable_agents(self) -> tuple[str, ...]:
        return self.agent_registry.list_plannable_agents()

    def list_code_changing_agents(self) -> tuple[str, ...]:
        return self.agent_registry.list_code_changing_agents()


def build_runtime_container(
    *,
    agent_registry=None,
    tool_registry=None,
    skill_registry=None,
    skill_manager=None,
    route_registry=None,
    routing_manager=None,
    workflow_manager=None,
) -> RuntimeContainer:
    return RuntimeContainer(
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        skill_registry=skill_registry,
        skill_manager=skill_manager,
        route_registry=route_registry,
        routing_manager=routing_manager,
        workflow_manager=workflow_manager,
    )
