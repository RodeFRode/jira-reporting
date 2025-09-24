from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import os
import uuid
import httpx
from dotenv import load_dotenv

API_PREFIX = "/rest/api/2"
MYSELF_PATH = f"{API_PREFIX}/myself"
SEARCH_PATH = f"{API_PREFIX}/search"


@dataclass(frozen=True)
class Settings:
    base_url: str
    pat: str

    # Optionales Unternehmens-CA (Pfad zu .crt / .pem) oder None -> System-Truststore
    ca_bundle: Optional[str] = None

    # Effektiver Timeout in Sekunden (wird aus timeout_s gespiegelt, wenn übergeben)
    timeout: float = 30.0

    # Alias, damit Tests Settings(..., timeout_s=5.0) benutzen können
    timeout_s: Optional[float] = None

    # Defaults für Suche/ETL
    page_size: int = 100
    jql: Optional[str] = None

    # Optional: Cloudflare Access (falls benötigt)
    cf_token: Optional[str] = None
    cf_client_id: Optional[str] = None
    cf_client_secret: Optional[str] = None

    def __post_init__(self):
        # Alias-Handling: timeout_s hat Vorrang, wenn gesetzt
        if self.timeout_s is not None:
            object.__setattr__(self, "timeout", float(self.timeout_s))

    def build_client(self, *, transport: Optional[httpx.BaseTransport] = None) -> httpx.Client:
        headers = {
            "Authorization": f"Bearer {self.pat}",
            "Accept": "application/json",
        }
        if self.cf_token:
            headers["CF-Access-JWT-Assertion"] = self.cf_token
        if self.cf_client_id and self.cf_client_secret:
            headers["CF-Access-Client-Id"] = self.cf_client_id
            headers["CF-Access-Client-Secret"] = self.cf_client_secret

        # verify: Pfad zur CA oder True (Systemzertifikate)
        verify = self.ca_bundle or True

        # kleine Request-ID für einfacheres Debugging in Logs/Proxies
        def _attach_req_id(request: httpx.Request) -> None:
            request.headers.setdefault("X-Request-Id", str(uuid.uuid4()))

        return httpx.Client(
            base_url=self.base_url.rstrip("/"),
            headers=headers,
            verify=verify,
            timeout=self.timeout,
            transport=transport,  # für httpx.MockTransport in Tests
            event_hooks={"request": [_attach_req_id]},
        )

    @staticmethod
    def from_env(env: Optional[dict] = None, *, dotenv_path: Optional[str | Path] = None) -> "Settings":
        """
        Liest Settings aus Umgebungsvariablen. Lädt .env, wenn vorhanden.
        Benötigt: JIRA_BASE_URL, JIRA_PAT
        Optionale: JIRA_CA_BUNDLE, JIRA_TIMEOUT_S, JIRA_PAGE_SIZE, JIRA_JQL,
                   CF_ACCESS_JWT, CF_ACCESS_CLIENT_ID, CF_ACCESS_CLIENT_SECRET
        """
        if env is None:
            env = os.environ

        # .env laden, falls vorhanden (oder explizit übergeben)
        if dotenv_path or Path(".env").exists():
            load_dotenv(dotenv_path=str(dotenv_path) if dotenv_path else None, override=False)
            env = os.environ  # nachladen

        def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
            val = env.get(name)
            return default if (val is None or val == "") else val

        missing = [n for n in ("JIRA_BASE_URL", "JIRA_PAT") if not getenv(n)]
        if missing:
            raise RuntimeError(f"Missing required env var(s): {', '.join(missing)}")

        return Settings(
            base_url=getenv("JIRA_BASE_URL"),
            pat=getenv("JIRA_PAT"),
            ca_bundle=getenv("JIRA_CA_BUNDLE"),
            timeout=float(getenv("JIRA_TIMEOUT_S", 30.0)),
            page_size=int(getenv("JIRA_PAGE_SIZE", 100)),
            jql=getenv("JIRA_JQL"),
            cf_token=getenv("CF_ACCESS_JWT"),
            cf_client_id=getenv("CF_ACCESS_CLIENT_ID"),
            cf_client_secret=getenv("CF_ACCESS_CLIENT_SECRET"),
        )
