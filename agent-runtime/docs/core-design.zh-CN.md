# 核心设计

这份文档不是 API 手册，也不是逐文件导览。  
它的目标是用一份相对稳定的设计说明，回答这个项目“核心上到底怎么组织、怎么运行、准备往哪里扩”的问题。

当前项目更适合理解成一个面向代码任务的多 Agent 系统原型，其中：

- `app` 负责入口和展示
- `runtime` 负责执行内核和对外接口
- `workflow` 负责流程骨架
- `agents` 负责角色级决策与执行
- `state` 负责共享状态、会话、记忆和历史
- `infrastructure` 负责和外部能力打交道

## 1. 设计目标

这个项目当前追求的不是“做一个功能尽可能全的大框架”，而是把多 Agent 代码任务里的几个核心问题先拆清楚：

- 一次任务怎样被组织成可执行的 agent 流程
- 多个 agent 怎样共享状态但又保持职责边界
- 单轮任务和多轮会话怎样统一在同一个运行时里
- 执行、路由、记忆、工具调用这些能力怎样解耦
- 后续新增 agent 或调整流程时，怎样尽量不重写 runtime

换句话说，这个项目优先保证的是“结构清楚、边界稳定、便于扩展”，而不是一开始就把并发、分布式、生产级调度全部做满。

## 2. 核心边界

系统里最重要的边界有三条：

- `agent` 保留自己的脑子
- `workflow` 只保留流程骨架
- `runtime` 只保留执行管理与对外接口

这三条边界决定了后面的演进方式。

### Agent

Agent 负责：

- 按自己的角色读取必要上下文
- 做任务理解、推理、生成、验证或修复
- 调用工具、写回结果、更新共享状态

Agent 不负责：

- 全局调度
- 会话持久化
- 队列管理
- 系统级并发治理

### Workflow

Workflow 负责：

- 规范化 plan
- 决定 agent 之间的跳转
- 保证代码变更流程最终经过 tester
- 在 tester / fix 之间形成有限重试闭环

Workflow 不负责：

- 替 agent 做推理
- 直接生成代码
- 直接管理底层工具实现

### Runtime

Runtime 负责：

- 创建或恢复 `TaskState`
- 装配容器、registry、workflow、tools、skills
- 驱动 agent loop
- 处理执行层面的 fallback、收尾和持久化
- 对外暴露稳定入口

Runtime 不应该演变成：

- 一个塞满业务判断的超级 orchestrator
- 一个需要为了新增 agent 而频繁改动核心循环的中心化大对象

## 3. 共享状态模型

系统围绕 `TaskState` 运转。  
它既是一次运行的 blackboard，也是单轮与多轮之间的统一状态载体。

可以把 `TaskState` 分成几块理解：

- 身份信息：`task_id`、`user_id`、`conversation_id`、`turn_id`
- 执行控制：`plan`、`current_agent`、`next_agent`、`step_count`
- 当前输出：`generated_code`、`test_result`、`security_report`
- 当前轮上下文：`current_turn`
- 会话记忆：`memory`
- 归档历史：`history`
- 消息流：`conversation_log`
- 追踪和统计：`trace`、`metrics`
- 工具与错误：`tool_calls`、`artifacts`、`error_log`

这套设计的关键点不是“字段多”，而是把不同生命周期的数据分开：

- 当前 turn 的活跃上下文，放在 `current_turn`
- 跨 turn 的稳定记忆，放在 `memory`
- 已结束 turn 的归档摘要，放在 `history`
- 近期消息流，放在 `conversation_log`

这样做的好处是：

- agent 可以读到自己真正需要的上下文
- runtime 可以在 turn 结束时做统一收尾
- 多轮会话不会把所有数据都混成一团

## 4. 运行主路径

主路径可以概括成：

```text
app / API entry
-> create or resume TaskState
-> build runtime container
-> dispatch agent loop
-> workflow decides next transition
-> persist turn state
-> return final TaskState
```

更具体地说：

1. CLI 或 Python API 接收用户输入
2. `runtime/api.py` 创建新任务，或者恢复旧会话
3. `runtime/container.py` 装配 agents、workflow、tools 和 skills
4. `runtime/engine.py` 进入循环，按 `next_agent` 分发
5. 每个 agent 在自己的职责范围内读取 state、推理并写回结果
6. workflow 根据当前执行结果决定下一步去谁
7. turn 结束后，runtime 统一做 memory / history 持久化与收尾
8. 最终返回完整的 `TaskState`

这里最重要的不是“循环”本身，而是执行权的分配：

- runtime 负责“让系统跑起来”
- agent 负责“这一轮自己怎么做”
- workflow 负责“下一步轮到谁”

## 5. 对外使用模型

当前对外暴露了三种核心使用方式。

### 单轮任务

适合一次请求直接完成：

- `run_task(...)`

