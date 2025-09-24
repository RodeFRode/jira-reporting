from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import httpx

MYSELF_PATH = "/rest/api/2/myself"
SEARCH_PATH = "/rest/api/2/search"

@dataclass(frozen=True)
class Settings:
    base_url: str
    pat: str
    ca_bundle: Optional[str] = None
    timeout_s: Optional[float] = 5.0  # <- neu: explizit konfigurierbar

    def build_client(self, *, transport: Optional[httpx.BaseTransport] = None) -> httpx.Client:
        """
        Baut einen synchronen HTTPX-Client mit PAT-Auth und optionalem Custom CA.
        In Tests kann per `transport=MockTransport` injiziert werden.
        """
        headers = {
            "Authorization": f"Bearer {self.pat}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        verify = self.ca_bundle if self.ca_bundle else True
        return httpx.Client(
            base_url=self.base_url,
            headers=headers,
            verify=verify,
            timeout=self.timeout_s,     # <- neu
            transport=transport,
        )
