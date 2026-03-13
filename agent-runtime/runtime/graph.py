from runtime.node import Node

from agents.orchestrator_agent import OrchestratorAgent
from agents.router_agent import RouterAgent
from agents.research_agent import ResearchAgent
from agents.coder_agent import CoderAgent
from agents.tester_agent import TesterAgent
from agents.fix_agent import FixAgent
from agents.security_agent import SecurityAgent

def build_graph():

    orchestrator = Node("orchestrator", OrchestratorAgent())
    router = Node("router", RouterAgent())
    research = Node("research", ResearchAgent())
    coder = Node("coder", CoderAgent())
    tester = Node("tester", TesterAgent())
    fix = Node("fix", FixAgent())
    security = Node("security", SecurityAgent())

    orchestrator.connect(lambda s: True, router)

    router.connect(lambda s: s.next_agent == "research", research)
    router.connect(lambda s: s.next_agent == "coder", coder)
    router.connect(lambda s: s.next_agent == "tester", tester)
    router.connect(lambda s: s.next_agent == "fix", fix)
    router.connect(lambda s: s.next_agent == "security", security)
    router.connect(lambda s: s.next_agent == "finish", None)

    research.connect(lambda s: True, router)
    coder.connect(lambda s: True, router)
    tester.connect(lambda s: True, router)
    fix.connect(lambda s: True, router)
    security.connect(lambda s: True, router)

    class Graph:
        start_node = orchestrator

    return Graph()