from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.research_agent import ResearchAgent
from state.state import TaskState


class FakeResearchContainer:
    def execute_skill(self, *, state, agent, skill_name: str, **kwargs):
        if skill_name == "rag_retrieve":
            return {
                "documents": [{"source": "upload.py", "text": "def greet_user(name): return f'Hello, {name}!'"}],
                "retrieved_documents": [{"source": "upload.py", "text": "def greet_user(name): return f'Hello, {name}!'"}],
                "context_blocks": [
                    {
                        "id": "context-1",
                        "source": "upload.py",
                        "chunk_id": "chunk-1",
                        "text": "def greet_user(name): return f'Hello, {name}!'",
                        "score": 0.9,
                    }
                ],
                "citations": [{"id": "context-1", "source": "upload.py", "chunk_id": "chunk-1", "score": 0.9}],
                "query_analysis": {"original_query": kwargs["query"]},
                "retrieval_metadata": {"documents_retrieved": 1, "chunks_created": 1},
                "code_contracts": [
                    {
                        "language": "python",
                        "source": "upload.py",
                        "name": "greet_user",
                        "params": ["name"],
                        "arity": 1,
                        "signature": "greet_user(name)",
                    }
                ],
                "behavior_summaries": [
                    {
                        "language": "python",
                        "source": "upload.py",
                        "name": "greet_user",
                        "params": ["name"],
                        "body_preview": "return greeting string",
                        "returned_keys": [],
                        "key_accesses": [],
                    }
                ],
            }

        if skill_name == "web_search":
            return [
                {
                    "title": "Greeting examples",
                    "url": "https://example.com/greeting",
                    "snippet": "Examples of user greeting functions.",
                }
            ]

        raise AssertionError(f"unexpected skill: {skill_name}")


class TestResearchAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = ResearchAgent()
        self.agent.container = FakeResearchContainer()

    @patch("agents.research_agent.call_llm", return_value="research summary about greeting functions")
    def test_research_agent_populates_context_and_advances_plan(self, _mock_call_llm) -> None:
        state = TaskState(
            task_id="task-research-1",
            user_request="compare greeting function implementations",
            latest_user_message="compare greeting function implementations",
            plan=["research", "coder", "tester"],
            next_agent="research",
            uploaded_files=["upload.py"],
        )

        new_state = self.agent.run(state)

        self.assertEqual(new_state.local_memory["research"], "research summary about greeting functions")
        self.assertIsNone(new_state.next_agent)
        self.assertEqual(len(new_state.retrieved_documents), 1)
        self.assertEqual(len(new_state.artifacts["research_raw"]), 1)
        self.assertEqual(new_state.task_spec["code_contracts"][0]["name"], "greet_user")
        self.assertEqual(new_state.task_spec["behavior_summaries"][0]["name"], "greet_user")
        self.assertIn("Examples of user greeting functions.", new_state.retrieved_context)

    @patch("agents.research_agent.call_llm", return_value="research summary with no new contracts")
    def test_research_agent_preserves_existing_code_expectations_when_retrieval_finds_none(self, _mock_call_llm) -> None:
        state = TaskState(
            task_id="task-research-2",
            user_request="continue the same conversation and add a third function",
            latest_user_message="continue the same conversation and add a third function",
            plan=["research", "coder", "tester"],
            next_agent="research",
            task_spec={
                "language": "python",
                "task_mode": "extend",
                "code_contracts": [
                    {
                        "language": "python",
                        "source": "previous_turn.py",
                        "name": "greet_user",
                        "params": ["name"],
                        "arity": 1,
                        "signature": "greet_user(name)",
                    }
                ],
                "behavior_summaries": [
                    {
                        "language": "python",
                        "source": "previous_turn.py",
                        "name": "greet_user",
                        "params": ["name"],
                        "body_preview": 'return f"Hello, {name}!"',
                        "returned_keys": [],
                        "key_accesses": [],
                    }
                ],
            },
            retrieved_documents=[],
        )

        class EmptyRagContainer(FakeResearchContainer):
            def execute_skill(self, *, state, agent, skill_name: str, **kwargs):
                if skill_name == "rag_retrieve":
                    return {
                        "documents": [],
                        "retrieved_documents": [],
                        "context_blocks": [],
                        "citations": [],
                        "query_analysis": {"original_query": kwargs["query"]},
                        "retrieval_metadata": {"documents_retrieved": 0, "chunks_created": 0},
                        "code_contracts": [],
                        "behavior_summaries": [],
                    }
                return super().execute_skill(state=state, agent=agent, skill_name=skill_name, **kwargs)

        self.agent.container = EmptyRagContainer()
        new_state = self.agent.run(state)

        self.assertEqual(new_state.task_spec["code_contracts"][0]["name"], "greet_user")
        self.assertEqual(new_state.task_spec["behavior_summaries"][0]["name"], "greet_user")


if __name__ == "__main__":
    unittest.main()
