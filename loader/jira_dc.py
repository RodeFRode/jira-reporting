from __future__ import annotations
import time, logging, httpx
from typing import Optional
log = logging.getLogger(__name__)

class JiraClient:
    def __init__(
        self,
        base_url: str,
        auth_type: str,
        token: Optional[str],
        username: Optional[str],
        password: Optional[str],
        cf_access_client_id: Optional[str] = None,
        cf_access_client_secret: Optional[str] = None,
        cf_access_jwt: Optional[str] = None,
    ):
        self.base = base_url
        self.auth_type = auth_type
        self.token = token
        self.username = username
        self.password = password
        self.cf_access_client_id = cf_access_client_id
        self.cf_access_client_secret = cf_access_client_secret
        self.cf_access_jwt = cf_access_jwt

        def on_request(request: httpx.Request):
            request.extensions["start_time"] = time.perf_counter()
            # keine Header/Secrets loggen!
            log.debug("HTTP request", extra={"method": request.method, "url": str(request.url)})

        def on_response(response: httpx.Response):
            req = response.request
            start = req.extensions.get("start_time")
            elapsed_ms = int((time.perf_counter() - start) * 1000) if start is not None else None
            log.info("HTTP response", extra={
                "method": req.method, "url": str(req.url),
                "status_code": response.status_code, "elapsed_ms": elapsed_ms
            })
            # Erklärbare Fehler bei 302 -> Cloudflare Access
            if response.status_code in (301, 302, 303, 307, 308):
                loc = response.headers.get("Location", "")
                if "cloudflareaccess.com" in loc or "cdn-cgi/access" in loc:
                    log.error("Blocked by Cloudflare Access (302 redirect detected). Provide CF service token or JWT.")
        # follow_redirects=False erleichtert Diagnose (keine stillen HTML-Logins)
        self.client = httpx.Client(timeout=30.0, event_hooks={"request":[on_request], "response":[on_response]}, follow_redirects=False)

    def _headers(self):
        h = {"Accept": "application/json"}
        # KORREKT: echten PAT schicken, nicht maskiert
        if self.auth_type == "pat" and self.token:
            h["Authorization"] = f"Bearer {self.token}"

        # Cloudflare Access – bevorzugt Service Token
        if self.cf_access_client_id and self.cf_access_client_secret:
            h["CF-Access-Client-Id"] = self.cf_access_client_id
            h["CF-Access-Client-Secret"] = self.cf_access_client_secret
        elif self.cf_access_jwt:
            # vorhandenes Browser-/SSO-JWT als Cookie senden
            h["Cookie"] = f"CF_Authorization={self.cf_access_jwt}"
        return h

    def _auth(self):
        if self.auth_type == "basic" and self.username and self.password:
            return (self.username, self.password)
        return None

    def search_issues(self, jql: str, start_at: int = 0, max_results: int = 100, fields: list[str] | None = None, expand: list[str] | None = None):
        params = {"jql": jql, "startAt": start_at, "maxResults": max_results}
        if fields: params["fields"] = ",".join(fields)
        if expand: params["expand"] = ",".join(expand)
        for attempt in range(5):
            try:
                r = self.client.get(f"{self.base}/rest/api/2/search", headers=self._headers(), auth=self._auth(), params=params)
                # 302 von Cloudflare Access → erklärbarer Fehler
                if r.status_code in (301,302,303,307,308):
                    loc = r.headers.get("Location","")
                    if "cloudflareaccess.com" in loc or "cdn-cgi/access" in loc:
                        raise RuntimeError("Cloudflare Access blocked the request (redirect to login). Provide CF_ACCESS_CLIENT_ID/SECRET or CF_ACCESS_JWT.")
                if r.status_code == 429 or r.status_code >= 500:
                    wait = 2 ** attempt
                    log.warning("Retrying /search", extra={"status": r.status_code, "attempt": attempt, "wait_s": wait})
                    time.sleep(wait); continue
                r.raise_for_status(); return r.json()
            except httpx.HTTPError as e:
                wait = 2 ** attempt
                log.warning("HTTPError /search", extra={"attempt": attempt, "wait_s": wait, "error": str(e)})
                time.sleep(wait)
        log.error("Failed /search after retries", extra={"jql": jql, "start_at": start_at}); raise RuntimeError("Failed /search after retries")

    def get_issue_changelog_full(self, issue_id_or_key: str, page_size: int = 100) -> dict:
        start_at, all_histories, total = 0, [], None
        for attempt in range(5):
            try:
                while True:
                    r = self.client.get(f"{self.base}/rest/api/2/issue/{issue_id_or_key}/changelog",
                                        headers=self._headers(), auth=self._auth(),
                                        params={"startAt": start_at, "maxResults": page_size})
                    if r.status_code in (301,302,303,307,308):
                        loc = r.headers.get("Location","")
                        if "cloudflareaccess.com" in loc or "cdn-cgi/access" in loc:
                            raise RuntimeError("Cloudflare Access blocked the request (redirect to login). Provide CF_ACCESS_CLIENT_ID/SECRET or CF_ACCESS_JWT.")
                    if r.status_code == 429 or r.status_code >= 500:
                        wait = 2 ** attempt
                        log.warning("Retrying changelog", extra={"status": r.status_code, "attempt": attempt, "wait_s": wait, "start_at": start_at})
                        time.sleep(wait); continue
                    r.raise_for_status()
                    data = r.json()
                    total = data.get("total")
                    histories = data.get("values") or data.get("histories") or []
                    all_histories.extend(histories)
                    got = len(histories); start_at += got
                    log.debug("Changelog page", extra={"got": got, "accumulated": len(all_histories), "total": total})
                    if (total is not None and start_at >= total) or got == 0: break
                break
            except httpx.HTTPError as e:
                wait = 2 ** attempt
                log.warning("HTTPError changelog", extra={"attempt": attempt, "wait_s": wait, "error": str(e)})
                time.sleep(wait)
        return {"total": total if total is not None else len(all_histories), "histories": all_histories}
