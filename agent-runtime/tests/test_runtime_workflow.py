from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from state.state import TaskState
from workflow import WorkflowManager


class _Agent:
    def __init__(self, name: str, *, max_steps: int = 5, workflow_transition: str = "plan_progress") -> None:
        self.name = name
        self.max_steps = max_steps
        self.workflow_transition = workflow_transition


class TestRuntimeWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WorkflowManager()

    def test_orchestrator_plan_is_resolved_by_workflow(self) -> None:
        state = TaskState(
            task_id="task-workflow-1",
            user_request="write code",
            latest_user_message="write code",
            plan=["coder", "tester"],
            next_agent=None,
        )

        state = self.workflow.resolve_next(
            state=state,
            agent=_Agent("orchestrator", workflow_transition="start_plan"),
        )

        self.assertEqual(state.next_agent, "coder")
        self.assertFalse(state.finished)

    def test_research_advances_by_plan_through_workflow(self) -> None:
        state = TaskState(
            task_id="task-workflow-2",
            user_request="research then code",
            latest_user_message="research then code",
            plan=["research", "coder", "tester"],
            next_agent=None,
        )

        state = self.workflow.resolve_next(state=state, agent=_Agent("research"))

        self.assertEqual(state.next_agent, "coder")
        self.assertFalse(state.finished)

    def test_tester_failure_routes_to_fix_through_workflow(self) -> None:
        state = TaskState(
            task_id="task-workflow-3",
            user_request="write code",
            latest_user_message="write code",
            plan=["coder", "tester"],
            test_result="FAIL",
            generated_code="def broken():\n    pass\n",
        )
        state.artifacts["failure_report"] = {"summary": "missing expected function"}

        state = self.workflow.resolve_next(
            state=state,
            agent=_Agent("tester", max_steps=3, workflow_transition="test_outcome"),
        )

        self.assertEqual(state.next_agent, "fix")
        self.assertFalse(state.finished)

    def test_fix_routes_back_to_tester_through_workflow(self) -> None:
        state = TaskState(
            task_id="task-workflow-4",
            user_request="repair code",
            latest_user_message="repair code",
            plan=["coder", "tester"],
        )

        state = self.workflow.resolve_next(
            state=state,
            agent=_Agent("fix", workflow_transition="after_fix"),
        )

        self.assertEqual(state.next_agent, "tester")
        self.assertFalse(state.finished)


if __name__ == "__main__":
    unittest.main()
