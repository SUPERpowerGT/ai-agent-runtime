# Multi-Agent Runtime Framework

**中文** | [English](README.md)

---

一个轻量的多智能体运行时原型，用来探索基于 LLM 的任务编排、共享状态、检索增强、代码生成、验证与修复。

### 项目概览

这个项目在探索一种 runtime 模型：多个 agent 通过共享的 `TaskState` blackboard 协作，而不是彼此传递孤立的 prompt。

当前代码库已经支持：

- 共享 `TaskState`，统一管理流程控制、输出、memory、artifacts 和 tracing
- 统一的 `BaseAgent` 生命周期：
  `before_run -> perceive -> think -> validate_output -> act -> after_run`
- 运行时循环和基于 registry 的 agent 调度
- 用户上传文件的本地 RAG
- DuckDuckGo web search
- language-specific code analysis adapters
- tester / fix 验证与修复闭环
- 结构化日志、trace 和 metrics

它仍然是一个原型框架，但已经不再只是 skeleton。现在 `orchestrator / research / coder / tester / fix` 这条链已经可以支持比较真实的实验。

### 为什么要做这个项目

当 planning、retrieval、validation、repair、safety 全都混在一个大 prompt 循环里时，LLM 应用会越来越难维护。

这个项目把这些职责拆到 runtime abstraction 里，让它们可以被：

- 观察
- 扩展
- 测试
- 审计
- 独立替换

设计目标包括：

- 用共享状态对象协调多个 agent
- 用统一 contract 标准化 agent 执行
- 显式保留 retrieval、validation、repair 和 routing
- 为未来的 language adapters、sandbox 和更丰富的 tools 留出空间

### 架构

#### 核心运行时组件

- `TaskState`：共享 blackboard，存放 plan、next agent、输出、artifacts、memory、errors 和 trace
- `BaseAgent`：所有 agent 的统一生命周期 contract
- `AgentRuntime`：主循环，负责调度 agent 直到结束或达到上限
- `registry`：按名称查找 agent 的注册中心
- `runtime/api.py`：统一入口，比如 `run_task(...)`

#### runtime 分层

- `runtime/bootstrap/`：agent/tool 的 bootstrap 和 wiring
- `runtime/services/`：LLM、logging、task-spec、retrieval、repair、language analysis 等服务
- `runtime/policies/`：plan normalization、tester/fix transitions 等策略

#### 当前 agent 角色

- `OrchestratorAgent`：规划主执行路径
- `ResearchAgent`：结合本地文档和 web 搜索做 research
- `CoderAgent`：基于 task spec 和 research context 生成或改写代码
- `TesterAgent`：分层验证代码
- `FixAgent`：根据结构化 failure report 和 fix strategy 修复代码
- `SecurityAgent`：安全检查占位 agent

### 执行模型

runtime 围绕共享 `TaskState` 工作：

1. runtime 读取 `state.next_agent`
2. registry 解析对应 agent
3. agent 在 `perceive` 阶段读取共享状态
4. agent 在 `think` 阶段推理
5. 输出在 `validate_output` 阶段被标准化
6. agent 在 `act` 阶段修改 state
7. runtime 持续循环，直到 `finished` 或 `max_steps`

代码任务的常见主线流程是：

```text
orchestrator -> research -> coder -> tester
```

如果验证失败，runtime 会动态进入：

```text
tester -> fix -> tester
```

`fix` 不需要出现在初始 plan 中，它由 runtime policy 在测试失败后自动进入。

### 共享状态

`TaskState` 当前包含：

- 流程控制：`plan`, `current_agent`, `next_agent`, `finished`, `step_count`
- 任务输出：`task_spec`, `generated_code`, `test_result`, `security_report`
- 检索状态：`uploaded_files`, `retrieved_documents`, `rag_context`, `retrieved_context`
- memory：`working_memory`, `history`, `agent_memories`, `messages`
- artifacts：`tool_calls`, `artifacts`, `agent_outputs`
- 容错和安全：`error_log`, `retry_count`, `security_events`
- 可观测性：`trace`, `metrics`

这让 runtime 更像一个小型 agent OS，而不是简单的 prompt wrapper。

### Agent 生命周期

所有继承 `BaseAgent` 的 agent 都遵循同一套结构：

```text
before_run
  -> perceive
  -> think
  -> validate_output
  -> act
  -> after_run
```

这种设计让 reasoning、validation 和 mutation 更分离，也更方便加入：

- output guards
- trace hooks
- metrics
- tool logging
- policy-driven routing

### Retrieval 与 RAG

runtime 现在支持一个轻量的本地文档 RAG 流程。

#### 当前支持的上传文件类型

- `.txt`
- `.md`
- `.py`
- `.json`
- `.yaml`
- `.yml`

#### 当前检索流程

- 通过 `--file <path>` 传入文件
- 文档被切分成 chunks
- 用轻量关键词匹配检索相关 chunks
- `ResearchAgent` 同时利用本地 chunks 和 web search 结果
- 提取出的 code contracts 和 behavior summaries 会写回 `TaskState`

这是一个有意保持轻量的 MVP，目前还不是 embedding / vector store 方案。

### Language Adapters

语言相关的代码理解能力现在被放进 adapters：

- `agent-runtime/runtime/services/languages/`

当前已启用的 adapter：

- `python.py`

它负责：

- code contract 提取
- behavior summary 提取
- static consistency checks

adapter registry 定义在：

- [agent-runtime/runtime/services/languages/__init__.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/services/languages/__init__.py)

