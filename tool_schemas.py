"""Tool definitions in OpenAI function-calling format.

Used by the agent to tell the LLM what tools are available.
These mirror the MCP server tools but are formatted for the OpenAI API.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "List all accessible Redmine projects.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_issues",
            "description": (
                "Search Redmine issues with filters. "
                "Use this to find issues by project, status, assignee, or tracker."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project identifier (e.g. 'backend', 'mobile-app')",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter by status (default: open)",
                    },
                    "assigned_to": {
                        "type": "string",
                        "description": "Filter by assignee username or 'me'",
                    },
                    "tracker": {
                        "type": "string",
                        "description": "Filter by tracker (e.g. 'Bug', 'Feature', 'Task')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 25, max 100)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_issue",
            "description": "Get full details of a single Redmine issue by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_id": {
                        "type": "integer",
                        "description": "The numeric issue ID (e.g. 1234)",
                    },
                },
                "required": ["issue_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_issues",
            "description": (
                "Get issues assigned to the current user. "
                "Use this when the user asks about their own tasks or assignments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter by status (default: open)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_time_entries",
            "description": (
                "List time entries for a project or issue. "
                "Use this for time tracking queries like hours logged."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project identifier to filter by",
                    },
                    "issue_id": {
                        "type": "integer",
                        "description": "Issue ID to filter by",
                    },
                    "from_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format",
                    },
                    "to_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 50)",
                    },
                },
                "required": [],
            },
        },
    },
]

TOOL_NAMES = {t["function"]["name"] for t in TOOLS}
