"""
nanoAgent —— 一个最小可运行的 AI Agent（核心循环不到 80 行，其余是工具定义和注释）

它只做一件事：让模型自己决定“调用哪个工具”，由我们的 Python 代码真正执行，
再把执行结果交还给模型，如此循环，直到模型不再需要工具为止。

──────────────────────────── 核心循环 ────────────────────────────

    用户任务
       │
       ▼
    ┌──────────────────────────────────────────┐
    │  ① 把 messages + tools 发给模型           │
    │  ② 模型返回 assistant 消息：               │
    │       ├─ 没有 tool_calls → 输出最终回答，结束
    │       └─ 有 tool_calls   → 继续
    │  ③ 我们执行工具，得到结果                    │
    │  ④ 把结果以 role="tool" 追加进 messages     │
    └───────────────────┬──────────────────────┘
                        │  回到 ①（最多 max_iterations 轮）
                        ▼

──────────────────────────── 怎么运行 ────────────────────────────

    pip install -r requirements.txt
    export OPENAI_API_KEY="your-key-here"          # Windows 见 README_CN.md
    python agent.py "列出当前目录下的 Python 文件"

──────────────────────────── 怎么阅读 ────────────────────────────

    如果你第一次接触 Agent，建议先按顺序运行 steps/ 里的 4 个小脚本，
    再回来看这个文件。阅读顺序就是下面 6 节的顺序：

        第 1 节  配置            —— 客户端与开关
        第 2 节  工具说明书        —— 给“模型”看的 JSON
        第 3 节  工具实现          —— 真正干活的 Python 函数
        第 4 节  工具注册表        —— 名字 → 函数
        第 5 节  核心循环          —— Agent 的全部秘密
        第 6 节  入口              —— 命令行用法
"""

import json
import os
import subprocess
import sys

import httpx

try:
    from openai import OpenAI
except ImportError:
    raise SystemExit("缺少 openai 依赖，请先运行：pip install -r requirements.txt")


# ============================================================
# 第 1 节：配置
# ============================================================

# 模型名可以通过环境变量覆盖，方便接入其他兼容 OpenAI 协议的服务。
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# 安全开关：默认开启。执行 shell 命令 / 写文件前会先向用户确认。
# 设为 0、false 或 no 可以关闭（例如在 Docker 沙箱里批量跑任务时）。
SAFE_MODE = os.environ.get("NANOAGENT_SAFE", "1").lower() not in ("0", "false", "no")

# 这两个工具能修改系统，属于“危险操作”，需要人工确认。
# read_file 只读，不需要确认。
DANGEROUS_TOOLS = {"execute_bash", "write_file"}

# client 延迟到第一次调用模型时才创建。
# 这样做有两个好处：没有 API Key 时能给出友好提示；测试时也方便替换成假客户端。
client = None


def get_client():
    """返回全局 OpenAI 客户端；第一次调用时创建。"""
    global client
    if client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit(
                "没有找到 OPENAI_API_KEY。\n"
                "请先设置环境变量后再运行，例如：\n"
                '  PowerShell:  $env:OPENAI_API_KEY="your-key-here"\n'
                '  CMD:         set OPENAI_API_KEY=your-key-here\n'
                '  Git Bash:    export OPENAI_API_KEY="your-key-here"\n'
                "如果你使用其他兼容 OpenAI 协议的服务，还需要设置 OPENAI_BASE_URL。"
            )
        client = OpenAI(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
             http_client=httpx.Client(
        trust_env=False,
        timeout=30.0,
    ),
        )
    return client


# ============================================================
# 第 2 节：工具说明书（给模型看，不是给 Python 看的）
# ============================================================
#
# 这是新手最容易误解的地方：下面这段 JSON 不会执行任何操作。
# 它只是随请求一起发给模型，告诉模型：
#   “你有哪些工具可用、每个工具叫什么、需要哪些参数”。
# 模型读完这份“菜单”后，只会在回复里说“我想调用 xxx，参数是 yyy”，
# 真正的执行发生在第 3 节的 Python 函数里。
#
# 因此 description 和参数说明要写清楚——它们直接影响模型会不会用对工具。

tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "在用户电脑上执行一条 shell 命令，返回命令的输出。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令，例如 ls、pwd、python --version",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取一个文本文件的全部内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径，例如 README.md 或 notes/todo.txt",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "把内容写入文件（会覆盖同名文件）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要写入的文件路径",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的完整文本内容",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
]


# ============================================================
# 第 3 节：工具实现（真正干活的普通 Python 函数）
# ============================================================
#
# 工具本质上就是普通函数。唯一的要求是：
#   参数名要和第 2 节 schema 里的属性名一致，
#   返回值必须是字符串（或能转成字符串），因为要作为 tool 消息回传给模型。
#
# 注意：函数内部用 try/except 把错误变成字符串返回，而不是让程序崩溃。
# 这样模型能看到“执行失败了，原因是……”，并有机会换个方法重试。


def execute_bash(command):
    """执行一条 shell 命令，返回标准输出 + 标准错误。"""
    try:
        # shell=True：在 Windows 上走 cmd.exe，在 macOS/Linux 上走 /bin/sh。
        # timeout=30 防止命令卡死；errors="replace" 防止编码问题导致解码崩溃。
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            errors="replace",
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "Error: 命令执行超过 30 秒，已终止。"
    except Exception as error:
        return f"Error: {error}"


