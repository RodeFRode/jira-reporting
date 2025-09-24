from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import os
import httpx
from dotenv import load_dotenv, find_dotenv

# Von den Tests erwartete Konstante:
MYSELF_PATH = "/rest/api/2/myself"


@dataclass
class Settings:
    base_url: str
    pat: str
    ca_bundle: Optional[str] = None
    timeout_s: float = 30.0
    page_size: int = 100
    jql: Optional[str] = None
    # optional Cloudflare Access
    cf_client_id: Optional[str] = None
    cf_client_secret: Optional[str] = None
    cf_jwt: Optional[str] = None

    def build_client(self, transport: Optional[httpx.BaseTransport] = None) -> httpx.Client:
        headers = {"Authorization": f"Bearer {self.pat}"}
        if self.cf_client_id and self.cf_client_secret:
            headers["CF-Access-Client-Id"] = self.cf_client_id
            headers["CF-Access-Client-Secret"] = self.cf_client_secret
        if self.cf_jwt:
            headers["CF-Access-Jwt-Assertion"] = self.cf_jwt

        return httpx.Client(
            base_url=self.base_url.rstrip("/"),
            headers=headers,
            timeout=self.timeout_s,
            verify=self.ca_bundle if self.ca_bundle else True,
            transport=transport,
        )

    @classmethod
    def from_env(cls) -> "Settings":
        # .env aus dem aktuellen Projekt finden & laden
        load_dotenv(find_dotenv(usecwd=True), override=False)

        base_url = os.getenv("JIRA_BASE_URL")
        pat = os.getenv("JIRA_PAT")
        if not base_url or not pat:
            missing = [k for k, v in [("JIRA_BASE_URL", base_url), ("JIRA_PAT", pat)] if not v]
            raise RuntimeError(f"Missing required env var(s): {', '.join(missing)}")

        return cls(
            base_url=base_url,
            pat=pat,
            ca_bundle=os.getenv("JIRA_CA_BUNDLE") or None,
            timeout_s=float(os.getenv("JIRA_TIMEOUT_S", "30")),
            page_size=int(os.getenv("JIRA_PAGE_SIZE", "100")),
            jql=os.getenv("JIRA_JQL") or None,
            cf_client_id=os.getenv("CF_ACCESS_CLIENT_ID") or None,
            cf_client_secret=os.getenv("CF_ACCESS_CLIENT_SECRET") or None,
            cf_jwt=os.getenv("CF_ACCESS_JWT") or None,
        )


__all__ = ["Settings", "MYSELF_PATH"]
