from __future__ import annotations

from state.state import TaskState


def print_trace_summary(result: TaskState) -> None:
    for record in result.trace:
        status = "OK" if record.success else "ERROR"
        extra = ""
        if "duration_ms" in record.metadata:
            extra = f" ({record.metadata['duration_ms']:.2f} ms)"
        print(f"- [{status}] {record.agent_name}.{record.stage}: {record.message}{extra}")
