from agents.orchestrator_agent import OrchestratorAgent
from state.state import TaskState

# 创建一个测试 state
state = TaskState(
    task_id="test_1",
    user_request="write a python hello world function，help me do some resarch to see others peoeple code"
)

# 创建 agent
agent = OrchestratorAgent()

# 执行
new_state = agent.run(state)

print("\nFinal Plan:", new_state.plan)
print("Next Agent:", new_state.next_agent)