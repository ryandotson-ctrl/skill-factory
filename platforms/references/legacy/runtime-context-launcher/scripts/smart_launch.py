#!/usr/bin/env python3
"""UDS-first backend launcher for PFEMacOS dev/bundled runtime contexts.

This script intentionally avoids legacy supervise.sh and frontend port assumptions.
"""

from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional


def shell(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def find_repo_root(start: Path) -> Optional[Path]:
    for candidate in [start] + list(start.parents):
        if (candidate / "apps/project-free-energy/backend/main.py").exists():
            return candidate
    return None


def resolve_python(repo_root: Path) -> Optional[Path]:
    env_python = os.environ.get("PFE_BACKEND_PYTHON", "").strip()
    candidates = []
    if env_python:
        candidates.append(Path(env_python))
    candidates.extend(
        [
            repo_root / "venv_312/bin/python",
            repo_root / "apps/project-free-energy/venv/bin/python",
            repo_root / ".venv/bin/python",
        ]
    )
    for path in candidates:
        if path.exists() and os.access(path, os.X_OK):
            return path
    return None


def parse_bool(value: str, default: bool) -> bool:
    if not value:
        return default
    return value.strip().lower() not in {"0", "false", "off", "no"}


def app_support_dir() -> Path:
    return Path.home() / "Library/Application Support/Project Free Energy"


def endpoint_manifest_path() -> Path:
    return app_support_dir() / "backend_endpoint.json"


def make_socket_path() -> Path:
    socket_dir = Path("/tmp/pfe_ipc")
    socket_dir.mkdir(parents=True, exist_ok=True)
    compact = uuid.uuid4().hex[:12]
    path = socket_dir / f"pfe_{compact}.sock"
    if len(path.as_posix().encode("utf-8")) >= 100:
        raise RuntimeError("Generated socket path is too long for AF_UNIX safety margin.")
    return path


def random_session_token() -> str:
    raw = os.urandom(32)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def wait_for_health(transport: str, session_token: str, socket_path: Optional[Path], port: int, timeout_s: float = 12.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if transport == "uds":
            cmd = [
                "curl",
                "--silent",
                "--fail",
                "--unix-socket",
                socket_path.as_posix() if socket_path else "",
                "-H",
                f"X-PFE-Session: {session_token}",
                "http://localhost/health",
            ]
            ok = shell(cmd).returncode == 0
        else:
            cmd = [
                "curl",
                "--silent",
                "--fail",
                "-H",
                f"X-PFE-Session: {session_token}",
                f"http://127.0.0.1:{port}/health",
            ]
            ok = shell(cmd).returncode == 0
        if ok:
            return True
        time.sleep(0.3)
    return False


def write_manifest(transport: str, socket_path: Optional[Path], port: int, token: str, pid: int) -> None:
    payload = {
        "transport": transport,
        "socket_path": socket_path.as_posix() if socket_path else None,
        "loopback_port": port,
        "session_token": token,
        "pid": pid,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": "smart_launch_v2",
    }
    destination = endpoint_manifest_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(destination)


def launch_backend(python_bin: Path, backend_dir: Path, transport: str, socket_path: Optional[Path], port: int, reload_enabled: bool) -> subprocess.Popen[str]:
    args = [python_bin.as_posix(), "-m", "uvicorn", "backend.main:app", "--no-use-colors", "--log-level", "info"]
    if transport == "uds":
        args.extend(["--uds", socket_path.as_posix()])
    else:
        args.extend(["--host", "127.0.0.1", "--port", str(port)])
    if reload_enabled:
        args.append("--reload")

    env = os.environ.copy()
    env.update(
        {
            "PROJECT_MODE": "SHARED",
            "LOG_LEVEL": "INFO",
            "PYTHONUNBUFFERED": "1",
            "PFE_IPC_MODE": transport,
            "PFE_SOCKET_PATH": socket_path.as_posix() if socket_path else "",
            "PFE_SESSION_TOKEN": env["PFE_SESSION_TOKEN"],
            "PFE_BACKEND_RELOAD": "1" if reload_enabled else "0",
            "PFE_ALLOW_DEFAULT_USER_FALLBACK": "1",
        }
    )

    return subprocess.Popen(
        args,
        cwd=backend_dir.as_posix(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def terminate_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=1)


def main() -> int:
    print("Runtime Context Launcher v2.1: UDS-first backend launch")
    repo_root = find_repo_root(Path.cwd())
    if repo_root is None:
        print("ERROR: Could not locate repository root containing apps/project-free-energy/backend/main.py")
        return 1

    backend_dir = repo_root / "apps/project-free-energy"
    python_bin = resolve_python(repo_root)
    if python_bin is None:
        print("ERROR: No executable Python found. Set PFE_BACKEND_PYTHON or create venv_312/.venv.")
        return 1

    token = random_session_token()
    os.environ["PFE_SESSION_TOKEN"] = token

    port_raw = os.environ.get("PFE_BACKEND_PORT", "8001").strip()
    try:
        loopback_port = int(port_raw)
    except ValueError:
        loopback_port = 8001

    reload_enabled = parse_bool(os.environ.get("PFE_BACKEND_RELOAD", ""), default=False)

    uds_socket = make_socket_path()
    print(f"Attempting UDS launch on {uds_socket.as_posix()}")
    proc = launch_backend(
        python_bin=python_bin,
        backend_dir=backend_dir,
        transport="uds",
        socket_path=uds_socket,
        port=loopback_port,
        reload_enabled=reload_enabled,
    )
    if wait_for_health("uds", token, uds_socket, loopback_port):
        write_manifest("uds", uds_socket, loopback_port, token, proc.pid)
        print(f"READY transport=uds pid={proc.pid} manifest={endpoint_manifest_path().as_posix()}")
        return 0

    print("UDS launch failed health checks, falling back to loopback.")
    terminate_process(proc)
    proc = launch_backend(
        python_bin=python_bin,
        backend_dir=backend_dir,
        transport="loopback",
        socket_path=None,
        port=loopback_port,
        reload_enabled=reload_enabled,
    )
    if wait_for_health("loopback", token, None, loopback_port):
        write_manifest("loopback", None, loopback_port, token, proc.pid)
        print(f"READY transport=loopback pid={proc.pid} manifest={endpoint_manifest_path().as_posix()}")
        return 0

    terminate_process(proc)
    print("ERROR: Backend failed to start in both UDS and loopback modes.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
