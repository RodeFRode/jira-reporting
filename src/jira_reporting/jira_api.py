from __future__ import annotations
from typing import Iterable, Optional, Sequence
import httpx

from .config import Settings

MYSELF_PATH = "/rest/api/2/myself"
SEARCH_PATH = "/rest/api/2/search"


class JiraClient:
    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None) -> None:
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
        page_size: int = 50,
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


# Backward-compat: Tests importieren JiraAPI
class JiraAPI(JiraClient):
    pass


__all__ = [
    "JiraClient",
    "JiraAPI",
    "MYSELF_PATH",
    "SEARCH_PATH",
]