#### 如何新增一种语言

1. 新建 `runtime/services/languages/<language>.py`
2. 实现：
   - `extract_code_contracts`
   - `extract_behavior_summaries`
   - `check_static_consistency`
3. 在 `runtime/services/languages/__init__.py` 注册 `LanguageAdapter`

JavaScript 的 starter template 已经提供：

- [agent-runtime/runtime/services/languages/javascript.py](/Users/zee/xuziyi/projects/ai-agent-runtime/agent-runtime/runtime/services/languages/javascript.py)

### Tester 与 Fix 闭环

验证路径是分层设计的。

#### Tester 的职责

`TesterAgent` 是 validator，不是 code generator。

当前它组合了：

- contract checks
- language-specific static consistency checks
- LLM semantic judgment

验证失败时，它会生成：

- 结构化 `failure_report`
- 对应的 `fix_strategy`

这些内容会写入 runtime artifacts，并被 `FixAgent` 消费。

#### Fix 的职责

`FixAgent` 不自己发明修复策略，它依赖：

- 最新的 validation failure
- 结构化 failure report
- fix strategy
- code contracts
- behavior summaries

这样 repair 逻辑更通用，也不会和某个特定 bug case 绑死。

#### Retry 提前止损

runtime 现在有一个通用的 retry stop 规则。

如果失败重复出现但没有明显进展，runtime 会提前停止，而不是总是把重试次数跑满。

### 可观测性

runtime 当前会记录：

- 每个阶段的 trace
- 每个 agent 的执行次数
- 每个 agent 的耗时
- 总 LLM 调用次数
- 每个 agent 的 LLM 耗时
- tool calls
- errors 和 security events

终端日志也已经结构化：

- `[runtime] ...`
- `[agent:<name>] ...`
- `[tool:<name>] ...`
- `[llm:<name>] ...`

这样更容易分辨 dispatch、tool usage 和 model latency。

### 目录结构

```text
agent-runtime/
├── agents/                    # Agent implementations and BaseAgent
├── examples/
│   └── uploads/               # Sample uploaded files for RAG/manual tests
├── infra/                     # Config and compatibility shims
├── runtime/
│   ├── bootstrap/             # Agent/tool bootstrap wiring
│   ├── legacy/                # Older runtime leftovers kept for reference
│   ├── policies/              # Routing and transition policies
│   ├── services/              # LLM, logging, retrieval, repair, language adapters
│   ├── api.py                 # Reusable runtime entry points
│   ├── engine.py              # Runtime loop
│   └── registry.py            # Agent registry
├── state/                     # TaskState and record models
├── tools/                     # Tool abstractions and providers
└── main.py                    # CLI-style demo runner
```

### 运行项目

#### 1. 安装依赖

使用 `uv`：

```bash
uv sync
```

也可以使用你自己的 Python 环境，从 `pyproject.toml` 安装。

#### 2. 启动本地 OpenAI-compatible 模型服务

默认配置期望 Ollama 运行在：

```text
http://127.0.0.1:11434/v1
```

当前默认值：

```python
BASE_URL = "http://127.0.0.1:11434/v1"
API_KEY = "ollama"
MODEL = "llama3"
```

需要时可以修改 `agent-runtime/infra/config.py`。

#### 3. 运行 demo runner

不带上传文件：

```bash
python agent-runtime/main.py
```

带明确请求：

```bash
python agent-runtime/main.py "write a python function called is_even(n) that returns True for even numbers and False for odd numbers"
```

带上传文件：

```bash
python agent-runtime/main.py \
  --file agent-runtime/examples/uploads/test1.py \
  --file agent-runtime/examples/uploads/test2.py \
  --file agent-runtime/examples/uploads/context.md \
  "optimize the uploaded python code and keep the same behavior"
```

### 作为 API 使用

你也可以不走 `main.py`，而是直接从 Python 调 runtime。

```python
from runtime import run_task

result = run_task(
    "write a python function called is_even(n) that returns True for even numbers and False for odd numbers"
)

print(result.generated_code)
print(result.test_result)
```

带上传文件：

```python
from runtime import run_task

result = run_task(
    "optimize the uploaded python code and keep the same behavior",
    uploaded_files=[
        "agent-runtime/examples/uploads/test1.py",
        "agent-runtime/examples/uploads/test2.py",
        "agent-runtime/examples/uploads/context.md",
    ],
)
```

### 推荐的手动测试用例

- `write a python function that returns "hello world" without printing anything`
- `write a python function called is_even(n) that returns True for even numbers and False for odd numbers`
- `write a python function called clamp(value, min_value, max_value) that returns min_value if value is too small, max_value if value is too large, otherwise return value. do not use min() or max()`
- `optimize the uploaded python code and keep the same behavior`
- `rewrite the uploaded order calculation code in javascript`

### 当前状态

目前已经比较适合探索：

- shared runtime state
- planner/research/coder/tester/fix 流程
- 本地上传文件 RAG
- language adapter 结构
- 结构化 validation -> repair handoff
- tracing、timing 和 logging

仍在继续演进：

- 更丰富的非 Python language adapters
- Python sandbox execution
- 更强的 semantic validation
- 更完整的自动化测试
- 更完善的 CLI / demo 体验

### 备注

这个仓库更适合被理解为一个持续演进的 systems prototype。当前最成熟的部分是 runtime abstraction、shared state、RAG 路径，以及 validation/repair pipeline。

### License

如果你准备对外分发或开源，可以在这里补上项目 license。
