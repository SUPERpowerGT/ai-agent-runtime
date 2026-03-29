from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.api import create_task_state
from state.session_manager import SessionManager


class TestStateSessionManager(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.manager = SessionManager(self.temp_dir.name)

    def test_prepare_state_creates_new_conversation_for_first_turn(self) -> None:
        conversation_id, turn_id, state = self.manager.prepare_state(
            user_id="user-a",
            conversation_id="conv-a",
            resume=False,
            user_request="start a new conversation",
            requested_turn_id=1,
        )

        self.assertEqual(conversation_id, "conv-a")
        self.assertEqual(turn_id, 1)
        self.assertIsNone(state)

        record = self.manager.registry.get("conv-a")
        self.assertIsNotNone(record)
        self.assertEqual(record["user_id"], "user-a")
        self.assertEqual(record["title"], "start a new conversation")

    def test_save_and_resume_advances_turn(self) -> None:
        state = create_task_state(
            "first turn",
            task_id="conv-a:turn-1",
            user_id="user-a",
            conversation_id="conv-a",
            turn_id=1,
        )
        state.finished = True
        state.test_result = "PASS"
        state.mark_current_turn_finished(status="completed", summary="test_result=PASS")
        state.archive_current_turn(summary="test_result=PASS")

        self.manager.save(state)

        conversation_id, turn_id, loaded = self.manager.prepare_state(
            user_id="user-a",
            conversation_id="conv-a",
            resume=True,
            user_request="second turn",
            requested_turn_id=2,
        )

        self.assertEqual(conversation_id, "conv-a")
        self.assertEqual(turn_id, 2)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.turn_id, 1)

    def test_resume_rejects_wrong_user(self) -> None:
        state = create_task_state(
            "first turn",
            task_id="conv-a:turn-1",
            user_id="owner-user",
            conversation_id="conv-a",
            turn_id=1,
        )
        self.manager.save(state)

        with self.assertRaises(ValueError) as ctx:
            self.manager.prepare_state(
                user_id="other-user",
                conversation_id="conv-a",
                resume=True,
                user_request="try to open another user's conversation",
                requested_turn_id=2,
            )

        self.assertIn("belongs to user owner-user", str(ctx.exception))

    def test_non_strict_load_heals_stale_registry_entry(self) -> None:
        self.manager.registry.ensure_conversation(
            user_id="user-a",
            conversation_id="conv-a",
            title="stale conversation",
        )

        loaded = self.manager.load_state(
            user_id="user-a",
            conversation_id="conv-a",
            strict=False,
        )

        self.assertIsNone(loaded)
        self.assertIsNone(self.manager.registry.get("conv-a"))

    def test_existing_conversation_can_continue_without_resume_flag(self) -> None:
        state = create_task_state(
            "first turn",
            task_id="conv-a:turn-1",
            user_id="user-a",
            conversation_id="conv-a",
            turn_id=1,
        )
        self.manager.save(state)

        conversation_id, turn_id, loaded = self.manager.prepare_state(
            user_id="user-a",
            conversation_id="conv-a",
            resume=False,
            user_request="continue the same conversation",
            requested_turn_id=None,
        )

        self.assertEqual(conversation_id, "conv-a")
        self.assertEqual(turn_id, 2)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.turn_id, 1)


if __name__ == "__main__":
    unittest.main()
