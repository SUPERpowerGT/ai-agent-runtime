# 架构说明

这个项目更适合理解成一个分层明确的 agent system。  
其中 `runtime` 只是系统中的执行内核，不是整个项目的总称。

## 命名约定

- 系统：完整的多 agent 系统
- runtime：负责执行 turn、调度 agent 的内核
- workflow：负责 agent 之间的流程骨架与跳转规则
- agents：负责各自角色的思考、验证与执行
- state：负责 session、workspace、memory、history、trace 等数据

这层区分很重要，因为后续真正需要定制的地方，主要应该落在：

- `agents/`
- `workflow/`

而不是回头去改 `runtime` 的执行设计。

## 分层地图

### 1. App

文件：
[main.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/main.py)
[cli.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/app/cli.py)
[printer.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/app/printer.py)

职责：
- 解析 CLI 输入
- 恢复或创建 session
- 调用 runtime API
- 打印生成结果、指标摘要和 trace 摘要

### 2. Runtime

文件：
[api.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/api.py)
[engine.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/engine.py)
[container.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/container.py)
[scheduler.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/scheduler.py)

职责：
- 创建或恢复 `TaskState`
- 装配 runtime 依赖
- 运行 agent 循环
- 分发 agent
- 处理执行层面的 fallback、retry 和 wiring

判断原则：
如果问题是在问“系统怎么跑起来”，通常就属于这一层。

### 3. Workflow

文件：
[workflow.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/workflow/workflow.py)
[task_spec.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/workflow/task_spec.py)

职责：
- 把用户请求整理成 `task_spec`
- 定义已知的路由模板
- 规范化 plan
- 定义 agent 之间的跳转规则

这里要保持“骨架化”：
- workflow 负责串 agent
- 不负责替 agent 思考

判断原则：
如果问题是在问“下一步该轮到谁”或者“这些 agent 该怎么串起来”，就属于这一层。

### 4. Agents

目录：
`agent-runtime/agents/`

职责：
- 拥有角色本身的行为
- 按受限 read policy 读取 state
- 在自己的角色范围内思考、验证和执行
- 声明属于 agent 自己的 workflow 元信息

典型的 agent 元信息：
- `name`
- `description`
- `workflow_plannable`
- `workflow_internal_only`
- `workflow_code_changing`
- `workflow_transition`

典型的 agent 逻辑：
- research 摘要
- code generation
- validation
- repair
- security review

### 5. Capabilities

目录：
`agent-runtime/capabilities/skills/`
`agent-runtime/capabilities/tools/`

职责：
- 给 agent 暴露可复用能力
- 分离 capability 抽象与底层实现
- 让 agent 不直接依赖低层执行细节

### 6. Infrastructure

目录：
`agent-runtime/infrastructure/`

职责：
- LLM 集成
- sandbox 执行
- retrieval 实现
- MCP 与 provider 协议

判断原则：
如果代码是在和外部世界、provider 或协议实现打交道，通常属于这一层。

### 7. State

目录：
`agent-runtime/state/`

职责：
- 当前 turn 的 workspace
- session 持久化
- memory
- history
- trace 与 metrics 数据

实用理解：
- `workspace`：当前 turn 的活跃工作状态
- `memory`：跨 turn 记忆，分成 profile / episodic / vector
- `history`：归档后的 turn 摘要
- `conversation_log`：近期消息流

### 8. Observability

目录：
`agent-runtime/observability/`

职责：
- runtime 日志
- trace 摘要渲染
- metrics 摘要渲染

## 请求流转

1. `main.py` 转发到 `app/cli.py`
2. `app/cli.py` 解析输入并恢复 session
3. `runtime/api.py` 创建或恢复 `TaskState`
4. `runtime/container.py` 装配 agents、workflow、tools 和 skills
5. `runtime/engine.py` 分发第一个 agent，通常是 `orchestrator`
6. `orchestrator` 自己负责任务理解与规划决策
7. `workflow` 负责定义流程骨架与跳转规则
8. `runtime` 在循环里执行 agent
9. agent 通过 runtime 管理的 capability wiring 请求 skills 和 tools
10. runtime 收尾、持久化 session，再由 app 层打印结果

## 设计原则

新增一个 agent 时，正常的修改面应该主要是：

1. 新增 agent 实现
2. 在 registry 里注册
3. 在 `workflow` 里接入流程

正常情况下，不应该为了接一个新 agent 去重写 runtime 的执行逻辑。
