# nanoAgent 中文教程

> 一个能读文件、写文件、执行命令的最小 AI Agent。
> 核心循环不到 80 行，其余是工具定义和注释。**如果你会一点 Python，就能看懂 Agent 的全部秘密。**

这个仓库在原版 [sanbuphy/nanoAgent](https://github.com/sanbuphy/nanoAgent) 的基础上做了教学化改造：

- `agent.py` 全文中文逐段注释，按“配置 → 工具说明书 → 工具实现 → 注册表 → 循环 → 入口”组织
- 新增 `steps/` 目录，用 4 个可独立运行的小脚本，把 Agent 一步步搭出来
- 增加危险操作前的人工确认（默认开启）
- 修复坏 JSON 参数导致崩溃、Windows 中文文件读取失败等问题
- 仓库自带的回归测试已全部恢复通过

---

## 30 秒跑起来

**要求**：Python 3.9+，以及一个支持 function calling 的模型 API Key。

```bash
pip install -r requirements.txt
```

设置环境变量（三选一）：

```powershell
# Windows PowerShell
$env:OPENAI_API_KEY="your-key-here"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"   # 可选
$env:OPENAI_MODEL="gpt-4o-mini"                    # 可选
```

```cmd
:: Windows CMD
set OPENAI_API_KEY=your-key-here
set OPENAI_BASE_URL=https://api.openai.com/v1
set OPENAI_MODEL=gpt-4o-mini
```

```bash
# Git Bash / macOS / Linux
export OPENAI_API_KEY="your-key-here"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选
export OPENAI_MODEL="gpt-4o-mini"                   # 可选
```

运行：

```bash
python agent.py "当前目录是什么？里面有哪些文件？"
python agent.py "创建一个 hello.txt，内容是 Hello World"
python agent.py "读取 README.md，用三句话总结这个项目"
```

> 建议先在一个**专门的空目录**里试玩，不要在主目录或重要项目里直接运行。
> Agent 能执行任意命令，默认虽有人工确认，但仍然要小心。

### 你会看到什么

以创建文件为例，终端大致会输出：

```text
[第 1 轮] 模型请求工具：write_file({'path': 'hello.txt', 'content': 'Hello World'})

============================================================
模型请求执行危险操作：write_file
  path = hello.txt
  content = Hello World
============================================================
允许执行吗？输入 y 允许，直接回车拒绝: y
已创建 hello.txt。
```

输入 `y` 才会真正执行；直接回车（或输入其他内容）会拒绝，模型会收到
“用户拒绝执行”的结果，并尝试换一种方式完成或向你说明。

---

## 最小 Agent 到底做了什么

一句话：**模型负责决策，代码负责执行，循环负责把两者接起来。**

```text
        用户任务
           │
           ▼
┌─────────────────────────────────────────────┐
│ ① 把 messages（对话历史）+ tools（工具菜单）  │
│    一起发给模型                               │
└──────────────────────┬──────────────────────┘
                       ▼
              ┌──────────────────┐
              │ ② 模型返回什么？  │
              └────────┬─────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   没有 tool_calls                 有 tool_calls
   输出最终回答，结束                  │
                                      ▼
                        ┌──────────────────────────┐
                        │ ③ 我们的 Python 代码执行  │
                        │    模型点名要调用的工具    │
                        └────────────┬─────────────┘
                                     ▼
                        ┌──────────────────────────┐
                        │ ④ 结果以 role="tool"      │
                        │    追加进 messages        │
                        └────────────┬─────────────┘
                                     │
                                     └──► 回到 ①（最多 max_iterations 轮）
```

对应到 `agent.py`：

| 步骤 | 代码位置 | 在做什么 |
|---|---|---|
| ① | `run_agent()` 中的 `client.chat.completions.create(...)` | 把对话和工具菜单发给模型 |
| ② | `if not message.tool_calls: return message.content` | 判断模型是否还要用工具 |
| ③ | `functions[name](**arguments)` | 执行模型请求的工具 |
| ④ | `messages.append({"role": "tool", ...})` | 把结果回填给模型 |

### 5 个必须理解的概念

| 概念 | 是什么 | 为什么重要 |
|---|---|---|
| `messages` | 对话历史列表 | 模型没有记忆，每次请求都要把完整历史带上 |
| `role` | `system` / `user` / `assistant` / `tool` | 标记每条消息是谁说的；工具结果必须用 `tool` |
| `tools` | 给模型看的工具说明书（JSON schema） | 它不会执行任何东西，只影响模型“怎么请求” |
| `tool_calls` | 模型返回的调用请求 | 包含工具名、JSON 字符串参数、唯一 `id` |
| `tool_call_id` | 工具结果对应的调用 id | 模型靠它把“结果”和“请求”配对，不能省 |

还有一个容易忽略的：`max_iterations`。它是循环上限，防止模型反复调用工具停不下来。
默认 5 轮；复杂任务可以调大，但不要无限大。

---

## 怎么读这个项目

### 路线 A：先跑再读（推荐给完全没接触过 Agent 的人，约 30 分钟）

```bash
python steps/01_hello_llm.py        # 只有对话
python steps/02_watch_tool_call.py  # 模型只“请求”，不执行
python steps/03_execute_one_tool.py # 执行一次并回填
python steps/04_agent_loop.py       # 完整循环
```

每一步的说明、预期输出和新增代码，见 [`steps/README.md`](./steps/README.md)。

### 路线 B：直接读主文件（约 20 分钟）

按 `agent.py` 里的 6 节顺序读：

1. **配置**：客户端、模型名、安全开关
2. **工具说明书**：`tools` 列表——给模型看的菜单
3. **工具实现**：`execute_bash` / `read_file` / `write_file`——真正干活的函数
4. **工具注册表**：名字到函数的映射
5. **核心循环**：`run_agent()`，全文最重要的 40 行
6. **入口**：命令行参数怎么变成任务

### 文件说明

| 文件 | 用途 | 建议 |
|---|---|---|
| `agent.py` | 教学主文件，最小可用 Agent | 必读 |
| `steps/` | 4 个渐进式脚本 | 新手先跑一遍 |
| `agent-plus.py` | 进阶：任务规划 + 长期记忆 | 读完主文件再看 |
| `agent-claudecode.py` | 进阶：规则、技能、MCP 工具加载 | 最后看 |
| `tests/test_agent.py` | 回归测试，覆盖坏参数、未知工具等 | 学完可跑 |

运行测试（不需要 API Key）：

```bash
python -m unittest discover -s tests -v
```

---

## 安全说明（重要）

`execute_bash` 用 `shell=True` 执行任意命令，`write_file` 可以写任意路径。
模型被提示词注入或判断失误时，可能执行你并不想执行的操作。

本仓库的保护措施：

1. **执行前确认**：`execute_bash` 和 `write_file` 会先打印完整参数，询问 `y/N`。
   默认拒绝，只有输入 `y` 或 `yes` 才执行。
2. **循环上限**：最多 5 轮，避免失控。
3. **错误回传**：坏 JSON、未知工具、工具异常都不会让程序崩溃。

确认功能可以关闭（例如在 Docker 沙箱里批量运行）：

```bash
# Git Bash / macOS / Linux
export NANOAGENT_SAFE=0

# Windows PowerShell
$env:NANOAGENT_SAFE="0"

# Windows CMD
set NANOAGENT_SAFE=0
```

**但请先理解风险再关闭。** 更稳妥的做法是：

- 在专门的空目录里运行；
- 用 Docker 容器隔离；
- 或者把 `execute_bash` 从 `tools` 列表和 `functions` 注册表里删掉，只保留读文件。

---

## 自己动手改（最好的学习方式）

### 练习 1：加一个 `list_dir` 工具

在 `tools` 里加一段 schema，在 `functions` 里注册实现：

```python
def list_dir(path="."):
    import os
    return "\n".join(sorted(os.listdir(path)))
```

然后运行：

```bash
python agent.py "列出当前目录的文件，然后读 README.md 总结一下"
```

观察模型会不会自己决定先列目录、再读文件。

### 练习 2：改系统提示词

把 `run_agent()` 里的：

```python
{"role": "system", "content": "You are a helpful assistant. Be concise."}
```

改成中文，并加入约束，例如“回答前必须先读取相关文件”。观察行为变化。

### 练习 3：给工具加日志

在 `run_agent()` 执行工具的地方，把每次调用的时间、工具名、参数写进
`agent.log`。这是理解 Agent 行为最直接的办法。

### 练习 4：让 `max_iterations` 可配置

从环境变量读取轮数，例如 `NANOAGENT_MAX_STEPS`。试试设成 1，看看复杂任务会怎样失败。

---

## 常见问题

**Q：报错 `AuthenticationError` / 401？**
`OPENAI_API_KEY` 没设置或填错。PowerShell 中设置后，需要在同一个会话里运行，或重开终端重新设置。

**Q：报错模型不存在，或 `tools` 参数不被支持？**
你用的模型不支持 function calling。换一个支持工具调用的模型，或用 `OPENAI_MODEL` 指定。

**Q：报错 `Max iterations reached`？**
模型在 5 轮内没完成任务。可能是任务太复杂，或模型反复调用同一个工具。可以调大 `max_iterations`，或把任务拆小。

**Q：Windows 下读中文文件乱码？**
`read_file` / `write_file` 已显式使用 UTF-8。如果你读的是 GBK 编码的旧文件，可能仍会替换字符；先用编辑器转成 UTF-8 即可。

**Q：`python agent.py` 不带参数为什么没有反应？**
现在会打印用法和示例，不会执行任务。这是有意设计的，避免误触。

**Q：一定要用 OpenAI 吗？**
不一定。只要服务兼容 OpenAI 的 Chat Completions + function calling 协议，设置 `OPENAI_BASE_URL` 和 `OPENAI_MODEL` 即可，例如 DeepSeek、通义千问、智谱等兼容接口。

---

## 进阶路线

1. **`agent-plus.py`**：看 `create_plan()` 如何让模型先拆任务，`load_memory()` / `save_memory()` 如何做跨轮记忆。
2. **`agent-claudecode.py`**：看规则（rules）、技能（skills）、MCP 工具如何注入系统提示词与工具列表。
3. **MCP**：[sanbuphy/nanoMCP](https://github.com/sanbuphy/nanoMCP)，理解工具如何从外部服务动态获取。
4. **概念补充**：Anthropic 的 [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)，理解 workflow 与 agent 的边界。

---

## 致谢与许可

原项目：[sanbuphy/nanoAgent](https://github.com/sanbuphy/nanoAgent)，MIT License。
本仓库的教学化改造同样遵循 MIT License，欢迎继续修改和分享。

> “问题不在于你看到了什么，而在于你看见了什么。” —— 梭罗

看懂那个循环之后，你会发现：Agent 没有魔法，只有**模型决策 + 代码执行 + 结果回填**。
