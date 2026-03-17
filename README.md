# Redmine CLI Agent

A local-first CLI tool that lets you query your company's Redmine instance using natural language. A local LLM (Qwen3-8B via Ollama) interprets your questions, calls Redmine APIs through a custom MCP server, and returns human-readable answers.

**Everything runs on your machine** — no data leaves your laptop except direct calls to your company's Redmine server.

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐     ┌──────────┐
│  CLI (REPL)  │────▶│  Agent Loop       │────▶│  Ollama        │────▶│ Qwen3-8B │
│  Python      │◀────│  (orchestrator)   │◀────│  localhost:11434│◀────│ Q5_K_M   │
└─────────────┘     └──────┬───────────┘     └────────────────┘     └──────────┘
                           │
                           │ tool calls (stdio)
                           ▼
                    ┌──────────────┐     ┌───────────────┐
                    │  MCP Client   │────▶│ Redmine MCP   │───▶ Redmine REST API
                    │  (mcp SDK)    │◀────│ Server (local)│◀─── (company network)
                    └──────────────┘     └───────────────┘
```

## Requirements

- **Python 3.11+**
- **16 GB RAM** (Qwen3-8B uses ~8-10 GB; the rest is for OS and the tool stack)
- **Ollama** installed and running
- Access to a **Redmine instance** with an API key

## Setup

### 1. Install Ollama

**Linux:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**

```bash
brew install ollama
```

**Windows:**

Download and run the installer from [ollama.com/download/windows](https://ollama.com/download/windows), or use winget:

```powershell
winget install Ollama.Ollama
```

Ollama runs as a background service and starts automatically after installation. You'll see it in the system tray.

### 2. Pull the LLM model

```bash
ollama pull qwen3:8b
```

Verify it runs:

```bash
ollama run qwen3:8b "Hello, how are you?"
```

> If Qwen3-8B is too slow or runs out of memory on your machine, use the smaller model instead:
> ```bash
> ollama pull qwen3:4b
> ```

### 3. Get your Redmine API key

1. Log in to your Redmine instance
2. Go to **My Account** (top-right menu)
3. Copy the **API access key** from the right sidebar

### 4. Clone and install

```bash
git clone <repo-url>
cd local-llm-cli-redmine-tool
```

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Configure

**Linux/macOS:**

```bash
export REDMINE_URL="https://your-redmine.com"
export REDMINE_API_KEY="your-api-key-here"
```

**Windows (PowerShell):**

```powershell
$env:REDMINE_URL = "https://your-redmine.com"
$env:REDMINE_API_KEY = "your-api-key-here"
```

To make these permanent on Windows, set them via **System Properties > Environment Variables**, or add to your PowerShell profile:

```powershell
[System.Environment]::SetEnvironmentVariable("REDMINE_URL", "https://your-redmine.com", "User")
[System.Environment]::SetEnvironmentVariable("REDMINE_API_KEY", "your-api-key-here", "User")
```

Or edit `config.yaml` directly:

```yaml
redmine:
  url: "https://your-redmine.com"

llm:
  model: "qwen3:8b"          # change to "qwen3:4b" if needed
  temperature: 0.1
  ollama_url: "http://localhost:11434"

agent:
  max_tool_rounds: 5
  max_history_messages: 10
  timeout_seconds: 120
```

Environment variables always override `config.yaml` values.

## Running the MVP

Make sure Ollama is running, then start the CLI:

```bash
python cli.py
```

You'll see:

```
╭──────────────────────────────────────╮
│ Redmine CLI Agent                    │
│ Local LLM-powered Redmine assistant  │
╰──────────────────────────────────────╯
Type your question, or use /help for commands. /quit to exit.

Connecting to MCP server...
Connected.

>
```

Type a natural language question and press Enter.

### Example queries

```
> What projects do we have?
> Show me all open bugs in the backend project
> What's issue #1234 about?
> What am I working on right now?
> How much time was logged on the API project last week?
```

### Slash commands

| Command  | Action                                   |
|----------|------------------------------------------|
| `/help`  | Show available commands                  |
| `/tools` | List available Redmine tools             |
| `/clear` | Reset conversation history               |
| `/model` | Show current model and agent settings    |
| `/debug` | Toggle debug mode (show raw tool calls)  |
| `/quit`  | Exit                                     |

### Debug mode

Toggle with `/debug`. When enabled, you'll see exactly which tools the LLM calls and what they return — useful for diagnosing incorrect tool selection or bad arguments.

## Available tools

The agent has access to 5 read-only Redmine tools:

| Tool                | What it does                              |
|---------------------|-------------------------------------------|
| `list_projects`     | List all accessible projects              |
| `search_issues`     | Search issues by project, status, tracker |
| `get_issue`         | Get full details of a single issue        |
| `get_my_issues`     | Get issues assigned to you                |
| `list_time_entries` | List time entries by project or issue     |

> The MVP is **read-only** — no create, update, or delete operations.

## Running tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Project structure

```
├── config.yaml              # Configuration (Redmine URL, model, agent settings)
├── requirements.txt         # Python dependencies
├── redmine_client.py        # HTTP wrapper for Redmine REST API
├── redmine_mcp_server.py    # MCP server with 5 read-only tools
├── tool_schemas.py          # Tool definitions in OpenAI format
├── agent.py                 # LLM orchestrator + tool loop
├── cli.py                   # REPL interface
└── tests/
    ├── test_redmine_client.py
    ├── test_mcp_server.py
    └── test_queries.py
```

## Troubleshooting

**Ollama not running**
```
Error communicating with LLM: Connection refused
```
- Linux/macOS: run `ollama serve`
- Windows: check that Ollama is running in the system tray. If not, launch it from the Start menu.

**Missing API key**
```
Error: REDMINE_API_KEY not configured.
```
- Linux/macOS: `export REDMINE_API_KEY="your-key"`
- Windows: `$env:REDMINE_API_KEY = "your-key"`

**Model too slow**
Switch to a smaller model:
```bash
ollama pull qwen3:4b
```
- Linux/macOS: `export LLM_MODEL="qwen3:4b" && python cli.py`
- Windows: `$env:LLM_MODEL = "qwen3:4b"; python cli.py`

**Out of memory**
Close other heavy applications. Qwen3-8B needs ~8-10 GB RAM. If that's too much, use `qwen3:4b` instead.

## Known limitations

- Read-only: cannot create, update, or delete issues
- Relies on the LLM correctly interpreting queries — accuracy depends on the model
- Context window is limited; very large result sets get truncated
- No persistent conversation history across sessions
