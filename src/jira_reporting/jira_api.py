from __future__ import annotations
from typing import Any, Dict, Optional
import httpx
from .config import Settings, MYSELF_PATH

class JiraAPI:
    """
    Kapselt JIRA-REST-Calls. Aktuell nur /myself, später erweitern wir (search, issue, changelog, …).
    """
    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None) -> None:
        self.settings = settings
        # Client injizierbar (für Tests); sonst aus Settings bauen
        self._client = client or self.settings.build_client()

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def auth_check(self) -> Dict[str, Any]:
        """
        Ruft /myself auf. Schlägt mit httpx.HTTPStatusError fehl, wenn Status != 2xx.
        Gibt bei Erfolg das JSON (User-Objekt) zurück.
        """
        url = f"{self.settings.base_url}{MYSELF_PATH}"
        r = self._client.get(url)
        r.raise_for_status()
        # Doku: /myself liefert die Daten des eingeloggten Users (DC-Referenz).
        # (Path-Gruppierung "myself" ist in DC/Server-Referenzen dokumentiert)
        # https://docs.atlassian.com/software/jira/docs/api/REST/9.14.0/  (DC Ref)
        return r.json()
