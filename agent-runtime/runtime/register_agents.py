from runtime.agent_registry import AgentRegistry

from agents.orchestrator_agent import OrchestratorAgent
from agents.research_agent import ResearchAgent
from agents.coder_agent import CoderAgent
from agents.tester_agent import TesterAgent
from agents.fix_agent import FixAgent
from agents.security_agent import SecurityAgent


registry = AgentRegistry()

registry.register(OrchestratorAgent)
registry.register(ResearchAgent)
#registry.register(CoderAgent)
#registry.register(TesterAgent)
#registry.register(FixAgent)
#registry.register(SecurityAgent)