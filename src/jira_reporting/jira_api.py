# src/jira_reporting/jira_api.py
from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, List
import httpx

from .config import Settings, MYSELF_PATH, SEARCH_PATH


class JiraClient:
    """
    Dünner Wrapper um httpx.Client mit PAT-Auth, plus High-Level-Methoden.
    Für Tests kann ein vorbereiteter Client (MockTransport) injiziert werden.
    """

    def __init__(self, settings: Settings, *, client: Optional[httpx.Client] = None):
        self.settings = settings
        self.client = client or settings.build_client()

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def auth_check(self) -> Dict[str, Any]:
        """
        Führt einen /myself-Call aus, um Authentifizierung & Verbindung zu prüfen.
        Raises:
            httpx.HTTPStatusError bei Nicht-2xx
        """
        r = self.client.get(MYSELF_PATH)
        r.raise_for_status()
        return r.json()

    def get_myself(self) -> Dict[str, Any]:
        """
        Alias für Tests/Lesbarkeit: entspricht auth_check().
        """
        return self.auth_check()

    def search_stream(
        self,
        *,
        jql: str,
        page_size: int = 100,
        start_at: int = 0,
        expand: Optional[list[str]] = None,
    ) -> Iterable[Dict[str, Any]]:
        """
        Streamt Issues seitenweise über /rest/api/2/search (POST).

        Args:
            jql: Jira Query Language
            page_size: gewünschte Anzahl Issues pro Page (Server kann davon abweichen)
            start_at: Startoffset
            expand: zusätzliche Expand-Felder (z.B. ["changelog"])

        Yields:
            Issue-Dictionaries (so wie von der Jira-API geliefert)

        Raises:
            httpx.HTTPStatusError: bei Nicht-2xx-Antworten
        """
        current = start_at
        expand_list = expand or []

        while True:
            payload = {
                "jql": jql,
                "startAt": current,
                "maxResults": page_size,
                "expand": expand_list,
            }
            # Jira Server/DC: /rest/api/2/search via POST mit JSON body
            r = self.client.post(SEARCH_PATH, json=payload)
            r.raise_for_status()

            data: Dict[str, Any] = r.json()
            issues: List[Dict[str, Any]] = data.get("issues") or []

            # Yield alle Issues dieser Seite
            for it in issues:
                yield it

            returned = len(issues)
            if returned == 0:
                break  # nichts mehr da

            # Robuste Fortschritts-Logik:
            # - Manche Server ignorieren requested maxResults
            # - Wir zählen mit der realen Rückgabemenge weiter
            resp_start = int(data.get("startAt", current))
            total = data.get("total")
            current = resp_start + returned

            # Stop, wenn wir total erreicht/überschritten haben
            if isinstance(total, int) and current >= total:
                break

    def search_issues_stream(
        self,
        *,
        jql: str,
        page_size: int = 100,
        start_at: int = 0,
        expand: Optional[list[str]] = None,
    ) -> Iterable[Dict[str, Any]]:
        """
        Alias für Tests/Lesbarkeit: entspricht search_stream().
        """
        return self.search_stream(jql=jql, page_size=page_size, start_at=start_at, expand=expand)


# Alias für bestehende Imports in Tests
JiraAPI = JiraClient
