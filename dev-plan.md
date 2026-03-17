# Redmine CLI Agent — MVP Development Plan

## Project Overview

Build a local-first CLI tool that lets users query their company's Redmine instance using natural language. An LLM running entirely on the laptop interprets the user's intent, calls Redmine APIs through a custom MCP server, and returns human-readable answers.

**Core constraint:** everything runs on a 16GB RAM laptop, CPU only. No data leaves the machine except direct calls to the company Redmine server on the internal network.

---

## Architecture

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

### Tech Stack

| Component           | Technology                          | Why                                              |
| ------------------- | ----------------------------------- | ------------------------------------------------ |
| LLM                 | Qwen3-8B Q5_K_M (fallback: Qwen3-4B) | Best tool-calling in its class, fits 16GB      |
| Inference server    | Ollama                              | Zero-config, OpenAI-compatible API, model mgmt   |
| MCP server          | Python + `mcp` SDK                  | Custom, wraps Redmine REST API                   |
| MCP transport       | stdio                               | Simplest for local process-to-process             |
| Agent orchestrator  | Python (custom, ~150 lines)         | No framework overhead, full transparency          |
| CLI interface       | Python + `rich`                     | Pretty terminal output, tables, spinners          |
| HTTP client         | `httpx`                             | Async-ready, clean API for Redmine REST calls     |

---

## Phase 1 — Local LLM Setup & Validation

**Goal:** confirm the model runs on target hardware and can produce valid tool-call JSON.

**Duration:** ~0.5 day

### Steps

- [ ] **1.1** Install Ollama
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

- [ ] **1.2** Pull the primary model
  ```bash
  ollama pull qwen3:8b
  ```

- [ ] **1.3** Verify it runs and check resource usage
  ```bash
  ollama run qwen3:8b "Hello, how are you?"
  ```
  Monitor RAM with `htop` — confirm it stays under ~10GB leaving headroom for the OS and the rest of the stack.

- [ ] **1.4** Test tool-calling output format.
  Send a raw prompt via the API that includes a tool definition and verify the model returns well-formed JSON tool calls:
  ```bash
  curl http://localhost:11434/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
      "model": "qwen3:8b",
      "messages": [
        {"role": "system", "content": "You are a helpful assistant with access to tools. When you need to use a tool, respond with a JSON tool call."},
        {"role": "user", "content": "List all open issues in the backend project"}
      ],
      "tools": [{
        "type": "function",
        "function": {
          "name": "search_issues",
          "description": "Search Redmine issues with filters",
          "parameters": {
            "type": "object",
            "properties": {
              "project": {"type": "string", "description": "Project identifier"},
              "status": {"type": "string", "enum": ["open", "closed", "all"]}
            },
            "required": ["project"]
          }
        }
      }]
    }'
  ```
  **Pass criteria:** model returns a message with `tool_calls` containing valid function name and arguments.

- [ ] **1.5** If Qwen3-8B is too slow (< 5 tokens/sec) or OOMs, fall back:
  ```bash
  ollama pull qwen3:4b
  ```
  Re-run steps 1.3 and 1.4 with the smaller model.

### Phase 1 deliverable
A running Ollama instance with a confirmed model that fits in memory and produces valid tool-call JSON.

---

## Phase 2 — Redmine MCP Server

**Goal:** a working MCP server that exposes Redmine operations as tools, callable over stdio.

**Duration:** ~1.5 days

### 2A — Redmine API exploration

- [ ] **2A.1** Identify your Redmine instance URL and obtain an API key
  (Redmine → My Account → API access key on the right sidebar)

- [ ] **2A.2** Test basic API calls manually:
  ```bash
  # List projects
  curl -s "https://your-redmine.com/projects.json" \
    -H "X-Redmine-API-Key: YOUR_KEY" | python -m json.tool

  # Search issues
  curl -s "https://your-redmine.com/issues.json?project_id=backend&status_id=open" \
    -H "X-Redmine-API-Key: YOUR_KEY" | python -m json.tool

  # Get single issue
  curl -s "https://your-redmine.com/issues/1234.json" \
    -H "X-Redmine-API-Key: YOUR_KEY" | python -m json.tool
  ```

- [ ] **2A.3** Document the response shapes you'll need to parse.

### 2B — Define the tool surface (keep it small for MVP)

| Tool name             | Description                                  | Key parameters                          |
| --------------------- | -------------------------------------------- | --------------------------------------- |
| `list_projects`       | List all accessible projects                 | —                                       |
| `search_issues`       | Search issues with filters                   | `project`, `status`, `assigned_to`, `tracker`, `limit` |
| `get_issue`           | Get full details of a single issue           | `issue_id`                              |
| `get_my_issues`       | Get issues assigned to the current user      | `status`                                |
| `list_time_entries`   | List time entries for a project or issue     | `project`, `issue_id`, `from`, `to`     |

> **Principle:** start with read-only tools. No create/update/delete in the MVP. This eliminates an entire category of risk.

### 2C — Implement the MCP server