def read_file(path):
    """读取文本文件。UTF-8 优先，遇到无法解码的字节用替换字符，避免崩溃。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as error:
        return f"Error: {error}"


def write_file(path, content):
    """写入文本文件（覆盖）。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote to {path}"
    except Exception as error:
        return f"Error: {error}"


# ============================================================
# 第 4 节：工具注册表
# ============================================================
#
# 模型只会返回工具“名字”和参数。我们需要一张表，把名字映射到真正的函数。
# 这张表也是安全边界：不在表里的名字一律拒绝执行。

functions = {
    "execute_bash": execute_bash,
    "read_file": read_file,
    "write_file": write_file,
}


# ============================================================
# 第 5 节：核心循环 —— Agent 的全部秘密
# ============================================================


def parse_tool_arguments(raw_arguments):
    """
    把模型返回的 arguments 字符串解析成 dict。

    模型偶尔会返回不完整的 JSON（例如 '{"path":'），直接 json.loads 会让整个
    Agent 崩溃。这里把错误包装成 _argument_error，交给循环回传给模型，
    让模型自己修正参数后重试。
    """
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as error:
        return {"_argument_error": f"Invalid JSON arguments: {error}"}
    # 参数必须是 JSON 对象；数组或字符串都视为无效参数。
    return parsed if isinstance(parsed, dict) else {}


def preview(value, limit=300):
    """把可能很长的参数值截断，避免确认时刷屏。"""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"...（共 {len(text)} 个字符）"


def confirm_tool_call(name, arguments):
    """
    人类确认（human-in-the-loop）：危险操作执行前，先让用户看一眼。

    用户拒绝时返回 False，run_agent 会把“用户拒绝执行”作为工具结果回传给模型，
    模型就知道这条路走不通，可以换一种方式完成任务。
    """
    print("\n" + "=" * 60)
    print(f"模型请求执行危险操作：{name}")
    for key, value in arguments.items():
        print(f"  {key} = {preview(value)}")
    print("=" * 60)

    try:
        answer = input("允许执行吗？输入 y 允许，直接回车拒绝: ").strip().lower()
    except EOFError:
        # 非交互环境（例如管道、定时任务）里拿不到输入，按拒绝处理。
        answer = ""
    return answer in ("y", "yes")


def run_agent(user_message, max_iterations=5):
    """
    运行 Agent，返回模型的最终文本回答。

    参数：
        user_message   用户的任务描述
        max_iterations 最多循环几轮，防止模型反复调用工具停不下来
    """
    # messages 是整个 Agent 的“短期记忆”：
    #   system    —— 给模型的行为设定
    #   user      —— 用户任务
    #   assistant —— 模型自己的回复（包括它提出的工具调用请求）
    #   tool      —— 我们执行工具后得到的结果
    # 每轮循环都把这整份列表重新发给模型，所以模型能“看到”之前发生了什么。
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Be concise."},
        {"role": "user", "content": user_message},
    ]

    for iteration in range(1, max_iterations + 1):
        # ----------------------------------------------------
        # ① 调用模型：把完整对话和工具说明书一起发过去
        # ----------------------------------------------------
        response = get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
        )
        message = response.choices[0].message

        # 把模型这条回复原样存进历史。
        # 如果它包含 tool_calls，下一轮必须带着它，否则模型会不认账。
        messages.append(message)

        # ----------------------------------------------------
        # ② 判断结束条件：模型不再要求调用工具，就说明它要给出最终回答
        # ----------------------------------------------------
        if not message.tool_calls:
            return message.content

        # ----------------------------------------------------
        # ③ 逐个执行模型请求的工具
        # ----------------------------------------------------
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = parse_tool_arguments(tool_call.function.arguments)

            print(f"[第 {iteration} 轮] 模型请求工具：{name}({arguments})")

            # 参数不是合法 JSON：把错误告诉模型，让它重试。
            if "_argument_error" in arguments:
                result = f"Error: {arguments['_argument_error']}"
            # 模型编造了不存在的工具：同样回传错误，而不是崩溃。
            elif name not in functions:
                result = f"Error: Unknown tool '{name}'"
            # 危险操作：先问用户。用户拒绝就不执行。
            elif SAFE_MODE and name in DANGEROUS_TOOLS and not confirm_tool_call(name, arguments):
                result = "用户拒绝执行，工具没有运行。"
            else:
                try:
                    result = functions[name](**arguments)
                except Exception as error:
                    # 参数数量不对、类型不对等，也作为工具错误回传给模型。
                    result = f"Error: {error}"

            # ----------------------------------------------------
            # ④ 把执行结果作为 tool 消息回填
            # ----------------------------------------------------
            # role 必须是 "tool"，并且 tool_call_id 必须和模型请求里的 id 一一对应。
            # 模型靠这个 id 判断“这条结果是在回答哪一次调用”。
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                }
            )

        # 这一轮的工具都执行完了，回到 ①，让模型根据结果决定下一步。

    # 循环用完还没结束，通常意味着任务太复杂，或者模型陷入了工具调用循环。
    return "Max iterations reached（达到最大轮数，任务可能没有完成）"


# ============================================================
# 第 6 节：入口
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('用法: python agent.py "你的任务"')
        print("示例:")
        print('  python agent.py "当前目录是什么？里面有哪些文件？"')
        print('  python agent.py "创建一个 hello.txt，内容是 Hello World"')
        print('  python agent.py "读一下 README.md 并总结三句话"')
        sys.exit(0)

    # 把所有命令行参数拼成一个任务字符串。
    task = " ".join(sys.argv[1:])
    print(run_agent(task))
