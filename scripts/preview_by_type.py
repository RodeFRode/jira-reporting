import json
from pathlib import Path

from jira_reporting.config import Settings
from jira_reporting.jira_api import JiraClient


_DICT_VALUE_KEYS = (
    "displayName",
    "name",
    "value",
    "summary",
    "title",
    "text",
    "description",
    "key",
    "emailAddress",
)


def _format_issue_ref(issue):
    if not isinstance(issue, dict):
        return _format_field_value(issue)

    key = issue.get("key") or issue.get("id")
    summary = None
    fields = issue.get("fields")
    if isinstance(fields, dict):
        summary = fields.get("summary") or fields.get("name")

    if key and summary:
        return f"{key} ({summary})"
    if key:
        return str(key)

    summary = issue.get("summary") or issue.get("name")
    if summary:
        return _format_field_value(summary)

    return json.dumps(issue, ensure_ascii=False)


def _format_issue_link(link: dict) -> str:
    type_info = link.get("type") if isinstance(link, dict) else None
    relationship_out = type_info.get("outward") if isinstance(type_info, dict) else None
    relationship_in = type_info.get("inward") if isinstance(type_info, dict) else None
    type_name = type_info.get("name") if isinstance(type_info, dict) else None

    parts: list[str] = []

    if isinstance(link, dict):
        if "outwardIssue" in link:
            relation = relationship_out or type_name or "outward"
            parts.append(f"{relation}: {_format_issue_ref(link['outwardIssue'])}")
        if "inwardIssue" in link:
            relation = relationship_in or type_name or "inward"
            parts.append(f"{relation}: {_format_issue_ref(link['inwardIssue'])}")

    if parts:
        return "; ".join(parts)

    return json.dumps(link, ensure_ascii=False)


def _format_field_value(value):
    if value is None:
        return "<none>"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "<none>"
        parts = [p for p in (_format_field_value(item) for item in value) if p and p != "<none>"]
        return ", ".join(parts) if parts else "<none>"
    if isinstance(value, dict):
        if "inwardIssue" in value or "outwardIssue" in value:
            return _format_issue_link(value)
        for key in _DICT_VALUE_KEYS:
            candidate = value.get(key)
            if candidate:
                return _format_field_value(candidate)

        # special case for paged results that embed "values" or "histories"
        if "values" in value or "histories" in value:
            entries = value.get("values")
            if entries is None:
                entries = value.get("histories")
            return _format_field_value(entries)

        items = []
        for key in sorted(value):
            nested = _format_field_value(value[key])
            items.append(f"{key}={nested}")
        if items:
            return "{" + ", ".join(items) + "}"
        return "<none>"

    return json.dumps(value, ensure_ascii=False)


def main() -> int:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    s = Settings.from_env(env_path=env_path)
    client = JiraClient(s)
    print(f"Auth OK as: {client.get_myself().get('displayName') or 'n/a'}")
    print(f"Base JQL: {s.jql or '<<none>>'}")

    validate = getattr(s, "validate_query", True)

    type_fields = {
        "Feature": ["customfield_11881","customfield_11882","customfield_11883","customfield_11885","customfield_11880","customfield_11884","customfield_10312","customfield_10355","customfield_10317","customfield_10363","customfield_10364","customfield_10341","customfield_10318","customfield_10319","customfield_10320","customfield_10310","customfield_10345","customfield_10303","customfield_10302","customfield_10354","customfield_10365","customfield_10348","customfield_10351","customfield_10366","customfield_11167","customfield_10367","customfield_10368","customfield_10369","customfield_10333","customfield_10311","customfield_10353","customfield_10349","customfield_10304","customfield_10305","customfield_10308","customfield_10315","customfield_10314","customfield_11001","customfield_10107","customfield_10758","customfield_10757","customfield_10358","customfield_10357","customfield_10356","issuetype","summary","customfield_10618","priority","assignee","customfield_10301","customfield_11897","components","fixVersions","customfield_11672","customfield_10326","customfield_10328","customfield_10327","customfield_14290","issuelinks","labels","customfield_11896","customfield_10362","customfield_13268 ","customfield_11864","customfield_11334"],
        "Enabler": ["customfield_11881","customfield_11882","customfield_11883","customfield_11885","customfield_11880","customfield_11884","customfield_10312","customfield_10355","customfield_10317","customfield_10363","customfield_10364","customfield_10341","customfield_10318","customfield_10319","customfield_10320","customfield_10310","customfield_10345","customfield_10303","customfield_10302","customfield_10354","customfield_10365","customfield_10348","customfield_10351","customfield_10366","customfield_11167","customfield_10367","customfield_10368","customfield_10369","customfield_10333","customfield_10311","customfield_10353","customfield_10349","customfield_10304","customfield_10305","customfield_10308","customfield_10315","customfield_10314","customfield_11001","customfield_10107","customfield_10758","customfield_10757","customfield_10358","customfield_10357","customfield_10356","issuetype","summary","customfield_10618","priority","assignee","customfield_10301","customfield_11897","components","fixVersions","customfield_11672","customfield_10326","customfield_10328","customfield_10327","customfield_14290","issuelinks","labels","customfield_11896","customfield_10362","customfield_13268 ","customfield_11864","customfield_11334"],
        "Epic": ["customfield_11881","customfield_11882","customfield_11883","customfield_11885","customfield_11880","customfield_11884","customfield_10312","customfield_10355","customfield_10317","customfield_10363","customfield_10364","customfield_10341","customfield_10318","customfield_10319","customfield_10320","customfield_10310","customfield_10345","customfield_10303","customfield_10302","customfield_10354","customfield_10365","customfield_10348","customfield_10351","customfield_10366","customfield_11167","customfield_10367","customfield_10368","customfield_10369","customfield_10333","customfield_10311","customfield_10353","customfield_10349","customfield_10304","customfield_10305","customfield_10308","customfield_10315","customfield_10314","customfield_11001","customfield_10107","customfield_10758","customfield_10757","customfield_10358","customfield_10357","customfield_10356","issuetype","summary","customfield_10618","priority","assignee","customfield_10301","customfield_11897","components","fixVersions","customfield_11672","customfield_10326","customfield_10328","customfield_10327","customfield_14290","issuelinks","labels","customfield_11896","customfield_10362","customfield_13268 ","customfield_11864","customfield_11334"],

    }

    field_name_map = client.get_field_name_map()

    for issuetype, fields in type_fields.items():
        jql = f"({s.jql}) AND issuetype = \"{issuetype}\"" if s.jql else f'issuetype = "{issuetype}"'
        print(f"\n=== {issuetype} ===")
        for issue in client.search_issues_stream(jql=jql, fields=fields, validate_query=validate, page_size=s.page_size):
            key = issue.get("key") or "<unknown>"
            print(key)
            field_values = issue.get("fields") or {}
            for field_name in fields:
                field_id = field_name.strip()
                label = field_name_map.get(field_id, field_id)
                formatted = _format_field_value(field_values.get(field_id))
                print(f"    {label}: {formatted}")
            print()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
