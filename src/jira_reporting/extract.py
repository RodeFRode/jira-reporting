# src/jira_reporting/extract.py
from __future__ import annotations

import json
import logging
from typing import Dict, Iterable, List, Optional

from .config import Settings
from .jira_api import JiraClient

log = logging.getLogger(__name__)

# Minimale, performante Felder (kannst du jederzeit erweitern)
DEFAULT_FIELDS = [
    "id",
    "key",
    "summary",
    "issuetype",
    "project",
    "priority",
    "status",
    "assignee",
    "reporter",
    "created",
    "updated",
    "resolutiondate",
    "parent",
]


def extract_issues(
    *,
    settings: Settings,
    jql: str,
    page_size: int = 100,
    fields: Optional[List[str]] = None,
    include_recent_changelog: bool = False,
    fetch_full_changelog: bool = False,
) -> Iterable[Dict]:
    """
    Führt zunächst /myself aus (Auth sanity check),
    dann streamt Issues gemäß JQL. Optional: vollständiger Changelog pro Issue.
    """
    client = JiraClient(settings)
    try:
        me = client.get_myself()
        log.info("Auth ok", extra={"account": me.get("name") or me.get("displayName")})
    except Exception:
        client.close()
        raise

    # Performance: nur bei Bedarf expand=changelog (liefert zuletzt ~100)
    expand = ["changelog"] if include_recent_changelog and not fetch_full_changelog else None
    flds = fields or DEFAULT_FIELDS

    for issue in client.search_issues_stream(jql=jql, page_size=page_size, fields=flds, expand=expand):
        if fetch_full_changelog:
            iterator = client.iter_issue_changelog(issue["key"], page_size=100)
            histories = []
            meta: dict | None = None
            while True:
                try:
                    histories.append(next(iterator))
                except StopIteration as stop:
                    meta = stop.value or {}
                    break

            payload = {"histories": histories}
            if meta:
                payload.update(meta)
            issue["changelog"] = payload
        yield issue

    client.close()
