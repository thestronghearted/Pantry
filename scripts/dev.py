#!/usr/bin/env python3
"""One entry point for local work, on Windows, macOS and Linux.

    py scripts/dev.py up                 start everything (app, Postgres, Grafana stack, responder)
    py scripts/dev.py down [--volumes]   stop it (--volumes also deletes the database)
    py scripts/dev.py test               run every test suite (starts a throwaway Postgres in Docker)
    py scripts/dev.py simulate-incident  inject a bad release and watch alert -> responder -> recovery
    py scripts/dev.py logs [service]     follow container logs
"""
from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROM_IMAGE = "prom/prometheus:v2.55.1"
PG_IMAGE = "postgres:16-alpine"


def say(msg: str) -> None:
    print(f"==> {msg}", flush=True)


def run(cmd: list[str], cwd: Path = ROOT, env: dict | None = None, check: bool = True) -> int:
    proc = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})})
    if check and proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc.returncode


def require_docker() -> None:
    if shutil.which("docker") is None:
        raise SystemExit("Docker is not installed. Install Docker Desktop: https://www.docker.com/products/docker-desktop/")
    probe = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if probe.returncode != 0:
        raise SystemExit("Docker is not running. Start Docker Desktop, wait until it says 'running', then try again.")


# ---- .env -----------------------------------------------------------------------------------
def ensure_env() -> None:
    """Create .env with random secrets on first run. Existing values are never touched."""
    path = ROOT / ".env"
    if path.exists():
        return
    say("creating .env with freshly generated random secrets (it is git-ignored)")
    token = lambda: secrets.token_urlsafe(24)
    lines = [
        f"POSTGRES_PASSWORD={token()}",
        f"SESSION_SECRET={secrets.token_urlsafe(48)}",
        f"ADMIN_TOKEN={token()}",
        f"GRAFANA_PASSWORD={token()}",
        "PROBE_EMAIL=probe@pantry-probe.com",
        f"PROBE_PASSWORD={token()}",
        "ANTHROPIC_API_KEY=",
        "RESPONDER_MODEL=claude-sonnet-5-5",
        "GITHUB_TOKEN=",
        "GITHUB_REPOSITORY=thestronghearted/Pantry",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_env() -> dict[str, str]:
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


# ---- up / down ------------------------------------------------------------------------------
def wait_for(url: str, seconds: int = 180) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)
    return False


def cmd_up(_args: list[str]) -> int:
    require_docker()
    ensure_env()
    say("building and starting the system (first run downloads images, give it a few minutes)")
    run(["docker", "compose", "up", "-d", "--build"])
    say("waiting for the app to answer")
    if not wait_for("http://localhost:8080/ready"):
        run(["docker", "compose", "logs", "--tail", "60", "app"], check=False)
        raise SystemExit("The app did not become ready. Logs above.")
    print(
        "\nPantry Plan is running:\n"
        "  App         http://localhost:8080\n"
        "  Grafana     http://localhost:3000   (dashboard: Pantry Plan / User journeys)\n"
        "  Prometheus  http://localhost:9090\n"
        "  Responder   http://localhost:9000/incidents\n"
        "\nTry the incident drill:  py scripts/dev.py simulate-incident\n"
        "Stop everything:         py scripts/dev.py down\n"
    )
    return 0


def cmd_down(args: list[str]) -> int:
    require_docker()
    cmd = ["docker", "compose", "down"]
    if "--volumes" in args:
        cmd.append("--volumes")
    return run(cmd, check=False)


def cmd_logs(args: list[str]) -> int:
    require_docker()
    return run(["docker", "compose", "logs", "-f", "--tail", "100", *args], check=False)


# ---- tests ----------------------------------------------------------------------------------
def venv_python(folder: Path) -> str:
    venv = folder / ".venv"
    exe = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not exe.exists():
        say(f"creating virtualenv in {venv.relative_to(ROOT)}")
        run([sys.executable, "-m", "venv", str(venv)])
    return str(exe)


def install_python_deps(folder: Path, python: str) -> None:
    stamp = folder / ".venv" / ".deps-installed"
    req = folder / "requirements-dev.txt"
    if stamp.exists() and stamp.stat().st_mtime >= max(req.stat().st_mtime, (folder / "requirements.txt").stat().st_mtime):
        return
    say(f"installing {folder.name} dependencies")
    run([python, "-m", "pip", "install", "-q", "-r", str(req)])
    stamp.write_text("ok")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_test_db() -> tuple[str, str]:
    name = f"pantry-test-db-{secrets.token_hex(3)}"
    port = free_port()
    say(f"starting throwaway Postgres on port {port}")
    run(["docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_PASSWORD=test", "-e", "POSTGRES_DB=pantry_test",
         "-p", f"127.0.0.1:{port}:5432", PG_IMAGE], check=True)
    for _ in range(60):
        ready = subprocess.run(["docker", "exec", name, "pg_isready", "-U", "postgres", "-d", "pantry_test"], capture_output=True)
        if ready.returncode == 0:
            time.sleep(1)  # pg_isready can answer during the initialisation restart
            if subprocess.run(["docker", "exec", name, "pg_isready", "-U", "postgres"], capture_output=True).returncode == 0:
                return name, f"postgresql://postgres:test@127.0.0.1:{port}/pantry_test"
        time.sleep(1)
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    raise SystemExit("Postgres did not start in time")


def cmd_test(_args: list[str]) -> int:
    require_docker()
    results: dict[str, int] = {}
    db_name, db_url = start_test_db()
    try:
        backend = ROOT / "backend"
        py = venv_python(backend)
        install_python_deps(backend, py)
        say("backend: unit + integration tests (real Postgres)")
        results["backend"] = run([py, "-m", "pytest", "tests", "-q"], cwd=backend, env={"TEST_DATABASE_URL": db_url}, check=False)

        responder = ROOT / "responder"
        rpy = venv_python(responder)
        install_python_deps(responder, rpy)
        say("responder: tests")
        results["responder"] = run([rpy, "-m", "pytest", "-q"], cwd=responder, check=False)

        frontend = ROOT / "frontend"
        npm = shutil.which("npm") or "npm"
        if not (frontend / "node_modules").exists():
            say("frontend: installing packages")
            run([npm, "ci", "--no-audit", "--no-fund"], cwd=frontend)
        say("frontend: tests")
        results["frontend"] = run([npm, "test"], cwd=frontend, check=False)

        say("alert rules: promtool unit tests")
        results["alert rules"] = run(
            ["docker", "run", "--rm", "-v", f"{ROOT / 'observability'}:/rules:ro", "-w", "/rules", "--entrypoint", "promtool",
             PROM_IMAGE, "test", "rules", "alerts_test.yml"], check=False)
    finally:
        subprocess.run(["docker", "rm", "-f", db_name], capture_output=True)

    print("\n---- summary ----")
    for name, code in results.items():
        print(f"  {'PASS' if code == 0 else 'FAIL'}  {name}")
    return 0 if all(c == 0 for c in results.values()) else 1


# ---- incident drill -------------------------------------------------------------------------
def cmd_simulate(args: list[str]) -> int:
    ensure_env()
    return run([sys.executable, str(ROOT / "scripts" / "simulate_incident.py"), *args], check=False)


COMMANDS = {"up": cmd_up, "down": cmd_down, "test": cmd_test, "logs": cmd_logs, "simulate-incident": cmd_simulate}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 2
    return COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
