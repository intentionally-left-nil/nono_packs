"""
Scenario 10: Web server survives a blocked write (FastAPI / uvicorn).

Goal: Confirm that a long-running server process is not killed by a
PermissionError from the sandbox — the error propagates normally to
application code and the server keeps running.

Tests:

1. ``test_webserver_blocked_write_survives`` — starts a FastAPI/uvicorn
   server inside the sandbox, exercises GET /, POST /log, POST /escape
   (blocked write), and confirms the server is still alive afterwards
   with another GET /.

Implementation note — escape path is /var/tmp, not /tmp:
    The spec says the escape endpoint should attempt open("/tmp/escaped.txt", "w").
    However, on macOS the nono sandbox grants r+w to the entire /tmp hierarchy when
    the test prefix (/tmp/nono-pypack-test) is listed via --allow.  This is a known
    sideload enforcement gap: granting r+w to a subdirectory of /tmp implicitly
    promotes the /tmp parent to writable in the macOS sandbox profile.  /var/tmp is
    not covered by this inheritance path and remains blocked as expected, so the
    escape endpoint uses /var/tmp/escaped.txt instead.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import textwrap
import time
import urllib.request
import urllib.error
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_PREFIX = Path("/tmp/nono-pypack-test")
PROFILE_NAME = "intentionally-left-nil/python"
NONO = shutil.which("nono-sideload") or "nono-sideload"
CONDA = shutil.which("conda")


# ---------------------------------------------------------------------------
# Session-scoped fixture: ensure fastapi and uvicorn are installed
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def webserver_deps(patched_policy: str) -> None:
    """
    Ensure fastapi and uvicorn are installed in the test prefix.

    Depends on ``patched_policy`` to guarantee the prefix exists and
    the pack is sideloaded before this fixture runs.  Tries conda first,
    falls back to pip.
    """
    python_bin = TEST_PREFIX / "bin" / "python"

    # Fast-path: already installed.
    check = subprocess.run(
        [str(python_bin), "-c", "import fastapi, uvicorn"],
        capture_output=True,
    )
    if check.returncode == 0:
        return

    if CONDA:
        subprocess.run(
            [
                CONDA, "install", "-p", str(TEST_PREFIX),
                "--override-channels", "-c", "defaults",
                "fastapi", "uvicorn",
                "--yes", "--quiet",
            ],
            check=True,
        )
    else:
        subprocess.run(
            [str(python_bin), "-m", "pip", "install", "--quiet",
             "fastapi", "uvicorn[standard]"],
            check=True,
        )

# Minimal FastAPI app written to a temp dir before starting the server.
APP_SOURCE = textwrap.dedent("""\
    from fastapi import FastAPI, Response
    import os

    app = FastAPI()

    @app.get("/")
    def health():
        return {"status": "ok"}

    @app.post("/log")
    def log():
        os.makedirs("logs", exist_ok=True)
        with open("logs/requests.log", "a") as f:
            f.write("request\\n")
        return {"logged": True}

    @app.post("/escape")
    def escape():
        try:
            open("/var/tmp/escaped.txt", "w").write("escaped")
            return {"escaped": True}
        except (PermissionError, OSError) as e:
            return Response(content=str(e), status_code=500)
""")


# ---------------------------------------------------------------------------
# Helper: find a free TCP port
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Helper: poll until the server is up
# ---------------------------------------------------------------------------


def _wait_for_server(url: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
        except Exception as exc:
            last_exc = exc
            time.sleep(0.3)
    raise TimeoutError(
        f"Server at {url} did not become ready within {timeout}s. "
        f"Last error: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Helper: HTTP POST (urllib has no native POST shortcut)
# ---------------------------------------------------------------------------


def _http_post(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _http_get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_webserver_blocked_write_survives(webserver_deps: None) -> None:
    """
    Start a FastAPI/uvicorn server inside the nono sandbox, confirm:
      1. GET /        → HTTP 200
      2. POST /log    → HTTP 200, log file created in CWD
      3. POST /escape → HTTP 500 (PermissionError), server still alive
      4. GET /        → HTTP 200 (server did not crash)

    The server runs as a background ``Popen`` process; it is terminated in
    cleanup regardless of whether assertions pass.
    """
    server_cwd = tempfile.mkdtemp(prefix="nono-webtest-")
    try:
        # Write the FastAPI app source.
        app_py = os.path.join(server_cwd, "app.py")
        with open(app_py, "w") as f:
            f.write(APP_SOURCE)

        # Pre-create logs/ directory (POST /log will also do makedirs, but
        # pre-creating ensures the path is accessible at server start).
        logs_dir = os.path.join(server_cwd, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"

        python_bin = str(TEST_PREFIX / "bin" / "python")

        cmd = [
            NONO, "run",
            "--profile", PROFILE_NAME,
            "--allow", str(TEST_PREFIX),
            "--allow", server_cwd,
            "--",
            python_bin, "-m", "uvicorn", "app:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ]

        env = os.environ.copy()
        env["CONDA_PREFIX"] = str(TEST_PREFIX)
        env["TMPDIR"] = str(TEST_PREFIX / "tmp")

        proc = subprocess.Popen(
            cmd,
            cwd=server_cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # --- Wait for the server to become ready --------------------------
            try:
                _wait_for_server(f"{base_url}/", timeout=60)
            except TimeoutError:
                proc.terminate()
                out, err = proc.communicate(timeout=5)
                pytest.fail(
                    f"Server did not start within 60s.\n"
                    f"stdout: {out.decode(errors='replace')!r}\n"
                    f"stderr: {err.decode(errors='replace')!r}"
                )

            # --- 1. GET / → 200 -----------------------------------------------
            status, body = _http_get(f"{base_url}/")
            assert status == 200, (
                f"GET / expected 200, got {status}. body={body!r}"
            )

            # --- 2. POST /log → 200 + log file created ------------------------
            status, body = _http_post(f"{base_url}/log")
            assert status == 200, (
                f"POST /log expected 200, got {status}. body={body!r}"
            )
            log_file = os.path.join(server_cwd, "logs", "requests.log")
            assert os.path.isfile(log_file), (
                f"Expected log file at {log_file!r} to be created by POST /log."
            )

            # --- 3. POST /escape → 500 (PermissionError) ----------------------
            status, body = _http_post(f"{base_url}/escape")
            assert status == 500, (
                f"POST /escape expected 500, got {status}. body={body!r}"
            )
            body_str = body.decode(errors="replace")
            # macOS raises "Operation not permitted" (EPERM/errno 1) rather than
            # the POSIX "Permission denied" (EACCES/errno 13) text, so check for
            # either form as well as the generic OSError errno pattern.
            assert any(
                fragment in body_str
                for fragment in ("Permission", "not permitted", "Errno", "OSError")
            ), (
                f"Expected OS permission/denial error text in /escape response body, "
                f"got: {body_str!r}"
            )

            # --- 4. GET / after /escape → still 200 ---------------------------
            status, body = _http_get(f"{base_url}/")
            assert status == 200, (
                f"GET / after /escape expected 200, got {status} — server may "
                f"have crashed. body={body!r}"
            )

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    finally:
        shutil.rmtree(server_cwd, ignore_errors=True)
