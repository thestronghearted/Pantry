"""Fakes for the systems the responder talks to: the app, Prometheus, Loki, and the LLM."""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings


class FakeStack:
    """One in-memory stand-in for the app (flags + shopping list), Prometheus and Loki."""

    def __init__(self, flags=None, loki_lines=None, probe_recovers_after: int = 0):
        self.flags = flags if flags is not None else {"shopping_list_v2": True}
        self.loki_lines = loki_lines or ['{"level":"ERROR","message":"journey finished","journey":"shopping_list"}']
        self.requests: list[tuple[str, str]] = []
        self.probe_failures_left = probe_recovers_after

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append((request.method, path))
        if path == "/api/v1/query":
            return httpx.Response(200, json={"data": {"result": [{"metric": {}, "value": [0, "0.62"]}]}})
        if path == "/loki/api/v1/query_range":
            return httpx.Response(200, json={"data": {"result": [{"values": [["1", line] for line in self.loki_lines]}]}})
        if path == "/admin/flags" and request.method == "GET":
            assert request.headers["x-admin-token"] == "admin-secret"
            return httpx.Response(200, json=[{"name": n, "enabled": e, "description": ""} for n, e in self.flags.items()])
        if path.startswith("/admin/flags/") and request.method == "PUT":
            name = path.rsplit("/", 1)[1]
            self.flags[name] = json.loads(request.content)["enabled"]
            return httpx.Response(200, json={"name": name, "enabled": self.flags[name]})
        if path == "/api/auth/login":
            return httpx.Response(200, json={})
        if path == "/api/shopping-list":
            assert request.headers["x-synthetic"] == "1"
            broken = self.flags.get("shopping_list_v2") or self.probe_failures_left > 0
            if self.probe_failures_left > 0:
                self.probe_failures_left -= 1
            return httpx.Response(500 if broken else 200, json={}, headers={"x-trace-id": "ab" * 16})
        return httpx.Response(404)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        app_url="http://app", prometheus_url="http://prom", loki_url="http://loki", admin_token="admin-secret",
        probe_email="probe@example.com", probe_password="probe-secret-for-tests", anthropic_api_key=None,
        report_dir=tmp_path / "reports", probe_retries=2, probe_wait_seconds=0, cooldown_seconds=600,
    )


@pytest.fixture
def stack():
    return FakeStack()


def make_toolbox(settings, stack):
    from app.tools import Toolbox

    transport = httpx.MockTransport(stack.handler)
    return Toolbox(settings, client=httpx.Client(transport=transport), probe_transport=transport, sleep=lambda _: None)


# ---- a scripted stand-in for the Anthropic client -----------------------------------------
def tool_use(tool_name, id_, /, **inputs):
    return SimpleNamespace(type="tool_use", id=id_, name=tool_name, input=inputs)


def text(content):
    return SimpleNamespace(type="text", text=content)


class FakeLLM:
    """Replays scripted responses; records what the agent sent so tests can inspect tool results."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        # the agent keeps appending to one list, so snapshot what the model saw at this point
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        if not self.script:
            return SimpleNamespace(content=[text("done")])
        nxt = self.script.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return SimpleNamespace(content=nxt)
