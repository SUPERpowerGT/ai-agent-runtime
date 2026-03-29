from runtime.registry import AgentRegistry

from agents.coder_agent import CoderAgent
from agents.fix_agent import FixAgent
from agents.orchestrator_agent import OrchestratorAgent
from agents.research_agent import ResearchAgent
from agents.security_agent import SecurityAgent
from agents.tester_agent import TesterAgent


def build_agent_registry() -> AgentRegistry:
    registry = AgentRegistry()

    registry.register(OrchestratorAgent)
    registry.register(ResearchAgent)
    registry.register(CoderAgent)
    registry.register(TesterAgent)
    registry.register(FixAgent)
    registry.register(SecurityAgent)

    return registry


registry = build_agent_registry()
