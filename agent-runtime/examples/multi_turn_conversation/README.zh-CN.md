# Multi-Turn Conversation Example

**中文** | [English](README.md)

---

这个目录提供了一个可直接运行的三轮多轮会话示例，用来演示当前
单用户、单会话 runtime 的完整链路。

它主要适合演示这些内容：

- 同一个 `conversation_id` 可以跨多轮继续使用
- session 文件会被持久化，并在原地更新
- `turn_id` 会按轮次递增
- 之前的轮次会归档进 `history`
- 当前轮的用户请求会成为新的 active request

更准确地说，这个目录适合被理解成：

- 一个可运行的端到端示例
- 一个 session 连续性示例
- 一个当前 runtime 的轻量 smoke 场景

它目前还不能完全保证这些事情：

- 所有多轮生成场景下都得到高质量代码
- `tester -> fix -> tester` 闭环在每次运行里都稳定修复成功
- 自动的长期偏好提取会稳定进入 `memory`
- 超出当前归档摘要能力之外的复杂 session 总结

## 文件说明

- `questions/turn1.txt`
- `questions/turn2.txt`
- `questions/turn3.txt`
- `run_turn1.sh`
- `run_turn2.sh`
- `run_turn3.sh`
- `run_all_turns.sh`
- `inspect_session.py`

## 快速开始

在仓库根目录下运行：

```bash
bash agent-runtime/examples/multi_turn_conversation/run_all_turns.sh
```

这会做下面几件事：

1. 创建或重置一个专门的示例 session 目录
2. 运行 turn 1
3. 续接 turn 2
4. 续接 turn 3
5. 检查最终保存下来的 session

## 预期结果

在流程结束时，`inspect_session.py` 应该至少能展示：

- `turn_id = 3`
- `history_count >= 2`
- `latest_user_message` 等于 turn 3 的问题
- 整个过程中保持同一个 `conversation_id`

生成代码本身在不同运行之间仍然可能变化，因为其中一部分行为依赖
LLM 输出。这里更重要的预期是 runtime 流程、session 持久化和轮次连
续性保持正确。

## 手动逐步运行

```bash
bash agent-runtime/examples/multi_turn_conversation/run_turn1.sh
bash agent-runtime/examples/multi_turn_conversation/run_turn2.sh
bash agent-runtime/examples/multi_turn_conversation/run_turn3.sh
python agent-runtime/examples/multi_turn_conversation/inspect_session.py
```
