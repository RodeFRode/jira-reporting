# tests/test_search.py
from __future__ import annotations
import json
import httpx
from jira_reporting.config import Settings
from jira_reporting.jira_api import JiraClient


def make_client(pages: list[dict]) -> JiraClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rest/api/2/myself"):
            return httpx.Response(200, json={"name": "tester"})
        if request.url.path.endswith("/rest/api/2/search"):
            # Body ist JSON, aber Request hat keine .json()-Methode:
            body = json.loads((request.content or b"{}").decode("utf-8"))
            idx = (body.get("startAt", 0)) // 2
            idx = min(idx, len(pages) - 1)
            return httpx.Response(200, json=pages[idx])
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    s = Settings(base_url="https://jira.local", pat="t", timeout_s=5.0)
    httpx_client = s.build_client(transport=transport)
    return JiraClient(s, client=httpx_client)



def test_search_stream_paginates():
    pages = [
        {"startAt": 0, "maxResults": 2, "total": 5, "issues": [{"key": "A-1"}, {"key": "A-2"}]},
        {"startAt": 2, "maxResults": 2, "total": 5, "issues": [{"key": "A-3"}, {"key": "A-4"}]},
        {"startAt": 4, "maxResults": 2, "total": 5, "issues": [{"key": "A-5"}]},
    ]
    client = make_client(pages)
    # sanity
    client.get_myself()
    got = [it["key"] for it in client.search_issues_stream(jql="project = A")]
    assert got == ["A-1", "A-2", "A-3", "A-4", "A-5"]
