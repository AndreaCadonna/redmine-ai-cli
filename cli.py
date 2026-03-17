"""CLI interface — REPL for the Redmine agent."""

import asyncio
import os
import sys

import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from agent import Agent

console = Console()


def load_config(path: str = "config.yaml") -> dict:
    """Load configuration from YAML file with env var overrides."""
    config = {
        "redmine": {"url": "", "api_key": ""},
        "llm": {
            "model": "qwen3:8b",
            "temperature": 0.1,
            "ollama_url": "http://localhost:11434",
        },
        "agent": {
            "max_tool_rounds": 5,
            "max_history_messages": 10,
            "timeout_seconds": 120,
        },
    }

    # Load from YAML file if it exists
    if os.path.exists(path):
        with open(path) as f:
            file_config = yaml.safe_load(f) or {}
        for section in config:
            if section in file_config:
                config[section].update(file_config[section])

    # Environment variables override file config
    if os.environ.get("REDMINE_URL"):
        config["redmine"]["url"] = os.environ["REDMINE_URL"]
    if os.environ.get("REDMINE_API_KEY"):
        config["redmine"]["api_key"] = os.environ["REDMINE_API_KEY"]
    if os.environ.get("OLLAMA_URL"):
        config["llm"]["ollama_url"] = os.environ["OLLAMA_URL"]
    if os.environ.get("LLM_MODEL"):
        config["llm"]["model"] = os.environ["LLM_MODEL"]

    return config


def print_banner():
    """Print the startup banner."""
    banner = Text()
    banner.append("Redmine CLI Agent", style="bold cyan")
    banner.append("\nLocal LLM-powered Redmine assistant")
    console.print(Panel(banner, border_style="cyan"))
    console.print(
        "Type your question, or use /help for commands. /quit to exit.\n",
        style="dim",
    )


def print_help():
    """Print available slash commands."""
    commands = [
        ("/help", "Show this help message"),
        ("/tools", "List available Redmine tools"),
        ("/clear", "Reset conversation history"),
        ("/model", "Show current model info"),
        ("/debug", "Toggle debug mode (show raw tool calls)"),
        ("/quit", "Exit the application"),
    ]
    console.print("\n[bold]Available commands:[/bold]")
    for cmd, desc in commands:
        console.print(f"  [cyan]{cmd:<10}[/cyan] {desc}")
    console.print()


async def run_repl():
    """Main REPL loop."""
    config = load_config()

    # Validate required config
    redmine_url = config["redmine"]["url"]
    redmine_api_key = config["redmine"].get("api_key", "")
    if not redmine_url:
        console.print(
            "[red]Error:[/red] REDMINE_URL not configured. "
            "Set it in config.yaml or as an environment variable."
        )
        sys.exit(1)
    if not redmine_api_key:
        console.print(
            "[red]Error:[/red] REDMINE_API_KEY not configured. "
            "Set the REDMINE_API_KEY environment variable."
        )
        sys.exit(1)

    # Set env vars for the MCP server subprocess
    os.environ["REDMINE_URL"] = redmine_url
    os.environ["REDMINE_API_KEY"] = redmine_api_key

    # Create the agent
    llm_config = config["llm"]
    agent_config = config["agent"]
    agent = Agent(
        ollama_url=llm_config["ollama_url"],
        model=llm_config["model"],
        temperature=llm_config["temperature"],
        max_tool_rounds=agent_config["max_tool_rounds"],
        max_history_messages=agent_config["max_history_messages"],
        timeout_seconds=agent_config["timeout_seconds"],
    )

    # Connect to MCP server
    print_banner()
    console.print("Connecting to MCP server...", style="dim")
    try:
        await agent.connect_mcp()
        console.print("Connected.\n", style="dim green")
    except Exception as e:
        console.print(f"[red]Failed to connect to MCP server:[/red] {e}")
        sys.exit(1)

    console.print(
        f"Model: [cyan]{llm_config['model']}[/cyan] @ {llm_config['ollama_url']}",
        style="dim",
    )
    console.print(
        f"Redmine: [cyan]{redmine_url}[/cyan]\n",
        style="dim",
    )

    try:
        while True:
            try:
                user_input = console.input("[bold green]> [/bold green]").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\nGoodbye!", style="dim")
                break

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                cmd = user_input.lower().split()[0]

                if cmd == "/quit" or cmd == "/exit":
                    console.print("Goodbye!", style="dim")
                    break

                elif cmd == "/help":
                    print_help()
                    continue

                elif cmd == "/tools":
                    from tool_schemas import TOOLS
                    console.print("\n[bold]Available tools:[/bold]")
                    for t in TOOLS:
                        fn = t["function"]
                        console.print(f"  [cyan]{fn['name']:<20}[/cyan] {fn['description']}")
                    console.print()
                    continue

                elif cmd == "/clear":
                    agent.clear_history()
                    console.print("Conversation history cleared.\n", style="dim")
                    continue

                elif cmd == "/model":
                    console.print(f"\nModel: [cyan]{agent.model}[/cyan]")
                    console.print(f"Temperature: {agent.temperature}")
                    console.print(f"Max tool rounds: {agent.max_tool_rounds}")
                    console.print(f"History window: {agent.max_history_messages} messages\n")
                    continue

                elif cmd == "/debug":
                    agent.debug = not agent.debug
                    state = "ON" if agent.debug else "OFF"
                    console.print(f"Debug mode: [cyan]{state}[/cyan]\n")
                    continue

                else:
                    console.print(f"Unknown command: {cmd}. Type /help for options.\n", style="yellow")
                    continue

            # Send to agent
            with console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots"):
                answer = await agent.chat(user_input)

            # Print debug info if enabled
            if agent.debug:
                debug_log = agent.get_debug_log()
                if debug_log:
                    console.print(Panel(
                        "\n".join(debug_log),
                        title="Debug",
                        border_style="yellow",
                    ))

            # Print the answer
            console.print()
            try:
                console.print(Markdown(answer))
            except Exception:
                console.print(answer)
            console.print()

    finally:
        await agent.disconnect_mcp()


def main():
    """Entry point."""
    asyncio.run(run_repl())


if __name__ == "__main__":
    main()
