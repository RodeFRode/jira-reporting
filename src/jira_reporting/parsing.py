from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class IssueLite:
    key: str
    summary: str
    status: str
    assignee: str
    updated: str
    created: Optional[str]
    issue_type: Optional[str]
    project_key: Optional[str]
    changelog_count: Optional[int]

def _get(d: Dict[str, Any], *path: str, default=None):
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur

def parse_issue(issue: Dict[str, Any]) -> IssueLite:
    fields = issue.get("fields", {}) or {}
    key = issue.get("key") or ""
    summary = fields.get("summary") or ""
    status = _get(fields, "status", "name", default="")
    assignee = _get(fields, "assignee", "displayName", default=_get(fields, "assignee", "name", default="-")) or "-"
    updated = fields.get("updated") or ""
    created = fields.get("created")
    issue_type = _get(fields, "issuetype", "name")
    project_key = _get(fields, "project", "key")
    # changelog only if expand=changelog
    changelog = issue.get("changelog") or {}
    changelog_count = changelog.get("total")
    return IssueLite(
        key=key,
        summary=summary,
        status=status,
        assignee=assignee,
        updated=updated,
        created=created,
        issue_type=issue_type,
        project_key=project_key,
        changelog_count=changelog_count,
    )
