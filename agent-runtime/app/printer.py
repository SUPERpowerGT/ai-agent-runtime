from __future__ import annotations

from pathlib import Path

from observability.metrics_printer import print_runtime_summary
from observability.trace_printer import print_trace_summary
from state.state import TaskState


def print_section(title: str) -> None:
    print()
    print(f"===== {title} =====")


def print_generated_code(result: TaskState) -> None:
    fallback_result = result.artifacts.get("fallback_result")
    runtime_failure = result.artifacts.get("runtime_failure")
    print_section("Generated Code")
    if fallback_result:
        print(
            "[fallback] restored uploaded code as the final result "
            f"({fallback_result.get('reason', 'unspecified')})"
        )
    if runtime_failure:
        print(
            "[runtime-failure] "
            f"{runtime_failure.get('code', 'unknown')}: "
            f"{runtime_failure.get('message', 'runtime failure')}"
        )
    print(result.generated_code)
    print(f"Test result: {result.test_result}")


def print_failure_summary(result: TaskState) -> None:
    runtime_failure = result.artifacts.get("runtime_failure")
    if not runtime_failure and not result.error_log:
        return

    print_section("Failure Summary")
    if runtime_failure:
        print(f"Failure code: {runtime_failure.get('code', 'unknown')}")
        print(f"Failure stage: {runtime_failure.get('stage', 'unknown')}")
        print(f"Failure message: {runtime_failure.get('message', 'runtime failure')}")
        metadata = runtime_failure.get("metadata") or {}
        if metadata:
            print(f"Failure metadata: {metadata}")

    if result.error_log:
        print("Errors:")
        for message in result.error_log:
            print(f"  - {message}")


def print_runtime_report(result: TaskState, *, session_path: Path | None) -> None:
    print_section("Runtime Summary")
    print_runtime_summary(result)
    print(f"Session file: {session_path}")


def print_trace_report(result: TaskState) -> None:
    print_section("Trace Summary")
    print_trace_summary(result)
