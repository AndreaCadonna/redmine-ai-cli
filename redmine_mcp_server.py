"""Redmine MCP Server — exposes Redmine operations as MCP tools over stdio."""

import os
import sys

from mcp.server.fastmcp import FastMCP
from redmine_client import RedmineClient

# --- Response condensers ---

def _condense_project(p: dict) -> str:
    """Condense a Redmine project into a short text summary."""
    lines = [f"Project: {p.get('name', '?')} (id: {p.get('identifier', '?')})"]
    if p.get("description"):
        desc = p["description"][:200]
        lines.append(f"  Description: {desc}")
    if p.get("status") is not None:
        status_map = {1: "active", 5: "closed", 9: "archived"}
        lines.append(f"  Status: {status_map.get(p['status'], str(p['status']))}")
    if p.get("created_on"):
        lines.append(f"  Created: {p['created_on'][:10]}")
    return "\n".join(lines)


def _condense_issue(issue: dict, verbose: bool = False) -> str:
    """Condense a Redmine issue into a short text summary."""
    tracker = issue.get("tracker", {}).get("name", "?")
    subject = issue.get("subject", "?")
    header = f"Issue #{issue.get('id', '?')} — [{tracker}] {subject}"

    project = issue.get("project", {}).get("name", "?")
    status = issue.get("status", {}).get("name", "?")
    priority = issue.get("priority", {}).get("name", "?")
    assigned = issue.get("assigned_to", {}).get("name", "unassigned")
    updated = issue.get("updated_on", "?")[:10] if issue.get("updated_on") else "?"

    lines = [
        header,
        f"  Project: {project} | Status: {status} | Priority: {priority}",
        f"  Assigned to: {assigned} | Updated: {updated}",
    ]

    if verbose:
        if issue.get("description"):
            desc = issue["description"][:500]
            lines.append(f"  Description: {desc}")
        if issue.get("start_date"):
            lines.append(f"  Start date: {issue['start_date']}")
        if issue.get("due_date"):
            lines.append(f"  Due date: {issue['due_date']}")
        if issue.get("done_ratio") is not None:
            lines.append(f"  Progress: {issue['done_ratio']}%")
        if issue.get("estimated_hours"):
            lines.append(f"  Estimated: {issue['estimated_hours']}h")
        if issue.get("spent_hours"):
            lines.append(f"  Spent: {issue['spent_hours']}h")

    return "\n".join(lines)


def _condense_time_entry(entry: dict) -> str:
    """Condense a time entry into a short text summary."""
    user = entry.get("user", {}).get("name", "?")
    hours = entry.get("hours", 0)
    activity = entry.get("activity", {}).get("name", "?")
    date = entry.get("spent_on", "?")
    issue_id = entry.get("issue", {}).get("id")
    project = entry.get("project", {}).get("name", "?")
    comment = entry.get("comments", "")

    line = f"{date} | {user} | {hours}h | {activity} | Project: {project}"
    if issue_id:
        line += f" | Issue #{issue_id}"
    if comment:
        line += f" | {comment[:100]}"
    return line


# --- MCP Server ---

mcp = FastMCP("Redmine")

_client: RedmineClient | None = None


def _get_client() -> RedmineClient:
    """Lazy-init the Redmine client from environment variables."""
    global _client
    if _client is None:
        url = os.environ.get("REDMINE_URL", "")
        api_key = os.environ.get("REDMINE_API_KEY", "")
        if not url or not api_key:
            raise RuntimeError(
                "REDMINE_URL and REDMINE_API_KEY environment variables must be set"
            )
        _client = RedmineClient(url, api_key)
    return _client


@mcp.tool()
def list_projects() -> str:
    """List all accessible Redmine projects."""
    client = _get_client()
    projects = client.list_projects()
    if not projects:
        return "No projects found."
    lines = [f"Found {len(projects)} project(s):\n"]
    for p in projects:
        lines.append(_condense_project(p))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def search_issues(
    project: str | None = None,
    status: str | None = None,
    assigned_to: str | None = None,
    tracker: str | None = None,
    limit: int = 25,
) -> str:
    """Search Redmine issues with filters.

    Args:
        project: Project identifier (e.g. 'backend', 'mobile-app')
        status: Filter by status — 'open', 'closed', or 'all' (default: open)
        assigned_to: Filter by assignee username or 'me'
        tracker: Filter by tracker name (e.g. 'Bug', 'Feature', 'Task')
        limit: Maximum number of results (default 25, max 100)
    """
    client = _get_client()
    issues = client.search_issues(
        project=project,
        status=status,
        assigned_to=assigned_to,
        tracker=tracker,
        limit=min(limit, 100),
    )
    if not issues:
        return "No issues found matching the given filters."
    lines = [f"Found {len(issues)} issue(s):\n"]
    for issue in issues:
        lines.append(_condense_issue(issue))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_issue(issue_id: int) -> str:
    """Get full details of a single Redmine issue.

    Args:
        issue_id: The numeric issue ID (e.g. 1234)
    """
    client = _get_client()
    issue = client.get_issue(issue_id)
    if not issue:
        return f"Issue #{issue_id} not found."
    return _condense_issue(issue, verbose=True)


@mcp.tool()
def get_my_issues(status: str | None = None) -> str:
    """Get issues assigned to the current user (the API key owner).

    Args:
        status: Filter by status — 'open', 'closed', or 'all' (default: open)
    """
    client = _get_client()
    issues = client.get_my_issues(status=status)
    if not issues:
        return "No issues assigned to you."
    lines = [f"You have {len(issues)} issue(s) assigned:\n"]
    for issue in issues:
        lines.append(_condense_issue(issue))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def list_time_entries(
    project: str | None = None,
    issue_id: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 50,
) -> str:
    """List time entries for a project or issue.

    Args:
        project: Project identifier to filter by
        issue_id: Issue ID to filter by
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        limit: Maximum number of results (default 50)
    """
    client = _get_client()
    entries = client.list_time_entries(
        project=project,
        issue_id=issue_id,
        from_date=from_date,
        to_date=to_date,
        limit=min(limit, 100),
    )
    if not entries:
        return "No time entries found."

    total_hours = sum(e.get("hours", 0) for e in entries)
    lines = [f"Found {len(entries)} time entry/entries (total: {total_hours:.1f}h):\n"]
    for entry in entries:
        lines.append(_condense_time_entry(entry))
    return "\n".join(lines)


def main():
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
