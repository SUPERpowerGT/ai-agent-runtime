from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.api import run_conversation_turn
from runtime.services.memory import persist_turn_memory_and_history


class FakeRuntime:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, state):
        self.calls += 1
        state.plan = ["coder", "tester"]
        state.generated_code = (
            f"def generated_turn_{state.turn_id}(value):\n"
            f"    return value\n"
        )
        state.test_result = "PASS"
        state.finished = True
        state.next_agent = None
        state.current_agent = "tester"
        state.local_memory["research"] = f"research turn {state.turn_id}"
        return persist_turn_memory_and_history(state)


class TestRuntimeMultiTurnSession(unittest.TestCase):
    def test_multi_turn_conversation_accumulates_history_and_memory(self) -> None:
        runtime = FakeRuntime()

        state = run_conversation_turn(
            "write greet_user(name)",
            user_id="demo-user",
            conversation_id="demo-conversation",
            turn_id=1,
            runtime=runtime,
        )
        self.assertEqual(state.turn_id, 1)
        self.assertEqual(state.current_turn["status"], "completed")
        self.assertEqual(len(state.history), 1)
        self.assertEqual(len(state.conversation_log), 1)
        self.assertEqual(len(state.episodic_memory()), 1)
        self.assertIn("session_summary", state.profile_memory())
        self.assertIn("last_code_contracts", state.profile_memory())
        self.assertEqual(state.profile_memory()["last_code_contracts"][0]["name"], "generated_turn_1")
        self.assertIn("last_behavior_summaries", state.profile_memory())

        state = run_conversation_turn(
            "keep greet_user and add greet_formally(name, title)",
            state=state,
            runtime=runtime,
        )
        self.assertEqual(state.turn_id, 2)
        self.assertEqual(state.current_turn["status"], "completed")
        self.assertEqual(len(state.history), 2)
        self.assertEqual(len(state.conversation_log), 2)
        self.assertEqual(len(state.episodic_memory()), 2)
        self.assertEqual(state.history[-1]["turn_id"], 2)
        self.assertIn("turn 1:", state.profile_memory()["session_summary"])
        self.assertIn("turn 2:", state.profile_memory()["session_summary"])
        self.assertEqual(state.profile_memory()["last_code_contracts"][0]["name"], "generated_turn_2")

        state = run_conversation_turn(
            "keep both previous functions and add greet_many(names)",
            state=state,
            runtime=runtime,
        )
        self.assertEqual(state.turn_id, 3)
        self.assertEqual(state.current_turn["status"], "completed")
        self.assertEqual(len(state.history), 3)
        self.assertEqual(len(state.conversation_log), 3)
        self.assertEqual(len(state.episodic_memory()), 3)
        self.assertEqual(state.current_turn["summary"], "test_result=PASS, generated_code=yes")
        self.assertEqual(state.local_memory["research"], "research turn 3")
        self.assertIn("turn 3:", state.profile_memory()["session_summary"])
        self.assertEqual(state.profile_memory()["last_code_contracts"][0]["name"], "generated_turn_3")

    def test_resume_clears_transient_workspace_before_next_turn(self) -> None:
        runtime = FakeRuntime()

        state = run_conversation_turn(
            "first turn",
            user_id="demo-user",
            conversation_id="demo-conversation",
            turn_id=1,
            runtime=runtime,
        )
        state.artifacts["draft"] = "artifact-from-turn-1"
        state.tool_calls = ["placeholder"]  # type: ignore[assignment]

        state = run_conversation_turn(
            "second turn",
            state=state,
            runtime=runtime,
        )

        self.assertEqual(state.turn_id, 2)
        self.assertEqual(state.artifacts, {})
        self.assertEqual(state.test_result, "PASS")
        self.assertIn("def generated_turn_2", state.generated_code)
        self.assertEqual(state.local_memory["research"], "research turn 2")


if __name__ == "__main__":
    unittest.main()
