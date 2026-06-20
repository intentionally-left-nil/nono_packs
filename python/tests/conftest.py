"""
conftest.py — pytest fixtures for the nono python pack test suite.

The Makefile (python/tests/Makefile) is responsible for creating the conda
environment that pytest itself runs in.  These fixtures only manage the
*sandboxed* Python prefix — the isolated conda env (or venv fallback) that
the nono sandbox wraps during tests.

Key design points
-----------------
- ``python_prefix``    — session-scoped; creates /tmp/nono-pypack-test, tears
                         it down after the session.
- ``patched_policy``   — session-scoped; sideloads the pack then patches
                         ``$PREFIX`` in the *installed* profile (in the pack
                         store), so nono resolves the profile by name and can
                         expand ``$PACK_DIR`` in session_hooks normally.
- ``sandbox``          — session-scoped ``SandboxHandle``; exposes three ways
                         to run code inside the nono sandbox:

                         sandbox(code, *, extra_env, extra_allow, timeout)
                             Run ``python -c <code>``; return CompletedProcess.

                         sandbox.popen(argv, *, extra_env, extra_allow, cwd,
                                       **kwargs) → Popen
                             Same invocation prefix, but appends *argv* (e.g.
                             ``["-m", "uvicorn", "app:app", ...]``) and returns
                             a ``subprocess.Popen`` handle.  Caller owns the
                             process lifecycle.

                         sandbox.run_in(python_bin, argv, *, extra_env,
                                        extra_allow, timeout) → CompletedProcess
                             Like the callable but uses an arbitrary
                             ``python_bin`` instead of the default prefix
                             python.

- ``third_party_deps`` — session-scoped; installs fastapi, uvicorn, requests
                         into the test prefix (idempotent).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Generator

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent  # …/nono_packs
PACK_DIR = REPO_ROOT / "python"
POLICY_SRC = PACK_DIR / "policy.json"

TEST_PREFIX = Path("/tmp/nono-pypack-test")

# Profile name as known to nono after sideloading (install_as in package.json).
PROFILE_NAME = "intentionally-left-nil/python"

NONO = shutil.which("nono-sideload") or "nono-sideload"
CONDA = shutil.which("conda")


# ---------------------------------------------------------------------------
# Fixture: isolated sandboxed Python prefix
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def python_prefix() -> Generator[Path, None, None]:
    """
    Create an isolated Python prefix for the sandboxed process to run in.

    Prefers conda (``conda create -p``); falls back to ``python3 -m venv``.
    Cleaned up after the session.
    """
    prefix = TEST_PREFIX

    if prefix.exists():
        shutil.rmtree(prefix)

    if CONDA:
        subprocess.run(
            [CONDA, "create", "-p", str(prefix),
             "--override-channels", "-c", "defaults",
             "python=3.12", "--yes", "--quiet"],
            check=True,
        )
    else:
        subprocess.run(
            [sys.executable, "-m", "venv", str(prefix)],
            check=True,
        )

    yield prefix

    try:
        shutil.rmtree(prefix)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fixture: sideload the pack
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sideloaded_pack(python_prefix: Path) -> Generator[None, None, None]:
    """
    Patch ``$PREFIX`` in the source policy, sideload, then restore.

    nono-sideload records a hash of each artifact at install time and
    verifies it on every ``run``.  Patching after sideloading therefore
    fails the tamper check.  Instead we patch the source file before
    sideloading so the stored hash matches the patched content, then
    restore the original afterwards so the repo stays clean.
    """
    original = POLICY_SRC.read_text()
    POLICY_SRC.write_text(original.replace("$PREFIX", str(python_prefix)))
    try:
        subprocess.run(
            [NONO, "sideload", str(PACK_DIR)],
            check=True,
            cwd=str(REPO_ROOT),
        )
    finally:
        POLICY_SRC.write_text(original)

    yield


# ---------------------------------------------------------------------------
# Fixture: pre-create tmp dirs and expose profile name
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def patched_policy(python_prefix: Path, sideloaded_pack: None) -> Generator[str, None, None]:
    """Yield the profile name for use with ``nono-sideload run --profile``."""
    yield PROFILE_NAME


# ---------------------------------------------------------------------------
# SandboxHandle — callable + .popen() + .run_in()
# ---------------------------------------------------------------------------


class SandboxHandle:
    """
    Thin wrapper around ``nono-sideload run`` that provides three calling
    conventions:

    * ``handle(code, ...)``                  — run ``python -c <code>``
    * ``handle.popen(argv, ...)``            — ``Popen`` for long-running procs
    * ``handle.run_in(python_bin, argv, ...)`` — run with a different python
    """

    def __init__(self, profile: str, python_prefix: Path) -> None:
        self._profile = profile
        self._prefix = python_prefix

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_cmd(self, extra_allow: list[str] | None = None) -> list[str]:
        """Build the ``nono run --profile … --allow …`` prefix."""
        cmd = [
            NONO, "run",
            "--profile", self._profile,
            "--allow", str(self._prefix),
        ]
        for path in (extra_allow or []):
            cmd += ["--allow", str(path)]
        return cmd

    def _base_env(self, extra_env: dict[str, str] | None = None) -> dict[str, str]:
        """Build the environment dict with CONDA_PREFIX / TMPDIR set."""
        env = os.environ.copy()
        env["CONDA_PREFIX"] = str(self._prefix)
        env["TMPDIR"] = str(self._prefix / "tmp")
        if extra_env:
            env.update(extra_env)
        return env

    # ------------------------------------------------------------------
    # Primary callable: run python -c <code>
    # ------------------------------------------------------------------

    def __call__(
        self,
        code: str,
        *,
        extra_env: dict[str, str] | None = None,
        extra_allow: list[str] | None = None,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess:
        """
        Run ``python -c <code>`` inside the nono sandbox.

        Parameters
        ----------
        code:
            Python source passed to ``python -c``.  Leading indentation is
            stripped via ``textwrap.dedent``.
        extra_env:
            Extra variables merged into the parent environment before invoking
            nono-sideload.
        extra_allow:
            Additional ``--allow <path>`` flags.
        timeout:
            Seconds before the subprocess is killed (default 30).
        """
        python_bin = self._prefix / "bin" / "python"
        cmd = self._base_cmd(extra_allow) + ["--", str(python_bin), "-c", textwrap.dedent(code)]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self._base_env(extra_env),
        )

    # ------------------------------------------------------------------
    # .popen() — long-running background process
    # ------------------------------------------------------------------

    def popen(
        self,
        argv: list[str],
        *,
        extra_env: dict[str, str] | None = None,
        extra_allow: list[str] | None = None,
        cwd: str | None = None,
        **kwargs,
    ) -> subprocess.Popen:
        """
        Start a long-running sandboxed process via ``subprocess.Popen``.

        Parameters
        ----------
        argv:
            Arguments appended after ``--`` in the nono invocation.  The first
            element is treated as a python flag/module (e.g. ``["-m", "uvicorn",
            "app:app", ...]``); the default python binary from the prefix is
            used as the executable.
        extra_env:
            Extra variables merged into the environment.
        extra_allow:
            Additional ``--allow <path>`` flags.
        cwd:
            Working directory for the child process.
        **kwargs:
            Forwarded verbatim to ``subprocess.Popen`` (e.g. ``stdout``,
            ``stderr``).

        Returns
        -------
        subprocess.Popen
            The caller owns the process lifecycle (terminate / wait / kill).
        """
        python_bin = self._prefix / "bin" / "python"
        cmd = self._base_cmd(extra_allow) + ["--", str(python_bin)] + list(argv)

        popen_kwargs: dict = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
        }
        popen_kwargs.update(kwargs)

        if cwd is not None:
            popen_kwargs["cwd"] = cwd

        return subprocess.Popen(
            cmd,
            env=self._base_env(extra_env),
            **popen_kwargs,
        )

    # ------------------------------------------------------------------
    # .run_in() — run with an arbitrary python binary
    # ------------------------------------------------------------------

    def run_in(
        self,
        python_bin: Path | str,
        argv: list[str],
        *,
        extra_env: dict[str, str] | None = None,
        extra_allow: list[str] | None = None,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess:
        """
        Run ``<python_bin> <argv>`` inside the nono sandbox.

        Like the primary callable but uses *python_bin* instead of the prefix's
        default ``bin/python``.  Useful for testing nested venvs or other
        interpreter paths.

        Parameters
        ----------
        python_bin:
            Absolute path to the Python interpreter to invoke.
        argv:
            Arguments passed to *python_bin* (e.g. ``["-c", "print('hi')"]``
            or ``["-m", "pytest"]``).
        extra_env:
            Extra variables merged into the environment.
        extra_allow:
            Additional ``--allow <path>`` flags.
        timeout:
            Seconds before the subprocess is killed (default 30).
        """
        cmd = self._base_cmd(extra_allow) + ["--", str(python_bin)] + list(argv)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self._base_env(extra_env),
        )


# ---------------------------------------------------------------------------
# Fixture: sandbox callable
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sandbox(patched_policy: str, python_prefix: Path) -> SandboxHandle:
    """
    Return a :class:`SandboxHandle` that runs Python code inside the nono
    sandbox.

    Usage::

        def test_something(sandbox):
            result = sandbox("print('hello')")
            assert result.returncode == 0
            assert "hello" in result.stdout

        def test_server(sandbox):
            proc = sandbox.popen(["-m", "uvicorn", "app:app", ...])
            ...
            proc.terminate()

        def test_venv(sandbox, python_prefix):
            venv_python = Path("/tmp/myvenv/bin/python")
            result = sandbox.run_in(venv_python, ["-c", "print('hi')"],
                                    extra_allow=["/tmp/myvenv"])
    """
    return SandboxHandle(patched_policy, python_prefix)


# ---------------------------------------------------------------------------
# Fixture: third-party dependencies (fastapi, uvicorn, requests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def third_party_deps(python_prefix: Path, patched_policy: str) -> None:
    """
    Ensure fastapi, uvicorn, and requests are installed in the test prefix.

    Depends on ``patched_policy`` to guarantee the prefix exists and the pack
    is sideloaded before this fixture runs.  Tries conda first (with
    ``--override-channels -c defaults``), falls back to pip.  Idempotent:
    checks whether the packages are already importable before attempting any
    install.
    """
    python_bin = python_prefix / "bin" / "python"

    # Fast-path: already installed.
    check = subprocess.run(
        [str(python_bin), "-c", "import fastapi, uvicorn, requests"],
        capture_output=True,
    )
    if check.returncode == 0:
        return

    if CONDA:
        subprocess.run(
            [
                CONDA, "install", "-p", str(python_prefix),
                "--override-channels", "-c", "defaults",
                "fastapi", "uvicorn", "requests",
                "--yes", "--quiet",
            ],
            check=True,
        )
    else:
        subprocess.run(
            [str(python_bin), "-m", "pip", "install", "--quiet",
             "fastapi", "uvicorn[standard]", "requests"],
            check=True,
        )
