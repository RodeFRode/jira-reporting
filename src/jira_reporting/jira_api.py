from __future__ import annotations
import httpx

from .config import Settings

MYSELF_PATH = "/rest/api/2/myself"
SEARCH_PATH = "/rest/api/2/search"
CHANGELOG_PATH_TEMPLATE = "/rest/api/2/issue/{issue_key}/changelog"


class JiraClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or settings.build_client()

    # lifecycle
    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "JiraClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # API
    def auth_check(self) -> dict:
        """Alias für Tests: führt den /myself-Call aus."""
        return self.get_myself()

    def get_myself(self) -> dict:
        r = self.client.get(MYSELF_PATH)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise httpx.HTTPStatusError(
                f"/myself returned {r.status_code}. Body: {r.text}",
                request=r.request,
                response=r,
            ) from e
        return r.json()

    def search_issues_stream(
        self,
        *,
        jql: str,
        start_at: int = 0,
        page_size: int | None = 50,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
        validate_query: bool | None = None,  # <— NEU
    ):
        """
        Streamt Issues über POST /rest/api/2/search seitenweise.
        - jql: komplette JQL, inkl. ORDER BY
        - start_at, page_size: Pagination
        - fields, expand: optionale Felder/Expands
        - validate_query: wenn gesetzt, wird ins Payload als 'validateQuery' übernommen
          (siehe Jira REST: POST /rest/api/2/search akzeptiert validateQuery boolean)
        """
        if page_size is None:
            page_size = self.settings.page_size

        next_start = start_at
        total = None

        while True:
            payload = {
                "jql": jql,
                "startAt": next_start,
                "maxResults": page_size,
            }
            if fields is not None:
                payload["fields"] = fields
            if expand is not None:
                payload["expand"] = expand
            if validate_query is not None:
                payload["validateQuery"] = bool(validate_query)  # <— NEU

            r = self.client.post(SEARCH_PATH, json=payload)
            # httpx-Fehler klarer machen
            if r.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"Jira /search returned {r.status_code}. Body: {r.text}",
                    request=r.request,
                    response=r,
                )

            data = r.json()
            issues = data.get("issues", []) or []
            for it in issues:
                yield it

            total = data.get("total", total)
            returned = len(issues)
            next_start += returned
            if returned == 0:
                break
            if total is not None and next_start >= total:
                break

    def iter_issue_changelog(self, issue_key: str, page_size: int = 100):
        """Streamt den kompletten Changelog eines Issues seitenweise."""

        path = CHANGELOG_PATH_TEMPLATE.format(issue_key=issue_key)
        next_start = 0
        total = None
        meta: dict[str, int] = {}

        while True:
            params = {"startAt": next_start, "maxResults": page_size}
            r = self.client.get(path, params=params)
            if r.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"Jira changelog for {issue_key} returned {r.status_code}. Body: {r.text}",
                    request=r.request,
                    response=r,
                )

            data = r.json()
            histories = data.get("values")
            if histories is None:
                histories = data.get("histories", []) or []

            if "startAt" in data and "startAt" not in meta:
                meta["startAt"] = data["startAt"]
            if "maxResults" in data:
                meta["maxResults"] = data["maxResults"]
            if "total" in data:
                meta["total"] = data["total"]

            for history in histories:
                yield history

            returned = len(histories)
            total = data.get("total", total)
            next_start += returned

            if returned == 0:
                break
            if total is not None and next_start >= total:
                break

        return meta

    def _quote_jql_str(self, s: str) -> str:
        # minimal robustes Quoting (Doppelte Anführungszeichen escapen)
        return '"' + s.replace('"', '\\"') + '"'

    def search_issues_by_type(
        self,
        base_jql: str,
        per_type_fields: dict[str, list[str]],
        *,
        expand: list[str] | None = None,
        page_size: int | None = None,
        validate_query: bool = True,
    ):
        """
        Führt mehrere Suchen aus – gruppiert nach Issue-Typ-Sets mit identischer Feldliste –
        und liefert die Issues als ein gemeinsamer Generator zurück.

        per_type_fields: z.B. {
            "Bug":   ["key","summary","status","assignee","priority","issuetype","updated","created","changelog"],
            "Story": ["key","summary","status","assignee","issuetype","customfield_12345"]
        }
        """
        # Gruppe: gleiche Feldliste => gemeinsamer Call mit issuetype IN (...)
        groups: dict[tuple[str, ...], list[str]] = {}
        for itype, fields in per_type_fields.items():
            canon = tuple(sorted(set(fields)))
            groups.setdefault(canon, []).append(itype)

        for fields_tuple, types in groups.items():
            types_jql = ", ".join(self._quote_jql_str(t) for t in types)
            jql = f"({base_jql}) AND issuetype in ({types_jql})"
            # stream mit genau dieser Feldliste
            for issue in self.search_issues_stream(
                jql=jql,
                page_size=page_size,
                fields=list(fields_tuple),
                expand=expand,
                validate_query=validate_query,
            ):
                yield issue

# Backward-compat: Tests importieren JiraAPI
class JiraAPI(JiraClient):
    pass


__all__ = [
    "JiraClient",
    "JiraAPI",
    "MYSELF_PATH",
    "SEARCH_PATH",
]