它会创建一个新的 `TaskState`，跑完整个 agent 流程，再返回最终结果。

### 多轮会话

适合同一个会话持续续聊：

- `run_conversation_turn(...)`

它的重点不是“新建任务”，而是“在同一个 `conversation_id` 上接着往下跑”。  
上一轮的 memory、history、conversation_log 会继续保留，当前轮则会被刷新为新的活跃上下文。

### 批量队列运行

适合一次提交多个彼此独立的任务：

- `run_queued_tasks(...)`

它的定位是：

- 批量实验
- 队列调度测试
- runtime 行为验证

它不适合拿来续接同一个会话。  
因为它建模的是“多个独立任务排队执行”，不是“同一个会话逐轮推进”。

## 6. Session 与多轮连续性

这个项目对多轮连续性的处理，不是把所有历史都重新塞回 prompt，而是把“当前轮、会话记忆、归档历史”拆开管理。

相关职责大致是：

- `session_manager` 负责恢复会话、校验归属、保存状态
- `store` 负责文件级持久化
- `registry` 负责 conversation 元数据与 ownership
- runtime 在 turn 结束时把本轮结果沉淀进 memory / history

这套设计的意义在于：

- 单轮模式足够直接
- 多轮模式可以延续上下文
- session 持久化不需要侵入 agent 本身

## 7. 批量执行与并发边界

当前项目已经有一个轻量的 `InMemoryTaskScheduler`。  
它把“任务排队”和“runtime 执行”显式分开，但目前仍然是原型级设计。

它适合：

- 在单机内存里模拟排队
- 观察 queue wait 和 dispatch 行为
- 做 runtime 层面的实验

它暂时不等于生产级多租户调度系统。

如果后续走向多用户或高并发，推荐的分工是：

- 后端 / runtime 负责真正的任务并发、队列、限流、配额和会话锁
- agent 负责做到可重入、状态隔离、不要依赖共享脏状态

也就是说：

- agent 要“支持并发环境”
- 但并发治理本身不应该主要放在 agent 身上

## 8. 为什么要用 Container

这个项目用 container 来装配 runtime 所需依赖，核心目的不是炫技，而是把“执行逻辑”和“具体实现”分开。

Container 层主要解决：

- agent registry 的注册与解析
- workflow manager 的接入
- tool registry / skill manager 的注入
- runtime 对外保持稳定入口

这样做之后，外部集成方可以：

- 继续沿用默认 runtime
- 替换某些 agent
- 替换 tools / skills / workflow manager
- 在不重写 engine 的前提下调整系统能力

## 9. 为什么强调 Capability 抽象

`capabilities/tools` 和 `capabilities/skills` 的价值，在于不让 agent 直接绑死到底层实现。

这样带来两个好处：

- agent 逻辑更稳定，底层 provider 可以替换
- runtime 更容易在本地执行、检索、MCP、外部 LLM 之间切换

换句话说，这一层是系统的“能力适配层”，它把：

- agent 想做什么
- 底层具体怎么做

拆成了两件事。

## 10. 当前已经稳定的部分

从现在的代码结构看，已经比较稳定、适合继续作为骨架保留的部分主要有：

- runtime 的基本执行循环
- `TaskState` 作为共享状态载体的设计
- workflow 只做骨架与跳转的边界
- 单轮 / 多轮 / 批量三种入口的区分
- session 持久化与恢复机制
- trace / metrics / tool call 的观测面

这些部分已经足够支撑：

- 架构讲解
- 多 Agent 流程实验
- 多轮代码任务原型验证
- 后续继续扩展 agent 和 workflow

## 11. 当前仍然是原型的部分

这套系统已经可用，但还不是生产化成品。  
当前更像“结构已经跑顺，但能力仍在打磨”的状态。

主要还在继续演进的点包括：

- `tester -> fix -> tester` 闭环质量
- 行为级正确性的确定性验证
- 多用户、高并发、多 worker 场景下的调度治理
- 从内存队列走向持久化队列
- 更完善的隔离、限流、配额和审计

所以更准确的定位是：

- 它已经不是空壳
- 但它的重点仍然是 runtime 架构和 agent 协作原型

## 12. 后续扩展建议

如果后面继续演进，推荐优先沿着下面的方向扩：

1. 继续把新增能力放在 `agents/`、`workflow/`、`capabilities/`
2. 保持 `runtime` 的执行循环尽量稳定
3. 把多用户、高并发能力优先放到后端调度层，而不是塞进 agent
4. 把批量队列从原型内存实现逐步替换成可持久化任务系统
5. 保持 `TaskState` 的生命周期边界清楚，不把临时工作区和长期记忆混写

一句话总结：

这个项目的核心设计，不是“让 runtime 替所有层思考”，而是让系统在明确分层下运行起来，让 agent、workflow、runtime、state 各自只承担自己该承担的那部分复杂度。
