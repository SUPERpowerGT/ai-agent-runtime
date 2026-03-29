from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.orchestrator_agent import OrchestratorAgent
from state.state import TaskState


class FakeOrchestratorContainer:
    def resolve_route(self, *, task_spec: dict, uploaded_files: list[str] | None, user_request: str):
        return None


class TestOrchestratorAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = OrchestratorAgent()
        self.agent.container = FakeOrchestratorContainer()

    def test_orchestrator_uses_heuristic_plan_for_code_and_research_task(self) -> None:
        state = TaskState(
            task_id="task-orchestrator-1",
            user_request="write a python function and compare documentation examples from a library",
            latest_user_message="write a python function and compare documentation examples from a library",
            next_agent="orchestrator",
        )

        new_state = self.agent.run(state)

        self.assertEqual(new_state.plan, ["research", "coder", "tester"])
        self.assertIsNone(new_state.next_agent)
        self.assertEqual(new_state.artifacts["plan_source"], "heuristic")
        self.assertEqual(new_state.task_spec["language"], "python")
        self.assertEqual(new_state.task_spec["artifact_type"], "function")

    def test_orchestrator_uses_uploaded_file_heuristic_for_optimize_task(self) -> None:
        state = TaskState(
            task_id="task-orchestrator-2",
            user_request="optimize the uploaded python code and keep the same behavior",
            latest_user_message="optimize the uploaded python code and keep the same behavior",
            next_agent="orchestrator",
            uploaded_files=["test1.py"],
        )

        new_state = self.agent.run(state)

        self.assertEqual(new_state.plan, ["research", "coder", "tester"])
        self.assertIsNone(new_state.next_agent)
        self.assertEqual(new_state.artifacts["plan_source"], "heuristic")
        self.assertEqual(new_state.task_spec["task_mode"], "optimize")

    def test_orchestrator_inherits_previous_code_expectations_for_extend_tasks(self) -> None:
        state = TaskState(
            task_id="task-orchestrator-3",
            user_request="continue the same conversation and add a second function",
            latest_user_message="continue the same conversation and add a second function",
            next_agent="orchestrator",
            memory={
                "profile_memory": {
                    "last_code_contracts": [
                        {
                            "language": "python",
                            "name": "greet_user",
                            "params": ["name"],
                            "arity": 1,
                            "signature": "greet_user(name)",
                        }
                    ],
                    "last_behavior_summaries": [
                        {
                            "language": "python",
                            "name": "greet_user",
                            "params": ["name"],
                            "body_preview": 'return f"Hello, {name}!"',
                            "returned_keys": [],
                            "key_accesses": [],
                        }
                    ],
                },
                "episodic_memory": [],
                "vector_memory": [],
            },
        )

        new_state = self.agent.run(state)

        self.assertEqual(new_state.task_spec["task_mode"], "extend")
        self.assertEqual(new_state.task_spec["code_contracts"][0]["name"], "greet_user")
        self.assertEqual(new_state.task_spec["behavior_summaries"][0]["name"], "greet_user")
        self.assertEqual(new_state.artifacts["code_contracts"][0]["name"], "greet_user")


if __name__ == "__main__":
    unittest.main()
