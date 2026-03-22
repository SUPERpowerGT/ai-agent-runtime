print("MAIN START")

import sys

from runtime import run_task
from state.state import TaskState


def print_section(title: str):
    print()
    print(f"===== {title} =====")


def print_runtime_summary(result: TaskState):
    print(f"Plan: {result.plan}")
    print(f"Task spec: {result.task_spec}")
    print(f"Uploaded files: {result.uploaded_files}")
    print(f"Retrieved docs: {len(result.retrieved_documents)}")
    print(f"Finished: {result.finished}")
    print(f"Current agent: {result.current_agent}")
    print(f"Step count: {result.step_count}")
    print(f"Retry count: {result.retry_count}")
    print(f"Agent runs: {result.metrics.agent_runs}")
    print(f"Total LLM calls: {result.metrics.llm_calls}")
    print(f"Total LLM time: {result.metrics.llm_time_ms:.2f} ms")

    print("Agent durations:")
    for agent_name, duration_ms in result.metrics.agent_durations_ms.items():
        runs = result.metrics.agent_runs.get(agent_name, 0)
        avg_ms = duration_ms / runs if runs else duration_ms
        print(f"  {agent_name}: total={duration_ms:.2f} ms avg={avg_ms:.2f} ms runs={runs}")

    print("LLM time by agent:")
    for agent_name, duration_ms in result.metrics.llm_time_by_agent_ms.items():
        calls = result.metrics.llm_calls_by_agent.get(agent_name, 0)
        avg_ms = duration_ms / calls if calls else duration_ms
        print(f"  {agent_name}: total={duration_ms:.2f} ms avg={avg_ms:.2f} ms calls={calls}")


def print_trace_summary(result: TaskState):
    for record in result.trace:
        status = "OK" if record.success else "ERROR"
        extra = ""
        if "duration_ms" in record.metadata:
            extra = f" ({record.metadata['duration_ms']:.2f} ms)"
        print(f"- [{status}] {record.agent_name}.{record.stage}: {record.message}{extra}")


def main():
    args = sys.argv[1:]
    uploaded_files = []
    remaining_args = []

    index = 0
    while index < len(args):
        if args[index] == "--file" and index + 1 < len(args):
            uploaded_files.append(args[index + 1])
            index += 2
            continue

        remaining_args.append(args[index])
        index += 1

    user_request = (
        " ".join(remaining_args).strip()
        or "write a python function called clamp(value, min_value, max_value) "
           "that returns min_value if value is too small, max_value if value is too "
           "large, otherwise return value. do not use min() or max()"
    )

    result = run_task(user_request, task_id="task_1", uploaded_files=uploaded_files)

    print_section("Generated Code")
    print(result.generated_code)
    print(f"Test result: {result.test_result}")

    print_section("Runtime Summary")
    print_runtime_summary(result)

    print_section("Trace Summary")
    print_trace_summary(result)


if __name__ == "__main__":
    main()
