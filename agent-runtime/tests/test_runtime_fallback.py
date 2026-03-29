from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.engine import AgentRuntime
from state.state import TaskState


class _UnknownAgentContainer:
    def resolve_agent(self, name: str):
        raise ValueError(f"unknown agent: {name}")


class _NoNextAgentContainer:
    def resolve_agent(self, name: str):
        raise AssertionError("resolve_agent should not be called when next_agent is missing")


class _IdleAgent:
    name = "idle"

    def run(self, state):
        state.step_count += 1
        return state


class _MaxStepsContainer:
    def resolve_agent(self, name: str):
        return _IdleAgent()

    def resolve_next_transition(self, *, state, agent):
        state.next_agent = agent.name
        state.finished = False
        return state


class TestRuntimeFallback(unittest.TestCase):
    def test_runtime_fails_when_next_agent_is_missing(self) -> None:
        runtime = AgentRuntime(container=_NoNextAgentContainer())
        state = TaskState(
            task_id="task-fallback-1",
            user_request="test missing next agent",
            latest_user_message="test missing next agent",
            next_agent=None,
        )

        result = runtime.run(state)

        self.assertTrue(result.finished)
        self.assertEqual(result.test_result, "FAIL")
        self.assertEqual(result.artifacts["runtime_failure"]["code"], "missing_next_agent")
        self.assertEqual(result.current_turn["status"], "failed")

    def test_runtime_fails_when_agent_is_unknown(self) -> None:
        runtime = AgentRuntime(container=_UnknownAgentContainer())
        state = TaskState(
            task_id="task-fallback-2",
            user_request="test unknown agent",
            latest_user_message="test unknown agent",
            next_agent="ghost",
        )

        result = runtime.run(state)

        self.assertTrue(result.finished)
        self.assertEqual(result.test_result, "FAIL")
        self.assertEqual(result.artifacts["runtime_failure"]["code"], "unknown_agent")
        self.assertEqual(result.artifacts["runtime_failure"]["metadata"]["agent_name"], "ghost")

    def test_runtime_fails_when_max_steps_is_exceeded(self) -> None:
        runtime = AgentRuntime(container=_MaxStepsContainer())
        state = TaskState(
            task_id="task-fallback-3",
            user_request="test max steps",
            latest_user_message="test max steps",
            next_agent="idle",
            max_steps=1,
        )

        result = runtime.run(state)

        self.assertTrue(result.finished)
        self.assertEqual(result.test_result, "FAIL")
        self.assertEqual(result.artifacts["runtime_failure"]["code"], "max_steps_exceeded")
        self.assertEqual(result.current_turn["status"], "failed")


if __name__ == "__main__":
    unittest.main()
