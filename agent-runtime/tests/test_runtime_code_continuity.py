from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.tester_agent import TesterAgent
from runtime.services.transforms import apply_contract_transformations


class TestRuntimeCodeContinuity(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = TesterAgent()

    def test_python_contract_transform_preserves_public_api_names_and_params(self) -> None:
        task_spec = {
            "language": "python",
            "task_mode": "extend",
            "code_contracts": [
                {
                    "name": "greet_user",
                    "arity": 1,
                    "params": ["name: str"],
                }
            ],
        }
        generated_code = """
def greetUser(user_name: str):
    return f"Hello, {user_name}!"
""".strip()

        normalized = apply_contract_transformations(task_spec, generated_code)

        self.assertIn("def greet_user(name: str):", normalized)
        self.assertNotIn("def greetUser", normalized)
        self.assertIn("Hello, {name}!", normalized)
        self.assertNotIn("user_name", normalized)

    def test_requested_public_api_enforces_parameter_order(self) -> None:
        generated_code = """
def greet_formally(title, name):
    return f"Hello, {title} {name}!"
""".strip()

        failure = self.agent._enforce_requested_public_api(
            requested_public_api=[
                {
                    "kind": "function",
                    "name": "greet_formally",
                    "params": ["name", "title"],
                    "arity": 2,
                }
            ],
            target_language="python",
            code=generated_code,
        )

        self.assertEqual(
            failure,
            "Requested function signature mismatch for greet_formally: expected ['name', 'title'], got ['title', 'name']",
        )

    def test_extend_mode_contracts_enforce_parameter_order(self) -> None:
        generated_code = """
def greet_formally(title, name):
    return f"Hello, {title} {name}!"
""".strip()

        failure = self.agent._enforce_code_contracts(
            state_contracts=[
                {
                    "name": "greet_formally",
                    "arity": 2,
                    "params": ["name", "title"],
                }
            ],
            target_language="python",
            code=generated_code,
        )

        self.assertEqual(
            failure,
            "Function parameter mismatch for greet_formally: expected ['name', 'title'], got ['title', 'name']",
        )

    def test_class_methods_do_not_satisfy_expected_top_level_function_contracts(self) -> None:
        contracts = [
            {
                "name": "greet_user",
                "arity": 1,
                "params": ["name: str"],
            },
            {
                "name": "greet_formally",
                "arity": 2,
                "params": ["name: str", "title: str"],
            },
        ]
        generated_code = """
class Greeting:
    def greet_user(self, name):
        return f"Hello, {name}!"

    def greet_formally(self, name, title):
        return f"Hello, {title} {name}!"
""".strip()

        failure = self.agent._enforce_code_contracts(
            state_contracts=contracts,
            target_language="python",
            code=generated_code,
        )

        self.assertEqual(
            failure,
            "Missing expected functions: ['greet_formally', 'greet_user']",
        )

    def test_top_level_python_functions_satisfy_expected_contracts(self) -> None:
        contracts = [
            {"name": "greet_user", "arity": 1, "params": ["name: str"]},
            {"name": "greet_formally", "arity": 2, "params": ["name: str", "title: str"]},
        ]
        generated_code = """
def greet_user(name):
    return f"Hello, {name}!"

def greet_formally(name, title):
    return f"Hello, {title} {name}!"
""".strip()

        failure = self.agent._enforce_code_contracts(
            state_contracts=contracts,
            target_language="python",
            code=generated_code,
        )

        self.assertIsNone(failure)


if __name__ == "__main__":
    unittest.main()
