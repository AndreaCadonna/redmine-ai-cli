"""End-to-end query test suite.

These test cases document the expected behavior of the agent
for various user queries. They serve as a manual test checklist
and can be extended with automated tests when the full stack is running.
"""

# Test queries organized by category, as specified in the dev plan.
# Each entry: (query, expected_tool, description)

TEST_QUERIES = [
    # --- Category: Project discovery ---
    (
        "What projects are active?",
        "list_projects",
        "Should list all accessible projects",
    ),
    (
        "Tell me about the mobile-app project",
        "search_issues",
        "Should search for the mobile-app project or list its issues",
    ),
    (
        "What projects do we have?",
        "list_projects",
        "Should list all projects",
    ),
    # --- Category: Issue lookup ---
    (
        "Show open bugs in backend",
        "search_issues",
        "Should search with project=backend, tracker=Bug, status=open",
    ),
    (
        "What are the high priority issues?",
        "search_issues",
        "Should search for high priority issues",
    ),
    (
        "Get me the details on issue #567",
        "get_issue",
        "Should fetch issue 567 with full details",
    ),
    (
        "What's issue #1234 about?",
        "get_issue",
        "Should fetch issue 1234",
    ),
    (
        "Show me all open bugs in the backend project",
        "search_issues",
        "Should search with project=backend, status=open, tracker=Bug",
    ),
    # --- Category: Personal workflow ---
    (
        "What's assigned to me?",
        "get_my_issues",
        "Should use get_my_issues with default status",
    ),
    (
        "Do I have any overdue tasks?",
        "get_my_issues",
        "Should use get_my_issues and check due dates",
    ),
    (
        "What am I working on right now?",
        "get_my_issues",
        "Should use get_my_issues with status=open",
    ),
    # --- Category: Time tracking ---
    (
        "How many hours were logged on project X this month?",
        "list_time_entries",
        "Should use list_time_entries with project and date range",
    ),
    (
        "How much time was logged on the API project last week?",
        "list_time_entries",
        "Should use list_time_entries with date range",
    ),
    # --- Category: Ambiguous / edge cases ---
    (
        "What's the status?",
        None,
        "Should ask for clarification — ambiguous query",
    ),
    (
        "Delete all the issues",
        None,
        "Should refuse — no write tools available",
    ),
    (
        "Tell me a joke",
        None,
        "Should politely redirect — out of scope",
    ),
]


def test_query_catalog_is_complete():
    """Verify we have at least 15 test queries as required by the dev plan."""
    assert len(TEST_QUERIES) >= 15


def test_all_tools_covered():
    """Verify all tools appear in at least one test case."""
    expected_tools = {"list_projects", "search_issues", "get_issue", "get_my_issues", "list_time_entries"}
    covered = {q[1] for q in TEST_QUERIES if q[1] is not None}
    assert expected_tools == covered, f"Missing tools: {expected_tools - covered}"
