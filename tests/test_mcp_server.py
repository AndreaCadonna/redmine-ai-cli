"""Tests for the Redmine MCP server response condensers."""

import pytest

from redmine_mcp_server import (
    _condense_project,
    _condense_issue,
    _condense_time_entry,
)


class TestCondenseProject:
    def test_basic_project(self):
        project = {
            "name": "Backend",
            "identifier": "backend",
            "description": "Backend services",
            "status": 1,
            "created_on": "2026-01-15T10:00:00Z",
        }
        result = _condense_project(project)
        assert "Backend" in result
        assert "backend" in result
        assert "active" in result
        assert "2026-01-15" in result

    def test_closed_project(self):
        project = {"name": "Old Project", "identifier": "old", "status": 5}
        result = _condense_project(project)
        assert "closed" in result

    def test_minimal_project(self):
        project = {"name": "Test", "identifier": "test"}
        result = _condense_project(project)
        assert "Test" in result


class TestCondenseIssue:
    def test_basic_issue(self):
        issue = {
            "id": 1234,
            "subject": "Fix login bug",
            "tracker": {"name": "Bug"},
            "project": {"name": "Backend"},
            "status": {"name": "Open"},
            "priority": {"name": "High"},
            "assigned_to": {"name": "Marco"},
            "updated_on": "2026-03-15T14:00:00Z",
        }
        result = _condense_issue(issue)
        assert "#1234" in result
        assert "Bug" in result
        assert "Fix login bug" in result
        assert "Backend" in result
        assert "Open" in result
        assert "High" in result
        assert "Marco" in result

    def test_unassigned_issue(self):
        issue = {
            "id": 100,
            "subject": "Test",
            "tracker": {"name": "Task"},
            "project": {"name": "Test"},
            "status": {"name": "New"},
            "priority": {"name": "Normal"},
            "updated_on": "2026-03-10T10:00:00Z",
        }
        result = _condense_issue(issue)
        assert "unassigned" in result

    def test_verbose_issue(self):
        issue = {
            "id": 567,
            "subject": "Add feature",
            "tracker": {"name": "Feature"},
            "project": {"name": "Frontend"},
            "status": {"name": "In Progress"},
            "priority": {"name": "Normal"},
            "assigned_to": {"name": "Alice"},
            "updated_on": "2026-03-12T08:00:00Z",
            "description": "We need to add a new dashboard widget.",
            "start_date": "2026-03-10",
            "due_date": "2026-03-20",
            "done_ratio": 40,
            "estimated_hours": 16.0,
            "spent_hours": 6.5,
        }
        result = _condense_issue(issue, verbose=True)
        assert "dashboard widget" in result
        assert "2026-03-10" in result
        assert "2026-03-20" in result
        assert "40%" in result
        assert "16.0h" in result
        assert "6.5h" in result


class TestCondenseTimeEntry:
    def test_basic_time_entry(self):
        entry = {
            "user": {"name": "Marco"},
            "hours": 3.5,
            "activity": {"name": "Development"},
            "spent_on": "2026-03-15",
            "project": {"name": "Backend"},
            "issue": {"id": 1234},
            "comments": "Worked on login fix",
        }
        result = _condense_time_entry(entry)
        assert "Marco" in result
        assert "3.5h" in result
        assert "Development" in result
        assert "2026-03-15" in result
        assert "#1234" in result
        assert "login fix" in result

    def test_time_entry_no_issue(self):
        entry = {
            "user": {"name": "Alice"},
            "hours": 1.0,
            "activity": {"name": "Meeting"},
            "spent_on": "2026-03-16",
            "project": {"name": "General"},
            "comments": "",
        }
        result = _condense_time_entry(entry)
        assert "Alice" in result
        assert "#" not in result  # no issue reference
