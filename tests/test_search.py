# tests/test_search.py
from __future__ import annotations
import json
import httpx
from jira_reporting.config import Settings
from jira_reporting.jira_api import JiraClient
from jira_reporting.extract import extract_issues


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


def test_extract_issues_fetches_full_changelog(monkeypatch):
    changelog_pages = {
        0: {"startAt": 0, "maxResults": 2, "total": 3, "values": [{"id": "1"}, {"id": "2"}]},
        2: {"startAt": 2, "maxResults": 2, "total": 3, "values": [{"id": "3"}]},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/rest/api/2/myself"):
            return httpx.Response(200, json={"name": "tester"})
        if path.endswith("/rest/api/2/search"):
            body = json.loads((request.content or b"{}").decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "startAt": body.get("startAt", 0),
                    "maxResults": body.get("maxResults", 2),
                    "total": 1,
                    "issues": [{"key": "A-1"}],
                },
            )
        if path.endswith("/changelog"):
            start_at = int(request.url.params.get("startAt", "0"))
            payload = changelog_pages.get(start_at)
            if payload is None:
                payload = {
                    "startAt": start_at,
                    "maxResults": int(request.url.params.get("maxResults", "100")),
                    "total": 3,
                    "values": [],
                }
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    settings = Settings(base_url="https://jira.local", pat="t", timeout_s=5.0)

    original_build_client = Settings.build_client

    def build_client(self, transport: httpx.BaseTransport | None = None) -> httpx.Client:
        if transport is None:
            transport = mock_transport
        return original_build_client(self, transport=transport)

    monkeypatch.setattr(Settings, "build_client", build_client)

    issues = list(
        extract_issues(
            settings=settings,
            jql="project = A",
            page_size=2,
            fields=["key"],
            fetch_full_changelog=True,
        )
    )

    assert len(issues) == 1
    changelog = issues[0]["changelog"]
    assert [h["id"] for h in changelog["histories"]] == ["1", "2", "3"]
    assert changelog["total"] == 3
    assert changelog["maxResults"] == 2
