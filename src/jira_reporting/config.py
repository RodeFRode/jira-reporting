# src/jira_reporting/config.py
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import httpx
from dotenv import load_dotenv, find_dotenv

MYSELF_PATH = "/rest/api/2/myself"
SEARCH_PATH = "/rest/api/2/search"

def _parse_bool(val: Optional[str], default: bool = True) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    base_url: str
    pat: str
    ca_bundle: Optional[str] = None
    page_size: int = 100
    validate_query: bool = True
    timeout_s: float = 30.0
    # NEW: optional JQL aus der .env (kann None sein)
    jql: Optional[str] = None

    @classmethod
    def from_env(cls, env_path: Optional[str | Path] = None) -> "Settings":
        # robustes Laden der .env
        tried = []
        loaded = False
        if env_path:
            p = Path(env_path)
            tried.append(p)
            if p.is_file():
                load_dotenv(p, override=False)
                loaded = True
        if not loaded:
            p = Path.cwd() / ".env"
            tried.append(p)
            if p.is_file():
                load_dotenv(p, override=False)
                loaded = True
        if not loaded:
            repo_root = Path(__file__).resolve().parents[2]
            p = repo_root / ".env"
            tried.append(p)
            if p.is_file():
                load_dotenv(p, override=False)
                loaded = True
        if not loaded:
            p = find_dotenv(usecwd=True)
            if p:
                load_dotenv(p, override=False)
                loaded = True

        base_url = os.getenv("JIRA_BASE_URL") or os.getenv("BASE_URL")
        pat = os.getenv("JIRA_PAT") or os.getenv("PAT")
        ca_bundle = os.getenv("JIRA_CA_BUNDLE") or os.getenv("CA_BUNDLE")
        page_size = int(os.getenv("JIRA_PAGE_SIZE") or 100)
        validate_query = _parse_bool(os.getenv("JIRA_VALIDATE_QUERY"), True)
        timeout_s = float(os.getenv("JIRA_TIMEOUT_S") or 30.0)
        jql = os.getenv("JIRA_JQL")  # kann None sein

        missing = []
        if not base_url:
            missing.append("JIRA_BASE_URL")
        if not pat:
            missing.append("JIRA_PAT")
        if missing:
            tried_str = ", ".join(str(t) for t in tried)
            raise RuntimeError(f"Missing required env var(s): {', '.join(missing)} (tried: {tried_str or 'n/a'})")

        return cls(
            base_url=base_url.rstrip("/"),
            pat=pat,
            ca_bundle=ca_bundle,
            page_size=page_size,
            validate_query=validate_query,
            timeout_s=timeout_s,
            jql=jql,
        )

    def build_client(self, transport: httpx.BaseTransport | None = None) -> httpx.Client:
        headers = {"Authorization": f"Bearer {self.pat}"}
        timeout = httpx.Timeout(self.timeout_s)
        verify = self.ca_bundle if self.ca_bundle else True
        return httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            verify=verify,
            transport=transport,
        )
