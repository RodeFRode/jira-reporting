# src/jira_reporting/parse.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class IssueRow:
    id: str
    key: str
    project: Optional[str]
    issuetype: Optional[str]
    status: Optional[str]
    status_category: Optional[str]
    summary: Optional[str]
    assignee: Optional[str]
    priority: Optional[str]
    labels: List[str]
    components: List[str]
    created: Optional[str]   # String belassen (kein dateutil nötig)
    updated: Optional[str]


@dataclass(frozen=True)
class ChangeItem:
    field: str
    from_string: Optional[str]
    to_string: Optional[str]
    created: Optional[str]
    author: Optional[str]


def _get(d: Dict[str, Any], path: str, default=None):
    """Kleine Helper-Funktion für geschachtelte Dicts mit 'a.b.c' Pfaden."""
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def parse_issue(raw: Dict[str, Any]) -> IssueRow:
    f = raw.get("fields", {}) or {}

    status_category = _get(f, "status.statusCategory.name")
    comp_names = [c.get("name") for c in (f.get("components") or []) if isinstance(c, dict)]
    labels = list(f.get("labels") or [])

    return IssueRow(
        id=str(raw.get("id") or ""),
        key=str(raw.get("key") or ""),
        project=_get(f, "project.key") or _get(f, "project.name"),
        issuetype=_get(f, "issuetype.name"),
        status=_get(f, "status.name"),
        status_category=status_category,
        summary=f.get("summary"),
        assignee=_get(f, "assignee.displayName") or _get(f, "assignee.name"),
        priority=_get(f, "priority.name"),
        labels=labels,
        components=[c for c in comp_names if c],
        created=f.get("created"),
        updated=f.get("updated"),
    )


def iter_changelog_items(raw: Dict[str, Any]) -> Iterable[ChangeItem]:
    """Flacht das Changelog auf Einträge pro Item herunter."""
    cl = (raw.get("changelog") or {}).get("histories") or []
    for hist in cl:
        created = hist.get("created")
        author = _get(hist, "author.displayName") or _get(hist, "author.name")
        for it in (hist.get("items") or []):
            yield ChangeItem(
                field=str(it.get("field") or ""),
                from_string=it.get("fromString"),
                to_string=it.get("toString"),
                created=created,
                author=author,
            )
