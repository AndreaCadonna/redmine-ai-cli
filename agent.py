"""Agent orchestrator — connects the LLM to Redmine MCP tools."""

import asyncio
import json
import os
import re
import sys
from typing import Any

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from openai import OpenAI

from tool_schemas import TOOLS, TOOL_NAMES

SYSTEM_PROMPT = """\
You are a Redmine assistant. You help users find information about \
projects, issues, and time tracking from their company's Redmine instance.

Rules:
- Use the available tools to answer questions. Do not guess or make up data.
- If a query is ambiguous, ask the user to clarify.
- When presenting issues, format them as a clear, readable list.
- Never fabricate issue numbers, project names, or user names.
- If a tool returns an error, explain what went wrong clearly.
- Be concise in your answers.
- When the user asks about "my issues" or "assigned to me", use get_my_issues.
- When the user asks about time/hours logged, use list_time_entries.
- When the user asks about a specific issue number, use get_issue.
- When the user wants to search or filter issues, use search_issues.
- When the user asks about projects, use list_projects.\
"""


class Agent:
    """Orchestrates LLM calls and MCP tool execution."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen3:8b",
        temperature: float = 0.1,
        max_tool_rounds: int = 5,
        max_history_messages: int = 10,
        timeout_seconds: int = 120,
        debug: bool = False,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tool_rounds = max_tool_rounds
        self.max_history_messages = max_history_messages
        self.timeout_seconds = timeout_seconds
        self.debug = debug

        self.llm = OpenAI(base_url=f"{ollama_url}/v1", api_key="ollama")
        self.history: list[dict[str, Any]] = []
        self._mcp_session: ClientSession | None = None
        self._mcp_context = None
        self._debug_log: list[str] = []

    async def connect_mcp(self, server_script: str = "redmine_mcp_server.py"):
        """Start the MCP server subprocess and connect via stdio."""
        params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env=dict(os.environ),
        )
        # Store the context managers so they stay open
        self._stdio_ctx = stdio_client(params)
        read, write = await self._stdio_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self._mcp_session = await self._session_ctx.__aenter__()
        await self._mcp_session.initialize()

    async def disconnect_mcp(self):
        """Clean up MCP connections."""
        if self._session_ctx:
            await self._session_ctx.__aexit__(None, None, None)
        if self._stdio_ctx:
            await self._stdio_ctx.__aexit__(None, None, None)
        self._mcp_session = None

    def clear_history(self):
        """Reset conversation history."""
        self.history.clear()

    def _trim_history(self):
        """Keep only the most recent messages to fit context."""
        if len(self.history) > self.max_history_messages:
            self.history = self.history[-self.max_history_messages:]

    def _build_messages(self, user_message: str) -> list[dict[str, Any]]:
        """Build the full messages array for the LLM call."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})
        return messages

    async def _call_tool(self, name: str, arguments: dict) -> str:
        """Execute a tool via the MCP session."""
        if not self._mcp_session:
            return "Error: MCP server not connected."

        if name not in TOOL_NAMES:
            return f"Error: Unknown tool '{name}'."

        try:
            result = await self._mcp_session.call_tool(name, arguments)
            # MCP returns content as a list of content blocks
            text_parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
            return "\n".join(text_parts) if text_parts else "No output from tool."
        except Exception as e:
            return f"Error calling tool '{name}': {e}"

    def _parse_tool_calls(self, message) -> list[dict[str, Any]] | None:
        """Extract tool calls from the LLM response message."""
        # Standard OpenAI format
        if hasattr(message, "tool_calls") and message.tool_calls:
            calls = []
            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    args = self._parse_json(args)
                calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args if args is not None else {},
                })
            return calls
        return None

    def _parse_json(self, text: str) -> dict | None:
        """Parse JSON with fallback regex extraction."""
        # Try direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try extracting JSON block from markdown
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding any JSON object
        match = re.search(r"\{[^{}]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    async def chat(self, user_message: str) -> str:
        """Process a user message and return the agent's response.

        Returns the final text answer and populates self._debug_log
        with tool call details when debug mode is on.
        """
        self._debug_log = []
        messages = self._build_messages(user_message)

        for round_num in range(self.max_tool_rounds + 1):
            try:
                response = self.llm.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS,
                    temperature=self.temperature,
                    timeout=self.timeout_seconds,
                )
            except Exception as e:
                return f"Error communicating with LLM: {e}"

            assistant_msg = response.choices[0].message
            tool_calls = self._parse_tool_calls(assistant_msg)

            if not tool_calls:
                # No tool calls — this is the final answer
                answer = assistant_msg.content or ""
                # Strip thinking tags if present (Qwen3 /think mode)
                answer = re.sub(
                    r"<think>.*?</think>\s*", "", answer, flags=re.DOTALL
                ).strip()
                # Update history
                self.history.append({"role": "user", "content": user_message})
                self.history.append({"role": "assistant", "content": answer})
                self._trim_history()
                return answer

            # Process tool calls
            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in tool_calls
                ],
            })

            for tc in tool_calls:
                if self.debug:
                    self._debug_log.append(
                        f"[Tool Call] {tc['name']}({json.dumps(tc['arguments'])})"
                    )

                # Validate tool name
                if tc["name"] not in TOOL_NAMES:
                    result = f"Error: Unknown tool '{tc['name']}'. Available: {', '.join(TOOL_NAMES)}"
                else:
                    result = await self._call_tool(tc["name"], tc["arguments"])

                if self.debug:
                    preview = result[:500] + "..." if len(result) > 500 else result
                    self._debug_log.append(f"[Tool Result] {preview}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

        # Exceeded max rounds
        return (
            "I've reached the maximum number of tool calls for this query. "
            "Here's what I found so far based on the tool results above."
        )

    def get_debug_log(self) -> list[str]:
        """Return debug log entries from the last chat() call."""
        return self._debug_log
