"""Tests for the Redmine HTTP client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from redmine_client import RedmineClient


@pytest.fixture
def client():
    return RedmineClient(url="https://redmine.example.com", api_key="test-key")


class TestRedmineClient:
    def test_init(self, client):
        assert client.base_url == "https://redmine.example.com"
        assert client.headers["X-Redmine-API-Key"] == "test-key"

    def test_base_url_strips_trailing_slash(self):
        c = RedmineClient(url="https://redmine.example.com/", api_key="key")
        assert c.base_url == "https://redmine.example.com"

    @patch.object(RedmineClient, "_get")
    def test_list_projects(self, mock_get, client):
        mock_get.return_value = {
            "projects": [
                {"id": 1, "name": "Backend", "identifier": "backend"},
                {"id": 2, "name": "Frontend", "identifier": "frontend"},
            ],
            "total_count": 2,
        }
        projects = client.list_projects()
        assert len(projects) == 2
        assert projects[0]["name"] == "Backend"
        mock_get.assert_called_once()

    @patch.object(RedmineClient, "_get")
    def test_search_issues_with_filters(self, mock_get, client):
        mock_get.return_value = {
            "issues": [
                {"id": 100, "subject": "Fix login bug"},
            ],
        }
        issues = client.search_issues(project="backend", status="open", limit=10)
        assert len(issues) == 1
        assert issues[0]["subject"] == "Fix login bug"
        call_params = mock_get.call_args[1]["params"]
        assert call_params["project_id"] == "backend"
        assert call_params["status_id"] == "open"
        assert call_params["limit"] == 10

    @patch.object(RedmineClient, "_get")
    def test_search_issues_no_filters(self, mock_get, client):
        mock_get.return_value = {"issues": []}
        issues = client.search_issues()
        assert issues == []

    @patch.object(RedmineClient, "_get")
    def test_get_issue(self, mock_get, client):
        mock_get.return_value = {
            "issue": {
                "id": 1234,
                "subject": "Test issue",
                "description": "A test issue description",
            },
        }
        issue = client.get_issue(1234)
        assert issue["id"] == 1234
        assert issue["subject"] == "Test issue"

    @patch.object(RedmineClient, "_get")
    def test_get_my_issues(self, mock_get, client):
        mock_get.return_value = {
            "issues": [
                {"id": 10, "subject": "My task"},
            ],
        }
        issues = client.get_my_issues(status="open")
        assert len(issues) == 1
        call_params = mock_get.call_args[1]["params"]
        assert call_params["assigned_to_id"] == "me"

    @patch.object(RedmineClient, "_get")
    def test_list_time_entries(self, mock_get, client):
        mock_get.return_value = {
            "time_entries": [
                {"id": 1, "hours": 2.5, "spent_on": "2026-03-15"},
                {"id": 2, "hours": 3.0, "spent_on": "2026-03-16"},
            ],
        }
        entries = client.list_time_entries(
            project="backend", from_date="2026-03-01", to_date="2026-03-31"
        )
        assert len(entries) == 2
        call_params = mock_get.call_args[1]["params"]
        assert call_params["project_id"] == "backend"
        assert call_params["from"] == "2026-03-01"
        assert call_params["to"] == "2026-03-31"

    @patch.object(RedmineClient, "_get")
    def test_list_time_entries_by_issue(self, mock_get, client):
        mock_get.return_value = {"time_entries": []}
        client.list_time_entries(issue_id=567)
        call_params = mock_get.call_args[1]["params"]
        assert call_params["issue_id"] == 567

    @patch.object(RedmineClient, "_get")
    def test_search_issues_status_closed(self, mock_get, client):
        mock_get.return_value = {"issues": []}
        client.search_issues(status="closed")
        call_params = mock_get.call_args[1]["params"]
        assert call_params["status_id"] == "closed"

    @patch.object(RedmineClient, "_get")
    def test_search_issues_status_all(self, mock_get, client):
        mock_get.return_value = {"issues": []}
        client.search_issues(status="all")
        call_params = mock_get.call_args[1]["params"]
        assert call_params["status_id"] == "*"
