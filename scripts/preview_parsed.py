# scripts/preview_parsed.py
from __future__ import annotations
import shutil
from textwrap import shorten

from jira_reporting.config import Settings
from jira_reporting.jira_api import JiraClient
from jira_reporting.parse import parse_issue, iter_changelog_items

# Schlanke Felderliste – passe sie später nach Bedarf an
FIELDS = [
    "summary", "assignee", "status", "issuetype", "priority", "labels",
    "components", "project", "created", "updated"
]

def print_table(rows):
    term_w = shutil.get_terminal_size((120, 20)).columns
    def fmt(row):
        return [
            row.key,
            row.issuetype or "-",
            row.status or "-",
            shorten(row.summary or "", width=max(20, term_w - 80), placeholder="…"),
            row.assignee or "-",
            (row.updated or "-").replace("T", " ")[:19],
        ]
    headers = ["Key", "Type", "Status", "Summary", "Assignee", "Updated"]
    data = [headers] + [fmt(r) for r in rows]
    widths = [max(len(c[i]) for c in data) for i in range(len(headers))]
    for i, h in enumerate(headers):
        print(h.ljust(widths[i]), end="  ")
    print()
    print("  ".join("-" * w for w in widths))
    for d in data[1:]:
        for i, cell in enumerate(d):
            print(cell.ljust(widths[i]), end="  ")
        print()

def main():
    s = Settings.from_env()
    client = JiraClient(s)
    try:
        me = client.get_myself()
        print(f"Auth OK as: {me.get('displayName') or me.get('name')}")
        jql = s.jql or "project = TEST ORDER BY updated ASC"
        print(f"Using JQL: {jql}")

        parsed_rows = []
        total_changes = 0

        for raw in client.search_issues_stream(
            jql=jql,
            page_size=s.page_size,
            fields=FIELDS,
            expand=["changelog"],   # falls du Changelog sehen willst
        ):
            row = parse_issue(raw)
            parsed_rows.append(row)
            # Optional: Changelog zusammenzählen
            total_changes += sum(1 for _ in iter_changelog_items(raw))
            if len(parsed_rows) >= 25:  # nur erste 25 Zeilen als Preview anzeigen
                break

        print_table(parsed_rows)
        print(f"\nPreview rows: {len(parsed_rows)}  |  Changelog items (in preview): {total_changes}")

    finally:
        client.close()

if __name__ == "__main__":
    main()
