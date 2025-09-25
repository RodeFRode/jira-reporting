from pathlib import Path
from jira_reporting.config import Settings
from jira_reporting.jira_api import JiraClient

def main() -> int:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    s = Settings.from_env(env_path=env_path)
    client = JiraClient(s)
    print(f"Auth OK as: {client.get_myself().get('displayName') or 'n/a'}")
    print(f"Base JQL: {s.jql or '<<none>>'}")

    validate = getattr(s, "validate_query", True)

    type_fields = {
        "Story": ["summary", "status", "assignee", "customfield_12345"],
        "Bug":   ["summary", "priority", "status", "reporter"],
        "Task":  ["summary", "status"],
        "Enabler":   ["summary", "priority", "status", "reporter"],
        "Feature":   ["summary", "priority", "status", "reporter"],
        "Epic":   ["summary", "priority", "status", "reporter"],

    }

    for issuetype, fields in type_fields.items():
        jql = f"({s.jql}) AND issuetype = \"{issuetype}\"" if s.jql else f'issuetype = "{issuetype}"'
        print(f"\n=== {issuetype} ===")
        for issue in client.search_issues_stream(jql=jql, fields=fields, validate_query=validate, page_size=s.page_size):
            k = issue.get("key")
            f = issue.get("fields") or {}
            line = " | ".join(f"{name}={f.get(name)!r}" for name in fields)
            print(f"{k}: {line}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
