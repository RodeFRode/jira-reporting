from pathlib import Path
import json
from jira_reporting.config import Settings
from jira_reporting.jira_api import JiraClient

def main() -> None:
    s = Settings.from_env()
    with JiraClient(s) as client:
        me = client.get_myself()
        print(f"Auth OK as: {me.get('displayName') or me.get('name')}")

        if not s.jql or not s.jql.strip():
            raise RuntimeError("Missing JIRA_JQL in environment (.env). Bitte setze z. B.: "
                               "JIRA_JQL=project = <DEIN_PROJEKT> AND updated >= -14d ORDER BY updated ASC")
        jql = s.jql.strip()
        print(f"Using JQL: {jql}")

        out = Path("out/issues.ndjson")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("", encoding="utf-8")  # truncate

        count = 0
        for issue in client.search_issues_stream(jql=jql, page_size=s.page_size):
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(issue, ensure_ascii=False) + "\n")
            count += 1

        print(f"Wrote {count} issues to {out}")

if __name__ == "__main__":
    main()
