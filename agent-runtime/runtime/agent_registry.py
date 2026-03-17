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

    def get(self, name: str) -> BaseAgent:

        if name not in self._agents:
            raise ValueError(f"Agent '{name}' not found")

        return self._agents[name]()

    def list_agents(self):
        return list(self._agents.keys())