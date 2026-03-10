print("MAIN START")

from runtime.engine import AgentRuntime
from runtime.graph import build_graph
from runtime.state import TaskState


def main():

    graph = build_graph()
    runtime = AgentRuntime(graph)

    state = TaskState(
        task_id="task_1",
        user_request="write a hello world function in python"
    )

    result = runtime.run(state)

    print(result.generated_code)
    print("Execution Path:")
    print(" -> ".join(result.history))


if __name__ == "__main__":
    main()