# Agent Runtime

**中文** | [English](README.md)

---

一个面向多 Agent 代码任务的运行时原型。  
它把一次任务拆成明确的几层：

- `app`：命令行入口与输出
- `runtime`：执行内核与对外公共接口
- `workflow`：Agent 之间的流程骨架
- `agents`：各角色自己的行为与决策
- `state`：会话、记忆、历史与运行时状态
- `observability`：日志、指标与 trace

你可以通过两种方式使用它：

- 直接从命令行运行
- 作为 Python 运行时库集成到自己的代码里

## 目录说明

核心代码在：

- [agent-runtime/](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime)

最常用的入口有：

- CLI 入口：[agent-runtime/main.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/main.py)
- 运行时公共接口：[agent-runtime/runtime/__init__.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/__init__.py)
- 运行时实现：[agent-runtime/runtime/api.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/api.py)
- 核心设计说明：[agent-runtime/docs/core-design.zh-CN.md](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/docs/core-design.zh-CN.md)
- 多轮示例：[agent-runtime/examples/multi_turn_conversation/run_all_turns.sh](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/examples/multi_turn_conversation/run_all_turns.sh)

## 直接使用

### 1. 命令行使用

最直接的方式：

```bash
python agent-runtime/main.py "write a python function called greet_user(name) that returns Hello, {name}!"
```

带上会话信息：

```bash
python agent-runtime/main.py \
  --user-id demo-user \
  --conversation-id demo-conversation \
  "write a python function called greet_user(name) that returns Hello, {name}!"
```

继续同一个多轮会话：

```bash
python agent-runtime/main.py \
  --resume \
  --conversation-id demo-conversation \
  "keep greet_user and add greet_formally(name, title)"
```

带上传文件：

```bash
python agent-runtime/main.py \
  --file path/to/input.py \
  "optimize this uploaded python code"
```

CLI 会自动做这些事：

- 解析参数
- 恢复或创建 session
- 调用 runtime
- 保存 session
- 打印生成代码、运行摘要和 trace 摘要

### 2. 示例脚本

多轮示例可以直接跑：

```bash
bash agent-runtime/examples/multi_turn_conversation/run_all_turns.sh
```

这个示例会演示：

- turn 1 新建会话
- turn 2 续接会话
- turn 3 再续接
- 最后检查保存下来的 session 内容

相关说明在：

- [agent-runtime/examples/multi_turn_conversation/README.md](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/examples/multi_turn_conversation/README.md)

## 对外公共接口

如果你不是想跑 CLI，而是想在自己的 Python 代码里直接使用，建议从：

- [agent-runtime/runtime/__init__.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/__init__.py)

这里进入。

它现在对外暴露的核心接口有：

- `create_task_state(...)`
- `run_task(...)`
- `run_queued_tasks(...)`
- `run_conversation_turn(...)`
- `build_runtime_container(...)`

这些接口的实际实现都在：

- [agent-runtime/runtime/api.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/api.py)
- [agent-runtime/runtime/container.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/container.py)

### 1. 单轮运行

```python
from runtime import run_task

state = run_task(
    "write a python function called greet_user(name) that returns Hello, {name}!",
    user_id="demo-user",
    conversation_id="demo-conversation",
    turn_id=1,
)

print(state.generated_code)
print(state.test_result)
```

### 2. 多轮会话

```python
from runtime import run_conversation_turn

state = run_conversation_turn(
    "write a python function called greet_user(name) that returns Hello, {name}!",
    user_id="demo-user",
    conversation_id="demo-conversation",
    turn_id=1,
)

state = run_conversation_turn(
    "keep greet_user and add greet_formally(name, title)",
    state=state,
)

print(state.generated_code)
print(state.test_result)
```

### 3. 批量队列运行

这个接口适合：

- 一次提交多个彼此独立的任务
- 让 runtime 按内存队列顺序执行
- 做批量实验、队列调度测试、runtime 行为验证

它不适合同一个会话的一轮一轮续聊。  
如果是多轮对话，请用 `run_conversation_turn(...)`。

```python
from runtime import run_queued_tasks

results = run_queued_tasks([
    {"user_request": "write a python clamp function", "task_id": "task-1"},
    {"user_request": "write a python slugify function", "task_id": "task-2"},
])

for state in results:
    print(state.task_id, state.test_result)
```

这段代码实际做的是：

1. 列表里的每个字典都会变成一个独立任务
2. runtime 先把这些任务放进内存队列
3. scheduler 再按顺序一个个执行
4. 最后返回每个任务执行结束后的 `TaskState`

所以这里的 `results`：

- 不是对话历史
- 也不是单个结果
- 而是一组任务最终状态对象

### 4. 自定义 runtime container

如果你后面想替换：

- agent registry
- tool registry
- skill manager
- workflow manager

可以先自己构建 container，再把它交给 `AgentRuntime` 或 `run_*` 系列接口。

入口在：

- [agent-runtime/runtime/container.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/container.py)

## 运行流程

现在主路径是：

```text
main.py
-> app/cli.py
-> runtime/api.py
-> runtime/engine.py
-> runtime/container.py
-> agent.run(state)
-> workflow.resolve_next(...)
-> 继续循环直到结束
```

更具体一点：

1. `main.py` 转发到 CLI
2. CLI 解析参数并恢复会话
3. `runtime/api.py` 创建或恢复 `TaskState`
4. `runtime/engine.py` 开始 agent loop
5. `orchestrator` 负责任务理解与规划
6. `workflow` 负责 agent 之间的跳转
7. `runtime` 负责执行、调度、容器装配和收尾

## 设计边界

这个项目现在遵守的边界是：

- `agent` 保留自己的脑子
- `workflow` 只保留流程骨架
- `runtime` 只保留执行管理与对外接口

所以后面如果新增一个 Agent，正常应该主要改：

1. `agents/` 里的 agent 实现
2. `runtime/registry` 里的注册
3. `workflow` 里的流程接入

正常情况下，不应该为了一个新 Agent 回头重写 runtime 的执行设计。

## 当前状态

现在已经具备这些能力：

- 多 Agent 协作执行
- 共享 `TaskState`
- 单轮和多轮会话
- session 持久化与恢复
- runtime 指标与 trace
- 基础 research / coder / tester / fix 闭环
- 受限 sandbox 执行

它仍然是一个原型，但已经不只是空壳，已经可以用来跑真实的多轮代码任务实验。

## 当前限制

这个项目现在已经适合以“架构原型”和“运行时原型”的状态收尾，但仍然有一些已知限制：

- `runtime`、`workflow`、session 持久化和 agent 调度这几层已经比较稳定，也已经可以直接使用
- `tester -> fix -> tester` 这条质量闭环还在继续演进，多轮代码任务里仍然可能出现“能发现问题，但不一定修得很干净”的情况
- `examples/` 下面的脚本更适合用来演示流程连续性和 session 持久化，不建议现在把它当成最终代码质量的严格基准
- 当前一部分验证仍然是“规则校验 + LLM 判断”的混合方式，所以行为级正确性还没有做到完全确定

一句话说：

- 架构层已经足够稳定，适合展示、讲解和继续扩展
- 代码生成与自动修复质量这条链路，仍然是后续最值得继续优化的方向
