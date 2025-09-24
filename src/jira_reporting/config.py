from __future__ import annotations
import os
import ssl
from dataclasses import dataclass
from typing import Optional
import httpx
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    base_url: str
    pat: str
    ca_bundle: Optional[str] = None
    timeout_s: float = 30.0
    cf_access_client_id: Optional[str] = None
    cf_access_client_secret: Optional[str] = None

    @staticmethod
    def from_env() -> "Settings":
        # Lädt .env falls vorhanden (ohne Assertion-Fehler bei REPL)
        load_dotenv()
        base_url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
        pat = os.getenv("JIRA_PAT", "")
        if not base_url or not pat:
            raise RuntimeError("JIRA_BASE_URL und JIRA_PAT müssen gesetzt sein (.env oder Environment).")

        ca_bundle = os.getenv("JIRA_CA_BUNDLE")  # Pfad zu deiner .crt
        timeout_s = float(os.getenv("HTTP_TIMEOUT_S", "30"))
        cf_id = os.getenv("CF_ACCESS_CLIENT_ID")
        cf_secret = os.getenv("CF_ACCESS_CLIENT_SECRET")

        return Settings(
            base_url=base_url,
            pat=pat,
            ca_bundle=ca_bundle,
            timeout_s=timeout_s,
            cf_access_client_id=cf_id,
            cf_access_client_secret=cf_secret,
        )

    def build_client(self, transport: Optional[httpx.BaseTransport] = None) -> httpx.Client:
        """
        Erstellt einen synchronen httpx.Client mit:
        - Bearer PAT
        - optionalem Cloudflare-Access-Header
        - optionalem custom CA-Bundle
        """
        headers = {
            "Authorization": f"Bearer {self.pat}",   # PAT als Bearer in DC/Server.
            "Accept": "application/json",
        }
        # Optionale Cloudflare Access Service Token (falls nötig)
        if self.cf_access_client_id and self.cf_access_client_secret:
            headers["CF-Access-Client-Id"] = self.cf_access_client_id
            headers["CF-Access-Client-Secret"] = self.cf_access_client_secret

        verify: ssl.SSLContext | str | bool
        if self.ca_bundle:
            # Entweder Pfad als String (einfach) …
            verify = self.ca_bundle
        else:
            # … oder Standard-Truststore des Systems
            verify = True

        return httpx.Client(
            headers=headers,
            timeout=httpx.Timeout(self.timeout_s),
            verify=verify,                  # alternativ: Env SSL_CERT_FILE setzen
            transport=transport,            # für Tests via MockTransport
            event_hooks={
                "request": [self._on_request_log],
                "response": [self._on_response_log],
            },
        )

    # --- einfache, schlanke Logs (können wir später ausbauen) ---
    def _on_request_log(self, request: httpx.Request) -> None:
        import logging
        logging.getLogger("httpx").info("HTTP Request: %s %s", request.method, str(request.url))

    def _on_response_log(self, response: httpx.Response) -> None:
        import logging
        logging.getLogger("httpx").info("HTTP Response: %s %s -> %s",
                                        response.request.method, str(response.request.url), response.status_code)

# Konstanten für DC-API
API_V2 = "/rest/api/2"  # Data Center/Server v2-API Referenz
MYSELF_PATH = f"{API_V2}/myself"
