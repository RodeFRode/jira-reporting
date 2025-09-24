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
        jql: str,
        *,
        page_size: int = 100,
        expand: Optional[Sequence[str]] = None,
        fields: Optional[Sequence[str]] = None,
    ) -> Iterable[dict]:
        """
        Streamt Issues via POST /search. 'expand' wird als Query-Parameter gesendet.
        """
        start_at = 0
        params = {}
        if expand:
            params["expand"] = ",".join(expand)

        while True:
            payload: dict = {"jql": jql, "startAt": start_at, "maxResults": page_size}
            if fields is not None:
                payload["fields"] = list(fields)

            r = self.client.post(SEARCH_PATH, params=params, json=payload)
            if r.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"Jira /search returned {r.status_code}. Body: {r.text}",
                    request=r.request,
                    response=r,
                )
            data = r.json()

            issues = data.get("issues", [])
            for it in issues:
                yield it

            got = len(issues)
            total = data.get("total")
            start_at += got

            if got == 0:
                break
            if isinstance(total, int) and start_at >= total:
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
