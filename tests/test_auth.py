from __future__ import annotations
import httpx
from jira_reporting.config import Settings, MYSELF_PATH
from jira_reporting.jira_api import JiraAPI

def make_settings() -> Settings:
    # Dummy-Settings für Tests; verify=False nur hier im Test (keine echten Calls).
    return Settings(
        base_url="https://jira.example.com",
        pat="TEST_PAT",
        ca_bundle=None,
        timeout_s=5.0,
    )

def test_auth_check_success():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == MYSELF_PATH:
            return httpx.Response(200, json={"name": "tester", "displayName": "Test User"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    s = make_settings()
    client = s.build_client(transport=transport)
    api = JiraAPI(s, client=client)

    me = api.auth_check()
    assert me["name"] == "tester"

def test_auth_check_unauthorized():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == MYSELF_PATH:
            return httpx.Response(401, json={"errorMessages": ["Unauthorized"]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    s = make_settings()
    client = s.build_client(transport=transport)
    api = JiraAPI(s, client=client)

    try:
        api.auth_check()
        assert False, "auth_check() sollte bei 401 raise_for_status() auslösen"
    except httpx.HTTPStatusError as e:
        assert e.response.status_code == 401
