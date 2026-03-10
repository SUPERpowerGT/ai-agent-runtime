from runtime.engine import AgentRuntime
from runtime.state import TaskState


def main():
    #engine启动
    runtime = AgentRuntime()
    #模拟创建task并模拟输入
    state = TaskState(
        task_id="task_1",
        user_request="write a hello world function in python"
    )

    result = runtime.run(state)

    print("\n===== FINAL RESULT =====")
    print("Generated Code:")
    print(result.generated_code)

    print("\nTest Result:")
    print(result.test_result)

    print("\nSecurity Report:")
    print(result.security_report)


if __name__ == "__main__":
    main()