- [ ] **2C.1** Set up the project:
  ```bash
  mkdir redmine-agent && cd redmine-agent
  python -m venv .venv && source .venv/bin/activate
  pip install mcp httpx rich
  ```

- [ ] **2C.2** Create `redmine_mcp_server.py`:
  - Use the `mcp` Python SDK (`from mcp.server import Server`)
  - Register each tool with `@server.tool()` decorator
  - Each tool handler:
    1. Receives typed arguments
    2. Calls the Redmine REST API via `httpx`
    3. Parses the JSON response
    4. Returns a **condensed** plain-text summary (not raw JSON — saves tokens for the LLM)
  - Configuration via environment variables: `REDMINE_URL`, `REDMINE_API_KEY`

- [ ] **2C.3** Implement response condensing.
  The LLM has limited context. Don't dump raw Redmine JSON — transform it into concise text:
  ```
  # Instead of full JSON, return:
  Issue #1234 — [Bug] Login page broken
    Project: backend | Status: Open | Priority: High
    Assigned to: Marco | Updated: 2026-03-15
    Description: Users cannot log in after the OAuth migration...
  ```

- [ ] **2C.4** Test the MCP server standalone:
  ```bash
  # Quick smoke test — run server and send a tool list request
  python -c "
  import asyncio
  from mcp.client.stdio import stdio_client, StdioServerParameters

  async def test():
      params = StdioServerParameters(command='python', args=['redmine_mcp_server.py'])
      async with stdio_client(params) as (read, write):
          from mcp.client.session import ClientSession
          async with ClientSession(read, write) as session:
              await session.initialize()
              tools = await session.list_tools()
              for t in tools.tools:
                  print(f'  {t.name}: {t.description}')

  asyncio.run(test())
  "
  ```

### Phase 2 deliverable
An MCP server with 5 read-only tools, tested end-to-end against your Redmine instance.

---

## Phase 3 — Agent Orchestrator

**Goal:** the core loop that connects the LLM to the MCP tools.

**Duration:** ~1.5 days

### Agent loop logic

```
1. User types a question
2. Build messages array: [system_prompt, ...history, user_message]
3. Send to Ollama with tool definitions
4. If response contains tool_calls:
     a. Validate tool name exists
     b. Validate arguments against schema
     c. Execute tool via MCP session
     d. Append tool result to messages
     e. Send back to Ollama (go to step 4)
   Else:
     Display the assistant's final text answer
5. Cap at MAX_TOOL_ROUNDS (e.g. 5) to prevent infinite loops
```

### Steps

- [ ] **3.1** Write the system prompt — this is the most important tuning surface:
  ```
  You are a Redmine assistant. You help users find information about
  projects, issues, and time tracking from their company's Redmine.

  Rules:
  - Use the available tools to answer questions. Do not guess.
  - If a query is ambiguous, ask the user to clarify.
  - When presenting issues, format them as a clear list.
  - Never fabricate issue numbers or project names.
  - If a tool returns an error, explain what went wrong.
  ```

- [ ] **3.2** Implement `agent.py` — the orchestrator:
  - Connect to Ollama via its OpenAI-compatible API (`/v1/chat/completions`)
  - Connect to the MCP server via stdio
  - Extract tool definitions from MCP (`session.list_tools()`) and convert them to OpenAI tool format
  - Implement the loop from the diagram above
  - Add JSON parsing with fallback: try `json.loads` first, then regex extraction of JSON blocks, then retry the LLM (max 2 retries)

- [ ] **3.3** Implement safety guards:
  - `MAX_TOOL_ROUNDS = 5` — hard cap on tool-calling iterations
  - `TIMEOUT_SECONDS = 120` — per LLM call timeout
  - Tool name validation — reject any tool call whose name isn't in the registered set
  - Argument type validation — basic check before forwarding to MCP

- [ ] **3.4** Add conversation history management:
  - Keep a rolling window of the last N messages (start with N=10)
  - When context grows too large (> 4000 tokens estimated), summarize older turns or drop them
  - Always keep the system prompt and the current turn

- [ ] **3.5** Test with representative queries:
  ```
  "What projects do we have?"
  "Show me all open bugs in the backend project"
  "What's issue #1234 about?"
  "What am I working on right now?"
  "How much time was logged on the API project last week?"
  ```

### Phase 3 deliverable
A working agent that takes a text query, reasons about which tools to call, calls them, and returns a natural-language answer. Runs from a simple Python script.

---

## Phase 4 — CLI Interface

**Goal:** wrap the agent in a polished terminal experience.

**Duration:** ~1 day

### Steps

- [ ] **4.1** Build the REPL loop using `rich`:
  - Prompt with `>` indicator
  - Show a spinner while the LLM is generating
  - Pretty-print issue lists as `rich.table.Table`
  - Syntax-highlight any code or structured data in responses

- [ ] **4.2** Add slash commands:
  | Command      | Action                                    |
  | ------------ | ----------------------------------------- |
  | `/help`      | Show available commands                   |
  | `/tools`     | List available MCP tools                  |
  | `/clear`     | Reset conversation history                |
  | `/model`     | Show current model, option to switch      |
  | `/debug`     | Toggle debug mode (show raw tool calls)   |
  | `/quit`      | Exit                                      |

