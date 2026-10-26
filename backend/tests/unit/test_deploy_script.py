"""scripts/ci/deploy.sh must wait for the deployed image tag, not just for a healthy instance."""
import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ci" / "deploy.sh"


def _bash_has_tools() -> bool:
    bash = shutil.which("bash")
    if not bash:
        return False
    # run python3 for real: on Windows a Store stub answers `command -v` but cannot execute
    probe = subprocess.run([bash, "-c", "command -v curl && python3 -c pass"], capture_output=True)
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(not _bash_has_tools(), reason="needs bash, curl and python3")


class FakeRender:
    """Stands in for Render: a deploy hook plus a service whose /health reports a version sequence."""

    def __init__(self, versions: list[str], ready: bool = True):
        self.versions = versions
        self.ready = ready
        self.health_calls = 0
        self.hook_images: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, body: dict):
                data = json.dumps(body, separators=(",", ":")).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                query = parse_qs(urlparse(self.path).query)
                outer.hook_images.extend(query.get("imgURL", []))
                self._send(200, {"ok": True})

            def do_GET(self):
                if self.path == "/health":
                    index = min(outer.health_calls, len(outer.versions) - 1)
                    outer.health_calls += 1
                    version = outer.versions[index]
                    # None models an image built before /health reported a version
                    self._send(200, {"status": "ok"} if version is None else {"status": "ok", "version": version})
                elif self.path == "/ready":
                    self._send(200 if outer.ready else 503, {"status": "ready" if outer.ready else "starting"})
                else:
                    self._send(404, {})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def run_deploy(render: FakeRender, image: str = "ghcr.io/o/pantry-app:sha-new1234", attempts: int = 5):
    env = dict(
        os.environ,
        DEPLOY_HOOK=f"{render.url}/hook",
        IMAGE=image,
        BASE_URL=render.url,
        WAIT_ATTEMPTS=str(attempts),
        WAIT_SECONDS="0",
    )
    return subprocess.run([shutil.which("bash"), str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)


@pytest.fixture
def render():
    created = []

    def make(versions, ready=True):
        fake = FakeRender(versions, ready)
        created.append(fake)
        return fake

    yield make
    for fake in created:
        fake.stop()


def test_waits_through_the_old_version_until_the_new_one_serves(render):
    fake = render(["sha-old0000", "sha-old0000", "sha-new1234"])
    result = run_deploy(fake)
    assert result.returncode == 0, result.stderr
    assert fake.health_calls == 3  # two answers from the old instance were not accepted
    assert fake.hook_images == ["ghcr.io/o/pantry-app:sha-new1234"]
    assert "Serving sha-new1234" in result.stdout


def test_fails_when_the_old_version_keeps_serving(render):
    fake = render(["sha-old0000"])
    result = run_deploy(fake, attempts=3)
    assert result.returncode == 1
    assert "did not report version sha-new1234" in result.stderr
    assert "sha-old0000" in result.stderr  # shows what it saw instead


def test_fails_for_an_image_that_does_not_report_a_version(render):
    fake = render([None])
    result = run_deploy(fake, attempts=2)
    assert result.returncode == 1
    assert "did not report version sha-new1234" in result.stderr


def test_matching_version_but_not_ready_is_not_success(render):
    fake = render(["sha-new1234"], ready=False)
    result = run_deploy(fake, attempts=2)
    assert result.returncode == 1


def test_rejects_an_image_without_a_plain_tag(render):
    fake = render(["sha-new1234"])
    result = run_deploy(fake, image="ghcr.io/o/pantry-app")
    assert result.returncode == 1
    assert "plain tag" in result.stderr
    assert fake.hook_images == []  # nothing was deployed
