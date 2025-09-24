# Ausführen mit:  python -m scripts.preview_issues
from __future__ import annotations
import sys
from typing import List
from jira_reporting.config import Settings
from jira_reporting.jira_api import JiraClient
from jira_reporting.parsing import parse_issue

# Welche Felder minimal holen? (kannst du später erweitern)
DEFAULT_FIELDS: List[str] = [
    "summary", "status", "assignee", "updated", "created", "issuetype", "project"
]

def main() -> int:
    s = Settings.from_env()

    client = JiraClient(s)
    # 1) Auth-Check
    me = client.get_myself()
    who = me.get("displayName") or me.get("name")
    print(f"Auth OK as: {who}")

    # 2) JQL aus .env nehmen (fail-safe: bestehende s.jql; falls leer -> Hinweis + Abbruch)
    if not s.jql:
        print("Fehlende JQL (setze JIRA_JQL in deiner .env), z. B.: project = ABC AND updated >= -14d ORDER BY updated ASC")
        return 2

    print(f"Using JQL: {s.jql}")
    count = 0

    # 3) Iteriere paginiert über /search (POST)
    for raw in client.search_issues_stream(
        jql=s.jql,
        page_size=s.page_size,
        expand=["changelog"],
        validate_query=True,  # jetzt gültig (optional)
    ):
        item = parse_issue(raw)
        # 4) Schöne Ein-Zeilen-Ausgabe
        #   KEY         UPDATED                  STATUS              ASSIGNEE             SUMMARY (gekürzt)
        summary_short = (item.summary or "").replace("\n", " ")
        if len(summary_short) > 100:
            summary_short = summary_short[:97] + "..."
        print(f"{item.key:<12} {item.updated:<20} {item.status:<18} {item.assignee:<22} {summary_short}")
        count += 1

    print(f"\nTotal: {count} issues")
    return 0

if __name__ == "__main__":
    sys.exit(main())