- [ ] **4.3** Add debug mode:
  When enabled, print each tool call and its raw response before the LLM's final answer.
  This is essential for diagnosing when the model picks the wrong tool or misinterprets results.

- [ ] **4.4** Add configuration:
  Create a `config.yaml` or use environment variables:
  ```yaml
  redmine:
    url: "https://your-redmine.com"
    api_key: "${REDMINE_API_KEY}"  # from env

  llm:
    model: "qwen3:8b"
    temperature: 0.1        # low for tool-calling reliability
    ollama_url: "http://localhost:11434"

  agent:
    max_tool_rounds: 5
    max_history_messages: 10
  ```

- [ ] **4.5** Create an entry point:
  ```bash
  python -m redmine_agent
  # or
  python cli.py
  ```

### Phase 4 deliverable
A user-friendly CLI that non-technical team members could realistically use.

---

## Phase 5 — Testing, Tuning & Documentation

**Goal:** validate the MVP works for real use cases and document findings.

**Duration:** ~1 day

### Steps

- [ ] **5.1** Create a test suite of 15+ realistic queries:
  ```
  Category: Project discovery
    - "What projects are active?"
    - "Tell me about the mobile-app project"

  Category: Issue lookup
    - "Show open bugs in backend"
    - "What are the high priority issues?"
    - "Get me the details on issue #567"

  Category: Personal workflow
    - "What's assigned to me?"
    - "Do I have any overdue tasks?"

  Category: Time tracking
    - "How many hours were logged on project X this month?"

  Category: Ambiguous / edge cases
    - "What's the status?" (should ask for clarification)
    - "Delete all the issues" (should refuse — no write tools)
    - "Tell me a joke" (should politely redirect)
  ```

- [ ] **5.2** Run each query, log:
  - Whether the correct tool was selected
  - Whether the arguments were valid
  - Whether the final answer was accurate
  - Token count and response time
  - Any JSON parsing failures

- [ ] **5.3** Tune the system prompt based on failures:
  - If the model calls the wrong tool → add explicit routing hints to the system prompt
  - If it hallucinates issue numbers → strengthen the "never fabricate" instruction
  - If answers are too verbose → add "be concise" instruction

- [ ] **5.4** Benchmark performance:
  | Metric                   | Target          |
  | ------------------------ | --------------- |
  | Tool selection accuracy  | > 80%           |
  | JSON parse success rate  | > 90%           |
  | End-to-end response time | < 30s           |
  | RAM usage (peak)         | < 12GB          |

- [ ] **5.5** Write a `README.md` with:
  - Setup instructions (Ollama, model, Redmine config)
  - Usage examples
  - Known limitations
  - Findings: what works, what doesn't, where a bigger/cloud model would help

### Phase 5 deliverable
A validated MVP with documented success rates and a clear picture of what works and what needs improvement.

---

## Project Structure

```
redmine-agent/
├── README.md
├── config.yaml
├── requirements.txt
├── redmine_mcp_server.py     # MCP server wrapping Redmine REST API
├── agent.py                  # LLM orchestrator + tool loop
├── cli.py                    # REPL interface
├── redmine_client.py         # Thin HTTP wrapper for Redmine API
├── tool_schemas.py           # Tool definitions in OpenAI format
├── tests/
│   ├── test_redmine_client.py
│   ├── test_mcp_server.py
│   └── test_queries.py       # End-to-end query test suite
└── docs/
    └── findings.md           # Post-MVP evaluation notes
```

---

## Dependencies

```
# requirements.txt
mcp>=1.0.0
httpx>=0.27.0
rich>=13.0.0
pyyaml>=6.0
openai>=1.0.0       # for Ollama's OpenAI-compatible client
```

---

## Risk Mitigations

| Risk                                | Likelihood | Impact | Mitigation                                                                 |
| ----------------------------------- | ---------- | ------ | -------------------------------------------------------------------------- |
| Qwen3-8B too slow on CPU           | Medium     | Medium | Fallback to Qwen3-4B, use non-thinking mode (`/no_think`)                |
| Model produces malformed tool calls | High       | Low    | JSON fallback parser, 2 retries, schema validation                        |
| Model hallucinates data             | Medium     | High   | Strong system prompt, never cache or re-use fabricated references          |
| Redmine API rate limiting           | Low        | Low    | Add basic retry with backoff in `redmine_client.py`                       |
| Context window overflow             | Medium     | Medium | Rolling history window, condensed tool responses, token counting          |
| Model picks wrong tool              | Medium     | Medium | Clear tool descriptions, few-shot examples in system prompt if needed     |

---

## Success Criteria

The MVP is considered successful if:

1. A user can ask natural-language questions about their Redmine and get accurate answers
2. Everything runs locally — no data sent to external services
3. End-to-end response time stays under 30 seconds for typical queries
4. Tool selection accuracy exceeds 80% on the test suite
5. The system runs stable for a full working session without crashing or OOMing