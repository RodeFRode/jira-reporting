# scripts/dump_issues.py
from pathlib import Path
import json

from jira_reporting.config import Settings
from jira_reporting.jira_api import JiraClient


def main() -> None:
    # Konfig aus Umgebungsvariablen (oder .env) laden
    s = Settings.from_env()
    client = JiraClient(s)

    try:
        # Sanity: Auth prüfen
        me = client.get_myself()
        print(f"Auth OK as: {me.get('displayName') or me.get('name')}")

        # JQL aus ENV oder Fallback
        jql = s.jql or "project = TEST ORDER BY updated ASC"

        out = Path("out/issues.ndjson")
        out.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with out.open("w", encoding="utf-8") as fh:
            for issue in client.search_issues_stream(
                jql=jql,
                page_size=s.page_size,
                expand=["changelog"],
            ):
                fh.write(json.dumps(issue, ensure_ascii=False) + "\n")
                count += 1

        print(f"Wrote {count} issues to {out.resolve()}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
