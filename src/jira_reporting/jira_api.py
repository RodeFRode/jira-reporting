from __future__ import annotations
from typing import Any, Dict, Iterable, Optional
import httpx
from .config import Settings, MYSELF_PATH, SEARCH_PATH


class JiraClient:
    """
    Dünner Wrapper um httpx.Client mit PAT-Auth + High-Level-Methoden.
    Für Tests kann ein vorbereiteter Client (MockTransport) injiziert werden.
    """
    def __init__(self, settings: Settings, *, client: Optional[httpx.Client] = None):
        self.settings = settings
        self.client = client or settings.build_client()

    # --- Auth / User ---

    def get_myself(self) -> Dict[str, Any]:
        r = self.client.get(MYSELF_PATH)
        r.raise_for_status()
        return r.json()

    def auth_check(self) -> Dict[str, Any]:
        return self.get_myself()

    # --- Search / Issues ---

    def search_issues_stream(
        self,
        *,
        jql: str,
        max_results: Optional[int] = None,
        expand: Optional[list[str]] = None,
    ) -> Iterable[dict]:
        """
        Streamt Issues seitenweise. Bricht ab wenn:
          - keine Issues zurückkommen, ODER
          - die Anzahl der ausgelieferten Issues >= total ist (falls total vorhanden).
        Zusätzlich: Schutz gegen „keinen Fortschritt“ (gleicher startAt).
        """
        start_at = 0
        page_size = max_results or self.settings.page_size
        emitted = 0
        last_start_at = -1  # für Sicherheitsabbruch falls kein Fortschritt

        while True:
            payload: dict = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size,
            }
            if expand:
                payload["expand"] = expand

            r = self.client.post(SEARCH_PATH, json=payload)
            r.raise_for_status()
            data: dict = r.json() or {}
            issues: list[dict] = data.get("issues") or []
            total: Optional[int] = data.get("total")

            # Keine Daten -> fertig
            if not issues:
                break

            # Yielden
            for it in issues:
                yield it
            emitted += len(issues)

            # Abbruch, sobald wir alles (laut total) geliefert haben
            if isinstance(total, int) and emitted >= total:
                break

            # Nächsten Offset bestimmen; Schutz gegen Endlosschleifen ohne Fortschritt
            resp_start = int(data.get("startAt", start_at))
            next_start = resp_start + len(issues)
            if next_start <= start_at or resp_start == last_start_at:
                # Server liefert immer wieder dieselbe Seite -> abbrechen
                break

            last_start_at = resp_start
            start_at = next_start


# Alias, damit ältere Imports (JiraAPI) weiterhin funktionieren
JiraAPI = JiraClient
