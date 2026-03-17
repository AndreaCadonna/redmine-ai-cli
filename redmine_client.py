"""Thin HTTP wrapper for the Redmine REST API."""

import httpx
import time
from typing import Any


class RedmineClient:
    """HTTP client for Redmine REST API with retry support."""

    MAX_RETRIES = 3
    BACKOFF_BASE = 1.0  # seconds

    def __init__(self, url: str, api_key: str, timeout: float = 30.0):
        self.base_url = url.rstrip("/")
        self.headers = {
            "X-Redmine-API-Key": api_key,
            "Content-Type": "application/json",
        }
        self.client = httpx.Client(timeout=timeout, headers=self.headers)

    def _request(self, method: str, path: str, params: dict | None = None) -> dict:
        """Make an HTTP request with retry and backoff."""
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.request(method, url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    wait = self.BACKOFF_BASE * (2 ** attempt)
                    time.sleep(wait)

        raise last_error

    def _get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def list_projects(self) -> list[dict[str, Any]]:
        """List all accessible projects."""
        projects = []
        offset = 0
        limit = 100

        while True:
            data = self._get("/projects.json", params={"offset": offset, "limit": limit})
            projects.extend(data.get("projects", []))
            total = data.get("total_count", 0)
            offset += limit
            if offset >= total:
                break

        return projects

    def search_issues(
        self,
        project: str | None = None,
        status: str | None = None,
        assigned_to: str | None = None,
        tracker: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Search issues with filters."""
        params: dict[str, Any] = {"limit": limit, "sort": "updated_on:desc"}

        if project:
            params["project_id"] = project
        if status:
            if status == "open":
                params["status_id"] = "open"
            elif status == "closed":
                params["status_id"] = "closed"
            elif status == "all":
                params["status_id"] = "*"
            else:
                params["status_id"] = status
        if assigned_to:
            params["assigned_to_id"] = assigned_to
        if tracker:
            params["tracker_id"] = tracker

        data = self._get("/issues.json", params=params)
        return data.get("issues", [])

    def get_issue(self, issue_id: int) -> dict[str, Any]:
        """Get full details of a single issue."""
        data = self._get(
            f"/issues/{issue_id}.json",
            params={"include": "journals,attachments,relations"},
        )
        return data.get("issue", {})

    def get_my_issues(self, status: str | None = None) -> list[dict[str, Any]]:
        """Get issues assigned to the current user."""
        params: dict[str, Any] = {
            "assigned_to_id": "me",
            "limit": 50,
            "sort": "priority:desc,updated_on:desc",
        }
        if status:
            if status in ("open", "closed"):
                params["status_id"] = status
            elif status == "all":
                params["status_id"] = "*"
            else:
                params["status_id"] = status

        data = self._get("/issues.json", params=params)
        return data.get("issues", [])

    def list_time_entries(
        self,
        project: str | None = None,
        issue_id: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List time entries for a project or issue."""
        params: dict[str, Any] = {"limit": limit}

        if project:
            params["project_id"] = project
        if issue_id:
            params["issue_id"] = issue_id
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        data = self._get("/time_entries.json", params=params)
        return data.get("time_entries", [])

    def close(self):
        """Close the HTTP client."""
        self.client.close()
