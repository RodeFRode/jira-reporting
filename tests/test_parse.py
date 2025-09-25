# tests/test_parse.py
from jira_reporting.parse import parse_issue, iter_changelog_items

def test_parse_issue_minimal():
    raw = {
        "id": "10001",
        "key": "ABC-1",
        "fields": {
            "summary": "Hello",
            "assignee": {"displayName": "User One"},
            "status": {"name": "To Do", "statusCategory": {"name": "To Do"}},
            "issuetype": {"name": "Bug"},
            "priority": {"name": "High"},
            "labels": ["l1", "l2"],
            "components": [{"name": "CompA"}],
            "project": {"key": "ABC"},
            "created": "2024-09-01T10:00:00.000+0000",
            "updated": "2024-09-02T12:00:00.000+0000",
        }
    }
    row = parse_issue(raw)
    assert row.key == "ABC-1"
    assert row.assignee == "User One"
    assert row.status == "To Do"
    assert row.components == ["CompA"]
    assert row.labels == ["l1", "l2"]
    assert row.updated.startswith("2024-09-02")

def test_iter_changelog_items_flatten():
    raw = {
        "changelog": {
            "histories": [
                {
                    "created": "2024-09-02T12:00:00.000+0000",
                    "author": {"displayName": "User One"},
                    "items": [
                        {"field": "status", "fromString": "To Do", "toString": "In Progress"}
                    ]
                }
            ]
        }
    }
    items = list(iter_changelog_items(raw))
    assert len(items) == 1
    it = items[0]
    assert it.field == "status"
    assert it.from_string == "To Do"
    assert it.to_string == "In Progress"
    assert it.author == "User One"
