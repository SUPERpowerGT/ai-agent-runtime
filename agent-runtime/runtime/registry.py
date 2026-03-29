from typing import Dict, Type
from agents.base_agent import BaseAgent


class AgentRegistry:
    """
    Agent 注册中心
    """

    def __init__(self):
        self._agents: Dict[str, Type[BaseAgent]] = {}

    def register(self, agent_cls: Type[BaseAgent]):
        name = agent_cls.name

        if name in self._agents:
            raise ValueError(f"Agent '{name}' already registered")

        self._agents[name] = agent_cls

    def create(self, name: str, *, container=None) -> BaseAgent:
        if name not in self._agents:
            raise ValueError(f"Agent '{name}' not found")

        agent = self._agents[name]()
        self._attach_container(agent, container=container)
        return agent

    def get(self, name: str, *, container=None) -> BaseAgent:
        return self.create(name, container=container)

    def list_agents(self):
        return list(self._agents.keys())

    def get_agent_class(self, name: str) -> Type[BaseAgent]:
        if name not in self._agents:
            raise ValueError(f"Agent '{name}' not found")
        return self._agents[name]

    def list_agent_classes(self) -> list[Type[BaseAgent]]:
        return list(self._agents.values())

    def list_plannable_agents(self) -> tuple[str, ...]:
        return tuple(
            agent_cls.name
            for agent_cls in self.list_agent_classes()
            if getattr(agent_cls, "workflow_plannable", True)
            and not getattr(agent_cls, "workflow_internal_only", False)
        )

    def list_code_changing_agents(self) -> tuple[str, ...]:
        return tuple(
            agent_cls.name
            for agent_cls in self.list_agent_classes()
            if getattr(agent_cls, "workflow_code_changing", False)
        )

    def list_internal_agents(self) -> tuple[str, ...]:
        return tuple(
            agent_cls.name
            for agent_cls in self.list_agent_classes()
            if getattr(agent_cls, "workflow_internal_only", False)
        )

    def _attach_container(self, agent: BaseAgent, *, container=None) -> None:
        if container is None:
            return
        setattr(agent, "container", container)
        if hasattr(agent, "skill_manager"):
            agent.skill_manager = container.skill_manager
