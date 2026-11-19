# nanoAgent

[中文](./README_CN.md) | English

> *"The question is not what you look at, but what you see."* — Henry David Thoreau

The simplest way to build an agent that can interact with your system.

A minimal implementation of an AI agent using OpenAI's function calling. The agent can execute bash commands, read files, and write files.

If you want to learn more (e.g. what MCP is, and how to fetch tools in a more modern way), see: https://github.com/sanbuphy/nanoMCP

> **Teaching edition:** `agent.py` is now fully commented in Chinese, and `steps/` contains four
> runnable scripts that build the agent one concept at a time. Start with the
> [Chinese tutorial](README_CN.md) if you are new to agents.
>
> **Safety:** `execute_bash` and `write_file` ask for confirmation before running. Set
> `NANOAGENT_SAFE=0` to disable this (only if you are running in an isolated sandbox).

## install

```bash
pip install -r requirements.txt
```

Set your environment variables:

**macOS/Linux:**
```bash
export OPENAI_API_KEY='your-key-here'
export OPENAI_BASE_URL='https://api.openai.com/v1'  # optional
export OPENAI_MODEL='gpt-4o-mini'  # optional
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY='your-key-here'
$env:OPENAI_BASE_URL='https://api.openai.com/v1'  # optional
$env:OPENAI_MODEL='gpt-4o-mini'  # optional
```

**Windows (CMD):**
```cmd
set OPENAI_API_KEY=your-key-here
set OPENAI_BASE_URL=https://api.openai.com/v1
set OPENAI_MODEL=gpt-4o-mini
```

## quick start

```bash
python agent.py "list all python files in current directory"
python agent.py "create a file called hello.txt with 'Hello World'"
python agent.py "read the contents of README.md"
```

## how it works

The agent uses OpenAI's function calling to:
1. Receive a task from the user
2. Decide which tools to use (bash, read_file, write_file)
3. Execute the tools
4. Return results to the model
5. Repeat until task is complete

That's it. ~100 lines of logic, plus comments and tool schemas.

```python
# Define tools
tools = [{"type": "function", "function": {...}}]

# Agent loop
for _ in range(max_iterations):
    response = client.chat.completions.create(model=model, messages=messages, tools=tools)
    if not response.choices[0].message.tool_calls:
        return response.choices[0].message.content

    # Execute tool calls
    for tool_call in response.choices[0].message.tool_calls:
        result = available_functions[tool_call.function.name](**args)
        messages.append({"role": "tool", "content": result})
```

The core is just a loop: call model → execute tools → repeat.

Malformed JSON arguments, unknown tool names, and tool exceptions are returned to the model as explicit tool errors instead of crashing the agent.

## learning path

1. Run `steps/01_hello_llm.py` → `steps/04_agent_loop.py` in order (see [steps/README.md](steps/README.md)).
2. Read the commented `agent.py` (six sections: config → tool schemas → implementations → registry → loop → entry).
3. Explore `agent-plus.py` (planning + memory) and `agent-claudecode.py` (rules, skills, MCP).

## capabilities

- `execute_bash`: Run any bash command
- `read_file`: Read file contents
- `write_file`: Write content to files

## examples

```bash
# System operations
python agent.py "what's my current directory and what files are in it?"

# File operations
python agent.py "create a python script that prints hello world"

# Combined tasks
python agent.py "find all .py files and count total lines of code"
```

---

## license

MIT

────────────────────────────────────────

⏺ *Like a single seed that grows into a forest, one file becomes infinite possibilities.*
